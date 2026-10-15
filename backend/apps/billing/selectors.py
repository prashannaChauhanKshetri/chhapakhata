"""Read-side queries for balances, statements and outstanding dues."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.dates import bs_string, local_today
from apps.core.money import ZERO, q2

from .models import LedgerEntry, Payment, PaymentStatus

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
    for entry in entries.select_related("invoice", "payment").order_by("entry_date", "id"):
        running = q2(running + entry.debit - entry.credit)
        total_debit += entry.debit
        total_credit += entry.credit
        reference = ""
        if entry.invoice_id:
            reference = entry.invoice.invoice_no
        elif entry.payment_id:
            reference = entry.payment.receipt_no
        rows.append(
            {
                "id": entry.pk,
                "date": entry.entry_date,
                "date_bs": bs_string(entry.entry_date),
                "entry_type": entry.entry_type,
                "entry_type_label": entry.get_entry_type_display(),
                "reference": reference,
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


def outstanding_by_customer(as_of: dt.date | None = None) -> dict[int, Outstanding]:
    """Apply credits to the oldest debits first (FIFO) to age each customer's dues."""
    as_of = as_of or local_today()
    debits: dict[int, list[list[Any]]] = defaultdict(list)
    credits: dict[int, Decimal] = defaultdict(lambda: ZERO)
    rows = (
        LedgerEntry.objects.filter(entry_date__lte=as_of)
        .order_by("customer_id", "entry_date", "id")
        .values_list("customer_id", "entry_date", "debit", "credit")
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
