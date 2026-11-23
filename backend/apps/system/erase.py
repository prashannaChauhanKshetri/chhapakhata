"""Erase one business's data, to start entering again from a clean slate.

Kept: staff accounts, shop settings (name, PAN, logo, numbering patterns), the
activity log and backups. Erased: customers, orders, jobs, invoices,
payments, the ledger, purchases, suppliers and stock, and optionally the
rate card and the stock item list. Bill numbering starts again from 1.

A full backup is taken first; if it fails, nothing is erased. Only the
current business is touched: every delete filters on it, and row-level
security limits the connection to it as well.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.apps import apps
from django.db import transaction

from apps.core.activity import log_activity
from apps.core.exceptions import BusinessError
from apps.core.permissions import Role
from apps.tenancy.context import require_business_id

from .models import BackupStatus, BackupTrigger
from .services import run_backup

CONFIRM_WORD = "Confirm"


@dataclass(frozen=True)
class Table:
    label: str  # app_label.Model
    title: str  # shown to the owner; empty for tables counted under another title
    catalog: bool = False  # rate card and stock item list (can be kept)


# Children before parents, so every row's references are gone before it is.
TABLES = [
    # Advances point at salary payments (carried amounts), so they go first.
    Table("staff.StaffAdvance", "Salary advances"),
    Table("staff.SalaryPayment", "Salary payments"),
    Table("staff.Attendance", ""),
    Table("staff.Staff", "Staff"),
    Table("staff.HistoricalStaff", ""),
    Table("billing.LedgerEntry", "Ledger entries"),
    Table("billing.Payment", "Payments"),
    Table("billing.InvoiceLine", ""),
    Table("billing.InvoiceOrder", ""),
    Table("billing.Invoice", "Invoices"),
    Table("inventory.StockMovement", "Stock movements"),
    Table("production.JobStageEvent", ""),
    Table("production.Job", "Jobs"),
    Table("orders.OrderItemAddOn", ""),
    Table("orders.OrderItem", ""),
    Table("orders.Order", "Orders"),
    Table("inventory.Roll", "Rolls"),
    Table("inventory.PurchaseLine", ""),
    Table("inventory.Purchase", "Purchases"),
    Table("inventory.Supplier", "Suppliers"),
    Table("customers.Customer", "Customers"),
    Table("catalog.AddOn", "Add-ons", catalog=True),
    Table("catalog.MediaType", "Rate-card items", catalog=True),
    Table("inventory.StockItem", "Stock items", catalog=True),
    Table("core.DocumentSequence", ""),
    # Change history of the erased records.
    Table("customers.HistoricalCustomer", ""),
    Table("orders.HistoricalOrder", ""),
    Table("catalog.HistoricalAddOn", "", catalog=True),
    Table("catalog.HistoricalMediaType", "", catalog=True),
]


def _rows(table: Table, business_id: int):
    model = apps.get_model(table.label)
    return model._base_manager.filter(business_id=business_id)


def erase_preview() -> list[dict[str, Any]]:
    """What would be erased, as ``[{title, count, catalog}]`` for the confirmation window."""
    business_id = require_business_id()
    return [
        {"title": t.title, "count": _rows(t, business_id).count(), "catalog": t.catalog}
        for t in TABLES
        if t.title
    ]


def erase_business_data(
    *, user: Any, confirm: str, keep_catalog: bool = False, request: Any = None
) -> dict[str, Any]:
    """Back up, then erase the current business's data.

    Owner only, and ``confirm`` must be the word "Confirm".
    """
    if getattr(user, "role", None) != Role.OWNER:
        raise BusinessError("Only the owner can erase the shop's data.")
    if (confirm or "").strip().lower() != CONFIRM_WORD.lower():
        raise BusinessError({"confirm": [f"Type {CONFIRM_WORD} to erase the data."]})
    business_id = require_business_id()

    backup = run_backup(BackupTrigger.MANUAL, user=user)
    if backup.status != BackupStatus.SUCCESS:
        raise BusinessError(
            "The safety backup failed, so nothing was erased. "
            "Check Settings → Backups & export and try again."
        )

    erased: dict[str, int] = {}
    with transaction.atomic():
        for table in TABLES:
            if keep_catalog and table.catalog:
                continue
            rows = _rows(table, business_id)
            # One DELETE per table: no per-row signals (and no history rows for the deletes).
            count = rows._raw_delete(rows.db)
            if table.title:
                erased[table.title] = count
        if keep_catalog:
            # The movements behind the quantities are gone, so the items start empty.
            _rows(Table("inventory.StockItem", "", True), business_id).update(on_hand=0)
        summary = ", ".join(f"{n} {title.lower()}" for title, n in erased.items() if n)
        log_activity(
            user,
            "data.erased",
            None,
            message=(summary or "Nothing to erase")[:255],
            metadata={"erased": erased, "keep_catalog": keep_catalog, "backup": backup.pk},
            request=request,
        )
    return {"erased": erased, "keep_catalog": keep_catalog, "backup_file": backup.database_file}
