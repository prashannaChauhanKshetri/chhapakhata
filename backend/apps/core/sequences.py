"""Document numbering (orders, jobs, invoices, receipts, purchases, rolls).

Numbers are allocated inside the caller's transaction with a row lock, so two
counters can never hand out the same number and a rolled-back transaction
never leaves a gap. Invoices and receipts restart every Nepal fiscal year.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.db import IntegrityError, models, transaction

from .dates import fiscal_year_for, local_today
from .models import DocumentSequence, ShopSettings


class DocType(models.TextChoices):
    ORDER = "order", "Order"
    JOB = "job", "Job"
    INVOICE = "invoice", "Invoice"
    RECEIPT = "receipt", "Receipt"
    PURCHASE = "purchase", "Purchase"
    ROLL = "roll", "Roll"


FISCAL_YEAR_SCOPED = {DocType.INVOICE, DocType.RECEIPT}
START_AT = {DocType.JOB: 1001}
FIXED_PATTERNS = {DocType.ROLL: "R-{n:04d}"}
PATTERN_FIELD = {
    DocType.ORDER: "order_number_pattern",
    DocType.JOB: "job_number_pattern",
    DocType.INVOICE: "invoice_number_pattern",
    DocType.RECEIPT: "receipt_number_pattern",
    DocType.PURCHASE: "purchase_number_pattern",
}


@dataclass(frozen=True)
class AllocatedNumber:
    number: str
    sequence: int
    fiscal_year: str


def _lock_sequence(doc_type: str, scope: str) -> DocumentSequence:
    start = START_AT.get(DocType(doc_type), 1)
    for _ in range(2):
        try:
            with transaction.atomic():
                seq, _created = DocumentSequence.objects.select_for_update().get_or_create(
                    doc_type=doc_type, fiscal_year=scope, defaults={"last_number": start - 1}
                )
                return seq
        except IntegrityError:
            # Another transaction created the row first; retry and lock it.
            continue
    return DocumentSequence.objects.select_for_update().get(doc_type=doc_type, fiscal_year=scope)


def next_number(doc_type: str, on_date: dt.date | None = None) -> AllocatedNumber:
    """Allocate the next number. Must be called inside ``transaction.atomic()``."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("next_number() must run inside transaction.atomic()")
    doc = DocType(doc_type)
    fiscal_year = fiscal_year_for(on_date or local_today())
    scope = fiscal_year if doc in FISCAL_YEAR_SCOPED else ""

    seq = _lock_sequence(doc, scope)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])

    if doc in FIXED_PATTERNS:
        pattern = FIXED_PATTERNS[doc]
    else:
        pattern = getattr(ShopSettings.load(), PATTERN_FIELD[doc])
    number = pattern.format(n=seq.last_number, fy=fiscal_year)
    return AllocatedNumber(number=number, sequence=seq.last_number, fiscal_year=fiscal_year)
