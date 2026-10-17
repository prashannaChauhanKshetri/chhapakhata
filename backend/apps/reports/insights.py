"""Owner insights: how the business did over a period.

Everything is computed from the same records as the reports, so the figures
reconcile with them. "Work done" is the value of confirmed and delivered orders
by order date, which includes imported work-log history; "Invoiced" counts tax
invoices only.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce

from apps.billing.models import Invoice, InvoiceStatus, Payment, PaymentStatus
from apps.billing.selectors import AGING_BUCKETS, outstanding_by_customer
from apps.core.dates import BS_MONTHS, bs_month_range, bs_string, to_bs
from apps.core.money import ZERO, q2
from apps.customers.models import Customer
from apps.inventory.models import MovementType, StockMovement
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.production.models import Job, JobStageEvent, Stage

MONEY = DecimalField(max_digits=14, decimal_places=2)
DAILY_UP_TO_DAYS = 62
TOP_N = 8


def _sum(qs, expr) -> Decimal:
    return q2(qs.aggregate(v=Coalesce(Sum(expr), ZERO, output_field=MONEY))["v"])


def _buckets(date_from: dt.date, date_to: dt.date) -> list[tuple[str, dt.date, dt.date]]:
    """Daily buckets for short periods, BS months for longer ones."""
    if (date_to - date_from).days < DAILY_UP_TO_DAYS:
        days = (date_to - date_from).days + 1
        out = []
        for i in range(days):
            day = date_from + dt.timedelta(days=i)
            bs = to_bs(day)
            out.append((f"{BS_MONTHS[bs.month - 1][:3]} {bs.day}", day, day))
        return out
    out = []
    start = date_from
    while start <= date_to:
        month_start, month_end = bs_month_range(start)
        bs = to_bs(month_start)
        out.append(
            (
                f"{BS_MONTHS[bs.month - 1]} {bs.year}",
                max(month_start, date_from),
                min(month_end, date_to),
            )
        )
        start = month_end + dt.timedelta(days=1)
    return out


def insights(date_from: dt.date, date_to: dt.date) -> dict[str, Any]:
    orders = Order.objects.filter(order_date__range=(date_from, date_to)).exclude(
        status__in=[OrderStatus.QUOTATION, OrderStatus.CANCELLED]
    )
    payments = Payment.objects.filter(
        payment_date__range=(date_from, date_to), status=PaymentStatus.VALID
    )
    invoices = Invoice.objects.filter(
        invoice_date__range=(date_from, date_to), status=InvoiceStatus.ISSUED
    )

    order_count = orders.count()
    work_done = _sum(orders, "total")
    summary = {
        "work_done": work_done,
        "orders": order_count,
        "average_order": q2(work_done / order_count) if order_count else ZERO,
        "invoiced": _sum(invoices, "total"),
        "collected": _sum(payments, "amount"),
        "discounts": _sum(orders, "discount_amount"),
        "new_customers": Customer.objects.filter(
            created_at__date__range=(date_from, date_to)
        ).count(),
        "quotations_open": Order.objects.filter(status=OrderStatus.QUOTATION).count(),
    }

    # --- trend: work done vs collected ---
    work_by_day = dict(
        orders.values("order_date").annotate(v=Sum("total")).values_list("order_date", "v")
    )
    paid_by_day = dict(
        payments.values("payment_date").annotate(v=Sum("amount")).values_list("payment_date", "v")
    )

    def total_between(by_day: dict, start: dt.date, end: dt.date) -> float:
        return float(sum((v for d, v in by_day.items() if start <= d <= end), ZERO))

    trend = [
        {
            "label": label,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "work_done": total_between(work_by_day, start, end),
            "collected": total_between(paid_by_day, start, end),
        }
        for label, start, end in _buckets(date_from, date_to)
    ]

    # --- what sold, and to whom ---
    line_sqft = ExpressionWrapper(F("sqft") * F("quantity"), output_field=MONEY)
    items = (
        OrderItem.objects.filter(order__in=orders)
        .values("media_name")
        .annotate(
            amount=Sum("line_total"),
            pieces=Sum("quantity"),
            sqft=Sum(line_sqft),
            orders=Count("order", distinct=True),
        )
        .order_by("-amount")[:TOP_N]
    )
    top_items = [
        {
            "name": row["media_name"],
            "amount": q2(row["amount"] or 0),
            "pieces": row["pieces"] or 0,
            "sqft": q2(row["sqft"] or 0),
            "orders": row["orders"],
        }
        for row in items
    ]
    customers = (
        orders.values("customer_id", "customer__name")
        .annotate(amount=Sum("total"), orders=Count("id"))
        .order_by("-amount")[:TOP_N]
    )
    top_customers = [
        {
            "customer_id": row["customer_id"],
            "name": row["customer__name"],
            "amount": q2(row["amount"] or 0),
            "orders": row["orders"],
        }
        for row in customers
    ]

    # --- money in, by mode ---
    by_mode: dict[str, dict[str, Any]] = defaultdict(lambda: {"amount": ZERO, "count": 0})
    for p in payments.only("mode", "wallet", "amount"):
        entry = by_mode[p.mode_label]
        entry["amount"] += p.amount
        entry["count"] += 1
    payment_modes = sorted(
        ({"mode": k, "amount": q2(v["amount"]), "count": v["count"]} for k, v in by_mode.items()),
        key=lambda r: -r["amount"],
    )

    # --- dues and their age, as at the end of the period ---
    outstanding = outstanding_by_customer(date_to)
    aging = [
        {
            "label": label,
            "amount": q2(sum((o.buckets[label] for o in outstanding.values()), ZERO)),
        }
        for label, _ in AGING_BUCKETS
    ]
    names = dict(Customer.objects.filter(pk__in=list(outstanding)).values_list("pk", "name"))
    top_dues = [
        {
            "customer_id": o.customer_id,
            "name": names.get(o.customer_id, ""),
            "balance": o.balance,
            "oldest_due_date": o.oldest_due_date,
            "oldest_due_date_bs": bs_string(o.oldest_due_date),
        }
        for o in sorted(outstanding.values(), key=lambda o: -o.balance)[:TOP_N]
    ]

    # --- production: jobs finished in the period ---
    finished = (
        JobStageEvent.objects.filter(
            to_stage=Stage.READY, created_at__date__range=(date_from, date_to)
        )
        .order_by("job_id", "created_at")
        .distinct("job_id")
        .values("job_id", "created_at")
    )
    ready_at = {row["job_id"]: row["created_at"] for row in finished}
    jobs = Job.objects.filter(pk__in=list(ready_at)).select_related("order")
    on_time = with_deadline = 0
    turnaround_hours: list[float] = []
    for job in jobs:
        done = ready_at[job.pk]
        if job.deadline:
            with_deadline += 1
            on_time += int(done <= job.deadline)
        if job.order.confirmed_at:
            turnaround_hours.append((done - job.order.confirmed_at).total_seconds() / 3600)
    movements = StockMovement.objects.filter(created_at__date__range=(date_from, date_to))
    used = -_sum(movements.filter(movement_type=MovementType.CONSUMPTION), "quantity")
    wasted = -_sum(movements.filter(movement_type=MovementType.WASTAGE), "quantity")
    production = {
        "jobs_finished": len(ready_at),
        "on_time_percent": round(on_time / with_deadline * 100, 1) if with_deadline else None,
        "average_turnaround_hours": (
            round(sum(turnaround_hours) / len(turnaround_hours), 1) if turnaround_hours else None
        ),
        "material_used": q2(used),
        "material_wasted": q2(wasted),
        "wastage_percent": (
            round(float(wasted / (used + wasted) * 100), 1) if used + wasted > 0 else None
        ),
        "open_jobs": Job.objects.filter(
            stage__in=[Stage.DESIGN, Stage.READY_FOR_PRINT, Stage.PRINTING, Stage.FINISHING]
        ).count(),
        "average_job_value": q2(
            OrderItem.objects.filter(order__in=orders).aggregate(
                v=Coalesce(Avg("line_total"), ZERO, output_field=MONEY)
            )["v"]
        ),
    }

    return {
        "date_from": date_from,
        "date_to": date_to,
        "granularity": "day" if (date_to - date_from).days < DAILY_UP_TO_DAYS else "month",
        "summary": summary,
        "trend": trend,
        "top_items": top_items,
        "top_customers": top_customers,
        "payment_modes": payment_modes,
        "aging": aging,
        "top_dues": top_dues,
        "dues_total": q2(sum((o.balance for o in outstanding.values()), ZERO)),
        "production": production,
    }


def dues_follow_up(limit: int = 6) -> list[dict[str, Any]]:
    """Customers whose dues are oldest, for the front desk to call."""
    outstanding = outstanding_by_customer()
    rows = sorted(
        (o for o in outstanding.values() if o.oldest_due_date),
        key=lambda o: o.oldest_due_date,
    )[:limit]
    customers = {c.pk: c for c in Customer.objects.filter(pk__in=[o.customer_id for o in rows])}
    return [
        {
            "customer_id": o.customer_id,
            "name": customers[o.customer_id].name,
            "phone": customers[o.customer_id].phone,
            "balance": f"{o.balance:.2f}",
            "oldest_due_date": o.oldest_due_date.isoformat(),
            "oldest_due_date_bs": bs_string(o.oldest_due_date),
        }
        for o in rows
        if o.customer_id in customers
    ]
