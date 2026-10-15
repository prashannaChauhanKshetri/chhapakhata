"""The seven reports from the proposal (section 3.6), as format-neutral objects."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import Count, Sum
from django.db.models.functions import Abs

from apps.billing.models import (
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Payment,
    PaymentMode,
    PaymentStatus,
)
from apps.billing.selectors import outstanding_by_customer
from apps.core.dates import bs_string, local_today
from apps.core.money import ZERO, q2
from apps.customers.models import Customer
from apps.inventory.models import (
    MovementType,
    Roll,
    RollStatus,
    StockItem,
    StockKind,
    StockMovement,
)
from apps.orders.models import Order, OrderStatus
from apps.production.models import JobStageEvent, Stage

from .tables import Column, Metric, Report, Table, period_label


def _sum(qs, field: str) -> Decimal:
    return q2(qs.aggregate(s=Sum(field))["s"] or 0)


def _days(date_from: dt.date, date_to: dt.date):
    day = date_from
    while day <= date_to:
        yield day
        day += dt.timedelta(days=1)


def _mode_rows(payments) -> list[dict[str, Any]]:
    rows = []
    labels = dict(PaymentMode.choices)
    grouped = payments.values("mode", "wallet").annotate(count=Count("id"), amount=Sum("amount"))
    for row in grouped.order_by("mode", "wallet"):
        label = labels[row["mode"]]
        if row["mode"] == PaymentMode.WALLET and row["wallet"]:
            label = f"{label}: {row['wallet'].replace('_', ' ').title()}"
        rows.append({"mode": label, "count": row["count"], "amount": q2(row["amount"])})
    return rows


# --- 1. Daily sales -----------------------------------------------------------


def daily_sales(day: dt.date, **_: Any) -> Report:
    invoices = Invoice.objects.filter(invoice_date=day)
    issued = invoices.filter(status=InvoiceStatus.ISSUED)
    payments = Payment.objects.filter(payment_date=day, status=PaymentStatus.VALID)
    orders = Order.objects.filter(order_date=day).exclude(
        status__in=[OrderStatus.QUOTATION, OrderStatus.CANCELLED]
    )
    collected = _sum(payments, "amount")
    cash = _sum(payments.filter(mode=PaymentMode.CASH), "amount")
    return Report(
        slug="daily-sales",
        title="Daily sales",
        period=period_label(None, day),
        params={"date": day},
        summary=[
            Metric("Orders taken", orders.count(), "number"),
            Metric("Order value", _sum(orders, "total")),
            Metric("Invoiced", _sum(issued, "total")),
            Metric("VAT on invoices", _sum(issued, "vat_amount")),
            Metric("Collected", collected),
            Metric("Cash collected", cash),
            Metric("Digital and bank", q2(collected - cash)),
        ],
        tables=[
            Table(
                "Collection by payment mode",
                [
                    Column("mode", "Mode"),
                    Column("count", "Payments", "number"),
                    Column("amount", "Amount", "money"),
                ],
                _mode_rows(payments),
                totals={"mode": "Total", "count": payments.count(), "amount": collected},
            ),
            Table(
                "Invoices",
                [
                    Column("invoice_no", "Invoice"),
                    Column("customer", "Customer"),
                    Column("status", "Status"),
                    Column("vat", "VAT", "money"),
                    Column("total", "Total", "money"),
                ],
                [
                    {
                        "invoice_no": i.invoice_no,
                        "customer": i.customer_name,
                        "status": i.get_status_display(),
                        "vat": i.vat_amount,
                        "total": i.total,
                    }
                    for i in invoices.order_by("sequence")
                ],
                totals={
                    "invoice_no": "Total issued",
                    "vat": _sum(issued, "vat_amount"),
                    "total": _sum(issued, "total"),
                },
            ),
            Table(
                "Payments received",
                [
                    Column("receipt_no", "Receipt"),
                    Column("customer", "Customer"),
                    Column("mode", "Mode"),
                    Column("reference", "Reference"),
                    Column("received_by", "Received by"),
                    Column("amount", "Amount", "money"),
                ],
                [
                    {
                        "receipt_no": p.receipt_no,
                        "customer": p.customer.name,
                        "mode": p.mode_label,
                        "reference": p.reference_no or p.cheque_no,
                        "received_by": str(p.received_by),
                        "amount": p.amount,
                    }
                    for p in payments.select_related("customer", "received_by").order_by("id")
                ],
                totals={"receipt_no": "Total", "amount": collected},
            ),
        ],
    )


# --- 2. Monthly sales -----------------------------------------------------------


def sales_summary(date_from: dt.date, date_to: dt.date, **_: Any) -> Report:
    issued = Invoice.objects.filter(
        status=InvoiceStatus.ISSUED, invoice_date__gte=date_from, invoice_date__lte=date_to
    )
    by_day = {
        row["invoice_date"]: row
        for row in issued.values("invoice_date").annotate(
            count=Count("id"),
            taxable=Sum("taxable_amount"),
            vat=Sum("vat_amount"),
            total=Sum("total"),
        )
    }
    day_rows = []
    for day in _days(date_from, date_to):
        row = by_day.get(day)
        if row is None:
            continue
        day_rows.append(
            {
                "date": day,
                "date_bs": bs_string(day),
                "count": row["count"],
                "taxable": q2(row["taxable"]),
                "vat": q2(row["vat"]),
                "total": q2(row["total"]),
            }
        )
    lines = InvoiceLine.objects.filter(invoice__in=issued, media_type__isnull=False)
    media_rows = [
        {
            "media": row["media_type__name"],
            "sqft": q2(row["sqft"]),
            "billable": q2(row["billable"]),
            "amount": q2(row["amount"]),
        }
        for row in lines.values("media_type__name")
        .annotate(sqft=Sum("sqft"), billable=Sum("billable_sqft"), amount=Sum("amount"))
        .order_by("-amount")
    ]
    addon_amount = _sum(
        InvoiceLine.objects.filter(invoice__in=issued, media_type__isnull=True), "amount"
    )
    total = _sum(issued, "total")
    days_with_sales = len(day_rows)
    return Report(
        slug="monthly-sales",
        title="Sales summary",
        period=period_label(date_from, date_to),
        params={"from": date_from, "to": date_to},
        summary=[
            Metric("Total sales", total),
            Metric("Taxable amount", _sum(issued, "taxable_amount")),
            Metric("VAT", _sum(issued, "vat_amount")),
            Metric("Invoices", issued.count(), "number"),
            Metric(
                "Average per selling day", q2(total / days_with_sales) if days_with_sales else ZERO
            ),
        ],
        tables=[
            Table(
                "Sales by day",
                [
                    Column("date", "Date (AD)", "date"),
                    Column("date_bs", "Date (BS)"),
                    Column("count", "Invoices", "number"),
                    Column("taxable", "Taxable", "money"),
                    Column("vat", "VAT", "money"),
                    Column("total", "Total", "money"),
                ],
                day_rows,
                totals={
                    "date_bs": "Total",
                    "count": issued.count(),
                    "taxable": _sum(issued, "taxable_amount"),
                    "vat": _sum(issued, "vat_amount"),
                    "total": total,
                },
            ),
            Table(
                "Sales by media type",
                [
                    Column("media", "Media"),
                    Column("sqft", "Printed sq ft", "sqft"),
                    Column("billable", "Billed sq ft", "sqft"),
                    Column("amount", "Print amount", "money"),
                ],
                media_rows,
                totals={
                    "media": f"Add-ons (design, framing, etc.): {addon_amount}",
                    "sqft": q2(sum((r["sqft"] for r in media_rows), ZERO)),
                    "billable": q2(sum((r["billable"] for r in media_rows), ZERO)),
                    "amount": q2(sum((r["amount"] for r in media_rows), ZERO)),
                },
            ),
        ],
    )


# --- 3. Pending dues -----------------------------------------------------------


def pending_dues(day: dt.date, **_: Any) -> Report:
    outstanding = outstanding_by_customer(day)
    customers = Customer.objects.in_bulk(list(outstanding))
    rows = []
    for item in sorted(outstanding.values(), key=lambda o: (o.oldest_due_date or day, -o.balance)):
        customer = customers[item.customer_id]
        rows.append(
            {
                "customer": customer.name,
                "phone": customer.phone,
                "oldest_due": item.oldest_due_date,
                "days": (day - item.oldest_due_date).days if item.oldest_due_date else 0,
                "b0": item.buckets["0-30"],
                "b31": item.buckets["31-60"],
                "b61": item.buckets["61-90"],
                "b90": item.buckets["90+"],
                "balance": item.balance,
                "customer_id": customer.pk,
            }
        )
    total = q2(sum((r["balance"] for r in rows), ZERO))
    return Report(
        slug="pending-dues",
        title="Pending dues",
        period=f"As of {period_label(None, day)}",
        params={"date": day},
        summary=[
            Metric("Total due", total),
            Metric("Customers with dues", len(rows), "number"),
            Metric("Over 90 days", q2(sum((r["b90"] for r in rows), ZERO))),
        ],
        tables=[
            Table(
                "Customers with balance due (oldest first)",
                [
                    Column("customer", "Customer"),
                    Column("phone", "Phone"),
                    Column("oldest_due", "Oldest due", "date"),
                    Column("days", "Days", "number"),
                    Column("b0", "0–30 days", "money"),
                    Column("b31", "31–60", "money"),
                    Column("b61", "61–90", "money"),
                    Column("b90", "90+", "money"),
                    Column("balance", "Balance", "money"),
                ],
                rows,
                totals={
                    "customer": "Total",
                    "b0": q2(sum((r["b0"] for r in rows), ZERO)),
                    "b31": q2(sum((r["b31"] for r in rows), ZERO)),
                    "b61": q2(sum((r["b61"] for r in rows), ZERO)),
                    "b90": q2(sum((r["b90"] for r in rows), ZERO)),
                    "balance": total,
                },
                empty_message="No customer has a balance due.",
            )
        ],
    )


# --- 4. Collections -----------------------------------------------------------


def collections(date_from: dt.date, date_to: dt.date, **_: Any) -> Report:
    payments = Payment.objects.filter(
        payment_date__gte=date_from, payment_date__lte=date_to, status=PaymentStatus.VALID
    ).select_related("customer", "received_by", "order")
    voided = Payment.objects.filter(
        payment_date__gte=date_from, payment_date__lte=date_to, status=PaymentStatus.VOID
    )
    total = _sum(payments, "amount")
    staff_rows = [
        {
            "staff": f"{r['received_by__first_name']} {r['received_by__last_name']}".strip()
            or r["received_by__username"],
            "count": r["count"],
            "amount": q2(r["amount"]),
        }
        for r in payments.values(
            "received_by__first_name", "received_by__last_name", "received_by__username"
        )
        .annotate(count=Count("id"), amount=Sum("amount"))
        .order_by("-amount")
    ]
    return Report(
        slug="collections",
        title="Collection report",
        period=period_label(date_from, date_to),
        params={"from": date_from, "to": date_to},
        summary=[
            Metric("Total collected", total),
            Metric("Payments", payments.count(), "number"),
            Metric("Advances", _sum(payments.filter(is_advance=True), "amount")),
            Metric("Voided payments", voided.count(), "number"),
        ],
        tables=[
            Table(
                "By payment mode",
                [
                    Column("mode", "Mode"),
                    Column("count", "Payments", "number"),
                    Column("amount", "Amount", "money"),
                ],
                _mode_rows(payments),
                totals={"mode": "Total", "count": payments.count(), "amount": total},
            ),
            Table(
                "By staff",
                [
                    Column("staff", "Received by"),
                    Column("count", "Payments", "number"),
                    Column("amount", "Amount", "money"),
                ],
                staff_rows,
            ),
            Table(
                "All payments",
                [
                    Column("date", "Date (AD)", "date"),
                    Column("date_bs", "Date (BS)"),
                    Column("receipt_no", "Receipt"),
                    Column("customer", "Customer"),
                    Column("order", "Order"),
                    Column("mode", "Mode"),
                    Column("amount", "Amount", "money"),
                ],
                [
                    {
                        "date": p.payment_date,
                        "date_bs": bs_string(p.payment_date),
                        "receipt_no": p.receipt_no,
                        "customer": p.customer.name,
                        "order": p.order.order_no if p.order else "On account",
                        "mode": p.mode_label,
                        "amount": p.amount,
                    }
                    for p in payments.order_by("payment_date", "id")
                ],
                totals={"receipt_no": "Total", "amount": total},
            ),
        ],
    )


# --- 5. Material consumption vs sales -------------------------------------------


def material_vs_sales(date_from: dt.date, date_to: dt.date, **_: Any) -> Report:
    items = StockItem.objects.filter(kind=StockKind.ROLL_MEDIA).order_by("name")
    lines = InvoiceLine.objects.filter(
        invoice__status=InvoiceStatus.ISSUED,
        invoice__invoice_date__gte=date_from,
        invoice__invoice_date__lte=date_to,
        media_type__material__isnull=False,
    )
    billed = {
        r["media_type__material"]: r
        for r in lines.values("media_type__material").annotate(
            sqft=Sum("sqft"), billable=Sum("billable_sqft")
        )
    }
    movements = StockMovement.objects.filter(
        created_at__date__gte=date_from, created_at__date__lte=date_to, stock_item__in=items
    )
    used: dict[int, dict[str, Decimal]] = defaultdict(lambda: {"used": ZERO, "waste": ZERO})
    for row in (
        movements.filter(movement_type__in=[MovementType.CONSUMPTION, MovementType.WASTAGE])
        .values("stock_item", "movement_type")
        .annotate(qty=Sum(Abs("quantity")))
    ):
        key = "used" if row["movement_type"] == MovementType.CONSUMPTION else "waste"
        used[row["stock_item"]][key] = q2(row["qty"])

    rows = []
    for item in items:
        sold = billed.get(item.pk, {})
        printed = q2(sold.get("sqft") or 0)
        billable = q2(sold.get("billable") or 0)
        u = used[item.pk]["used"]
        w = used[item.pk]["waste"]
        if not any([printed, billable, u, w]):
            continue
        consumed = u + w
        rows.append(
            {
                "material": item.name,
                "billed": billable,
                "printed": printed,
                "used": u,
                "wastage": w,
                "variance": q2(consumed - printed),
                "wastage_pct": q2(w / consumed * 100) if consumed else ZERO,
            }
        )
    totals = {
        k: q2(sum((r[k] for r in rows), ZERO))
        for k in ("billed", "printed", "used", "wastage", "variance")
    }
    consumed_total = totals["used"] + totals["wastage"]
    totals["wastage_pct"] = q2(totals["wastage"] / consumed_total * 100) if consumed_total else ZERO
    totals["material"] = "Total"
    return Report(
        slug="material-vs-sales",
        title="Material consumption vs sales",
        period=period_label(date_from, date_to),
        params={"from": date_from, "to": date_to},
        summary=[
            Metric("Sq ft billed", totals["billed"], "sqft"),
            Metric("Sq ft printed (actual size)", totals["printed"], "sqft"),
            Metric("Sq ft used from rolls", totals["used"], "sqft"),
            Metric("Wastage", totals["wastage"], "sqft"),
            Metric("Wastage %", totals["wastage_pct"], "percent"),
        ],
        tables=[
            Table(
                "By material",
                [
                    Column("material", "Material"),
                    Column("billed", "Billed sq ft", "sqft"),
                    Column("printed", "Printed sq ft", "sqft"),
                    Column("used", "Used sq ft", "sqft"),
                    Column("wastage", "Wastage sq ft", "sqft"),
                    Column("variance", "Used − printed", "sqft"),
                    Column("wastage_pct", "Wastage %", "percent"),
                ],
                rows,
                totals=totals,
            )
        ],
    )


# --- 6. Operator production log ---------------------------------------------------


def operator_log(date_from: dt.date, date_to: dt.date, operator: Any = None, **_: Any) -> Report:
    movements = StockMovement.objects.filter(
        movement_type=MovementType.CONSUMPTION,
        job__isnull=False,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    ).select_related("job__order", "stock_item", "roll", "created_by")
    events = JobStageEvent.objects.filter(
        to_stage=Stage.PRINTING, created_at__date__gte=date_from, created_at__date__lte=date_to
    )
    if operator is not None:
        movements = movements.filter(created_by=operator)
        events = events.filter(created_by=operator)

    per_operator: dict[str, dict[str, Any]] = defaultdict(lambda: {"jobs": set(), "sqft": ZERO})
    for m in movements:
        entry = per_operator[str(m.created_by)]
        entry["jobs"].add(m.job_id)
        entry["sqft"] += -m.quantity
    for e in events.select_related("created_by"):
        per_operator[str(e.created_by)]["jobs"].add(e.job_id)

    summary_rows = [
        {"operator": name, "jobs": len(v["jobs"]), "sqft": q2(v["sqft"])}
        for name, v in sorted(per_operator.items())
    ]
    detail_rows = [
        {
            "date": m.created_at.date(),
            "date_bs": bs_string(m.created_at),
            "job_no": m.job.job_no,
            "order_no": m.job.order.order_no,
            "material": m.stock_item.name,
            "roll": m.roll.code if m.roll else "",
            "sqft": q2(-m.quantity),
            "operator": str(m.created_by),
        }
        for m in movements.order_by("created_at")
    ]
    total_sqft = q2(sum((r["sqft"] for r in detail_rows), ZERO))
    title = "Operator production log" + (f": {operator}" if operator is not None else "")
    return Report(
        slug="operator-log",
        title=title,
        period=period_label(date_from, date_to),
        params={"from": date_from, "to": date_to},
        summary=[
            Metric("Jobs printed", sum(r["jobs"] for r in summary_rows), "number"),
            Metric("Sq ft printed", total_sqft, "sqft"),
        ],
        tables=[
            Table(
                "By operator",
                [
                    Column("operator", "Operator"),
                    Column("jobs", "Jobs", "number"),
                    Column("sqft", "Sq ft used", "sqft"),
                ],
                summary_rows,
            ),
            Table(
                "Material recorded",
                [
                    Column("date", "Date (AD)", "date"),
                    Column("date_bs", "Date (BS)"),
                    Column("job_no", "Job"),
                    Column("order_no", "Order"),
                    Column("material", "Material"),
                    Column("roll", "Roll"),
                    Column("operator", "Operator"),
                    Column("sqft", "Sq ft", "sqft"),
                ],
                detail_rows,
                totals={"job_no": "Total", "sqft": total_sqft},
            ),
        ],
    )


# --- 7. Stock -----------------------------------------------------------


def stock_report(**_: Any) -> Report:
    items = StockItem.objects.filter(is_active=True).order_by("kind", "name")
    item_rows = [
        {
            "item": i.name,
            "kind": i.get_kind_display(),
            "on_hand": i.on_hand,
            "unit": i.get_unit_display(),
            "low_level": i.low_stock_level,
            "status": "Low" if i.is_low else "OK",
        }
        for i in items
    ]
    rolls = (
        Roll.objects.filter(status=RollStatus.ACTIVE)
        .select_related("stock_item")
        .order_by("stock_item__name", "width_ft", "code")
    )
    roll_rows = [
        {
            "code": r.code,
            "item": r.stock_item.name,
            "width": r.width_ft,
            "length": r.length_ft,
            "total": r.total_sqft,
            "remaining": r.remaining_sqft,
            "used_pct": q2((r.total_sqft - r.remaining_sqft) / r.total_sqft * 100)
            if r.total_sqft
            else ZERO,
        }
        for r in rolls
    ]
    low = [row for row in item_rows if row["status"] == "Low"]
    return Report(
        slug="stock",
        title="Stock report",
        period=f"As of {period_label(None, local_today())}",
        summary=[
            Metric("Stock items", len(item_rows), "number"),
            Metric("Low-stock items", len(low), "number"),
            Metric("Active rolls", len(roll_rows), "number"),
            Metric(
                "Roll media on hand (sq ft)",
                q2(sum((r["remaining"] for r in roll_rows), ZERO)),
                "sqft",
            ),
        ],
        tables=[
            Table(
                "Low stock",
                [
                    Column("item", "Item"),
                    Column("on_hand", "On hand", "number"),
                    Column("unit", "Unit"),
                    Column("low_level", "Low level", "number"),
                ],
                low,
                empty_message="Nothing is below its low-stock level.",
            ),
            Table(
                "Current stock",
                [
                    Column("item", "Item"),
                    Column("kind", "Kind"),
                    Column("on_hand", "On hand", "number"),
                    Column("unit", "Unit"),
                    Column("low_level", "Low level", "number"),
                    Column("status", "Status"),
                ],
                item_rows,
            ),
            Table(
                "Roll balance",
                [
                    Column("code", "Roll"),
                    Column("item", "Material"),
                    Column("width", "Width ft", "number"),
                    Column("length", "Length ft", "number"),
                    Column("total", "Total sq ft", "sqft"),
                    Column("remaining", "Remaining sq ft", "sqft"),
                    Column("used_pct", "Used %", "percent"),
                ],
                roll_rows,
            ),
        ],
    )
