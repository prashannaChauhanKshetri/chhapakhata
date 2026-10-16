"""Read-side queries for balances, statements and outstanding dues."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Case, DecimalField, F, Max, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.core.dates import bs_string, local_today
from apps.core.money import ZERO, q2

from .models import LedgerEntry, LedgerEntryType, Payment, PaymentStatus

MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)


def balance_subquery(outer: str = "pk") -> Coalesce:
    """Annotate a Customer queryset with its ledger balance (positive = due)."""
    sub = (
        LedgerEntry.objects.filter(customer=OuterRef(outer))
        .values("customer")
        .annotate(balance=Sum(F("debit") - F("credit")))
        .values("balance")[:1]
    )
    return Coalesce(Subquery(sub, output_field=MONEY_FIELD), Value(ZERO), output_field=MONEY_FIELD)


def paid_subquery(outer: str = "pk") -> Coalesce:
    """Annotate an Order queryset with the total of its valid payments."""
    sub = (
        Payment.objects.filter(order=OuterRef(outer), status=PaymentStatus.VALID)
        .values("order")
        .annotate(paid=Sum("amount"))
        .values("paid")[:1]
    )
    return Coalesce(Subquery(sub, output_field=MONEY_FIELD), Value(ZERO), output_field=MONEY_FIELD)


def customer_balance(customer: Any, as_of: dt.date | None = None) -> Decimal:
    qs = LedgerEntry.objects.filter(customer=customer)
    if as_of is not None:
        qs = qs.filter(entry_date__lte=as_of)
    result = qs.aggregate(balance=Sum(F("debit") - F("credit")))["balance"]
    return q2(result or 0)


def order_paid_amount(order: Any) -> Decimal:
    total = order.payments.filter(status=PaymentStatus.VALID).aggregate(s=Sum("amount"))["s"]
    return q2(total or 0)


def customer_statement(
    customer: Any, date_from: dt.date | None = None, date_to: dt.date | None = None
) -> dict[str, Any]:
    """Opening balance, entries with running balance, and closing balance."""
    date_to = date_to or local_today()
    entries = LedgerEntry.objects.filter(customer=customer, entry_date__lte=date_to)
    opening = ZERO
    if date_from is not None:
        before = entries.filter(entry_date__lt=date_from).aggregate(
            b=Sum(F("debit") - F("credit"))
        )["b"]
        opening = q2(before or 0)
        entries = entries.filter(entry_date__gte=date_from)

    running = opening
    rows = []
    total_debit = total_credit = ZERO
    by_type: dict[str, dict[str, Any]] = {}
    for entry in entries.select_related("invoice", "payment", "order").order_by("entry_date", "id"):
        running = q2(running + entry.debit - entry.credit)
        total_debit += entry.debit
        total_credit += entry.credit
        reference = ""
        if entry.invoice_id:
            reference = entry.invoice.invoice_no
        elif entry.payment_id:
            reference = entry.payment.receipt_no
        elif entry.order_id:
            reference = entry.order.order_no
        kind = by_type.setdefault(
            entry.entry_type,
            {
                "entry_type": entry.entry_type,
                "label": entry.get_entry_type_display(),
                "count": 0,
                "debit": ZERO,
                "credit": ZERO,
            },
        )
        kind["count"] += 1
        kind["debit"] += entry.debit
        kind["credit"] += entry.credit
        rows.append(
            {
                "id": entry.pk,
                "date": entry.entry_date,
                "date_bs": bs_string(entry.entry_date),
                "entry_type": entry.entry_type,
                "entry_type_label": entry.get_entry_type_display(),
                "reference": reference,
                "invoice_id": entry.invoice_id,
                "payment_id": entry.payment_id,
                "order_id": entry.order_id
                or (entry.invoice.order_id if entry.invoice_id else None),
                "narration": entry.narration,
                "debit": entry.debit,
                "credit": entry.credit,
                "balance": running,
            }
        )
    return {
        "customer_id": customer.pk,
        "customer_name": customer.name,
        "date_from": date_from,
        "date_to": date_to,
        "opening_balance": opening,
        "entries": rows,
        "total_debit": q2(total_debit),
        "total_credit": q2(total_credit),
        "closing_balance": running,
        "by_type": list(by_type.values()),
        "aging": _aging_payload(customer.pk, date_to),
    }


def _aging_payload(customer_id: int, as_of: dt.date) -> dict[str, Any] | None:
    outstanding = outstanding_by_customer(as_of, customer_id=customer_id).get(customer_id)
    if outstanding is None:
        return None
    return {
        "oldest_due_date": outstanding.oldest_due_date,
        "buckets": [{"label": k, "amount": v} for k, v in outstanding.buckets.items()],
    }


def _money(expr: Any) -> Coalesce:
    return Coalesce(Sum(expr), Value(ZERO), output_field=MONEY_FIELD)


def ledger_summary(
    date_from: dt.date | None,
    date_to: dt.date,
    *,
    search: str = "",
    balance: str = "",
) -> dict[str, Any]:
    """Opening, billed, received and closing balance for every customer in a period.

    ``balance`` narrows the rows by closing balance: ``due``, ``advance`` or ``settled``.
    """
    from apps.customers.models import Customer

    start = date_from or dt.date.min  # no start date: everything is in the period
    in_period = Q(entry_date__gte=start)
    before = Q(entry_date__lt=start)
    entries = LedgerEntry.objects.filter(entry_date__lte=date_to)
    if search:
        entries = entries.filter(
            Q(customer__name__icontains=search) | Q(customer__phone__icontains=search)
        )
    grouped = (
        entries.values("customer_id")
        .annotate(
            opening=_money(Case(When(before, then=F("debit") - F("credit")), default=Value(ZERO))),
            debit=_money(Case(When(in_period, then=F("debit")), default=Value(ZERO))),
            credit=_money(Case(When(in_period, then=F("credit")), default=Value(ZERO))),
            last_entry=Max("entry_date"),
            last_payment=Max("entry_date", filter=Q(entry_type=LedgerEntryType.PAYMENT)),
        )
        .order_by()
    )
    customers = {
        c.pk: c for c in Customer.objects.filter(pk__in=[g["customer_id"] for g in grouped])
    }
    rows = []
    for g in grouped:
        opening, debit, credit = q2(g["opening"]), q2(g["debit"]), q2(g["credit"])
        if opening == 0 and debit == 0 and credit == 0:
            continue
        closing = q2(opening + debit - credit)
        if balance == "due" and closing <= 0:
            continue
        if balance == "advance" and closing >= 0:
            continue
        if balance == "settled" and closing != 0:
            continue
        customer = customers[g["customer_id"]]
        rows.append(
            {
                "customer_id": customer.pk,
                "customer_name": customer.name,
                "phone": customer.phone,
                "address": customer.address,
                "opening_balance": opening,
                "debit": debit,
                "credit": credit,
                "closing_balance": closing,
                "last_entry_date": g["last_entry"],
                "last_payment_date": g["last_payment"],
            }
        )
    rows.sort(key=lambda r: (-r["closing_balance"], r["customer_name"].lower()))

    def total(key: str) -> Decimal:
        return q2(sum((r[key] for r in rows), ZERO))

    return {
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
        "totals": {
            "customers": len(rows),
            "opening_balance": total("opening_balance"),
            "debit": total("debit"),
            "credit": total("credit"),
            "closing_balance": total("closing_balance"),
            "receivable": q2(
                sum((r["closing_balance"] for r in rows if r["closing_balance"] > 0), ZERO)
            ),
            "advances": q2(
                -sum((r["closing_balance"] for r in rows if r["closing_balance"] < 0), ZERO)
            ),
        },
    }


@dataclass
class Outstanding:
    customer_id: int
    balance: Decimal
    oldest_due_date: dt.date | None
    buckets: dict[str, Decimal]


AGING_BUCKETS = (("0-30", 30), ("31-60", 60), ("61-90", 90), ("90+", None))


def _bucket(days: int) -> str:
    for label, limit in AGING_BUCKETS:
        if limit is None or days <= limit:
            return label
    return AGING_BUCKETS[-1][0]


def outstanding_by_customer(
    as_of: dt.date | None = None, customer_id: int | None = None
) -> dict[int, Outstanding]:
    """Apply credits to the oldest debits first (FIFO) to age each customer's dues."""
    as_of = as_of or local_today()
    debits: dict[int, list[list[Any]]] = defaultdict(list)
    credits: dict[int, Decimal] = defaultdict(lambda: ZERO)
    entries = LedgerEntry.objects.filter(entry_date__lte=as_of)
    if customer_id is not None:
        entries = entries.filter(customer_id=customer_id)
    rows = entries.order_by("customer_id", "entry_date", "id").values_list(
        "customer_id", "entry_date", "debit", "credit"
    )
    for customer_id, entry_date, debit, credit in rows:
        if debit:
            debits[customer_id].append([entry_date, debit])
        if credit:
            credits[customer_id] += credit

    result: dict[int, Outstanding] = {}
    for customer_id in set(debits) | set(credits):
        remaining_credit = credits[customer_id]
        open_items = []
        for entry_date, amount in debits[customer_id]:
            applied = min(amount, remaining_credit)
            remaining_credit -= applied
            if amount - applied > 0:
                open_items.append((entry_date, amount - applied))
        balance = q2(sum((a for _, a in open_items), ZERO) - remaining_credit)
        if balance <= 0:
            continue
        buckets = {label: ZERO for label, _ in AGING_BUCKETS}
        for entry_date, amount in open_items:
            buckets[_bucket((as_of - entry_date).days)] += amount
        result[customer_id] = Outstanding(
            customer_id=customer_id,
            balance=balance,
            oldest_due_date=open_items[0][0] if open_items else None,
            buckets={k: q2(v) for k, v in buckets.items()},
        )
    return result
