"""Find and void payments recorded twice by imports.

A payment can reach ChhapaKhata twice: once with its order (an order slip or
the work log's Payment column) and again from a payments sheet. Each such
sheet receipt is voided, never deleted: it stays on record as "Duplicate of
RCT-…", and the reversal is dated on the payment's own day so every period's
statement is right. A backup is taken first.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.billing.services import duplicate_sheet_payments, void_payment
from apps.core.activity import log_activity
from apps.core.exceptions import BusinessError
from apps.core.permissions import Role

from .erase import CONFIRM_WORD
from .models import BackupStatus, BackupTrigger
from .services import run_backup

SAMPLE = 20


def duplicates_preview() -> dict[str, Any]:
    pairs = duplicate_sheet_payments()
    return {
        "count": len(pairs),
        "total": sum((dup.amount for dup, _ in pairs), Decimal("0")),
        "sample": [
            {
                "receipt_no": dup.receipt_no,
                "original_receipt_no": original.receipt_no,
                "customer": dup.customer.name,
                "payment_date": dup.payment_date,
                "amount": dup.amount,
            }
            for dup, original in pairs[:SAMPLE]
        ],
    }


def void_duplicates(*, user: Any, confirm: str, request: Any = None) -> dict[str, Any]:
    """Back up, then void every duplicate sheet payment. Owner only; type "Confirm"."""
    if getattr(user, "role", None) != Role.OWNER:
        raise BusinessError("Only the owner can void duplicate payments.")
    if (confirm or "").strip().lower() != CONFIRM_WORD.lower():
        raise BusinessError({"confirm": [f"Type {CONFIRM_WORD} to void the duplicates."]})
    pairs = duplicate_sheet_payments()
    if not pairs:
        return {"voided": 0, "total": Decimal("0"), "backup_file": ""}
    backup = run_backup(BackupTrigger.MANUAL, user=user)
    if backup.status != BackupStatus.SUCCESS:
        raise BusinessError("The safety backup failed, so nothing was changed. Try again.")
    total = Decimal("0")
    with transaction.atomic():
        for dup, original in pairs:
            void_payment(
                payment=dup,
                user=user,
                reason=f"Duplicate of {original.receipt_no} (already recorded with the order)",
                reverse_on=dup.payment_date,
                request=request,
            )
            total += dup.amount
        log_activity(
            user,
            "payments.duplicates_voided",
            None,
            message=f"{len(pairs)} duplicate payments voided, Rs {total}",
            metadata={"count": len(pairs), "total": str(total), "backup": backup.pk},
            request=request,
        )
    return {"voided": len(pairs), "total": total, "backup_file": backup.database_file}
