"""A payment recorded with its order and again from a payments sheet is counted once."""

import datetime as dt
import io
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from apps.billing import services as billing
from apps.billing.models import LedgerEntryType, Payment, PaymentStatus
from apps.billing.selectors import customer_balance, customer_statement
from apps.core.exceptions import BusinessError
from apps.customers.models import Customer
from apps.system import duplicates
from apps.system.go_live import run_import
from apps.system.models import BackupStatus
from apps.system.work_log import import_work_log

pytestmark = pytest.mark.django_db

SHRAWAN_32 = dt.date(2026, 8, 17)  # 2083-05-01 BS, as in the client's screenshot

WORK_LOG = [
    [
        "Date",
        "Particular",
        "Address",
        "Items",
        "Height",
        "Width",
        "Qty",
        "SQFT",
        "Rate",
        "Amount",
        "Details",
        "Payment S",
        "Payment M",
        "Discount",
        "Balance",
    ],
    [
        "2083.05.01",
        "Light Board Client",
        "Nepalgunj",
        "Light Board",
        None,
        None,
        1,
        0,
        278951.8,
        278951.8,
        "",
        150000,
        "",
        0,
        128951.8,
    ],
]
PAYMENTS = [
    ["DATE", "CUSTOMER", "AMOUNT", "MODE", "REMARK"],
    ["2083.05.01", "Light Board Client", "1,50,000.00", "—", "Cash Received"],
]


def _xlsx(rows):
    wb = Workbook()
    for row in rows:
        wb.active.append(row)
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def _work_log(owner):
    return import_work_log(_xlsx(WORK_LOG), name="work.xlsx", user=owner, dry_run=False)


def _payments(owner, rows=PAYMENTS):
    return run_import(
        "payments", _xlsx(rows).getvalue(), name="pay.xlsx", user=owner, dry_run=False
    )


def test_payments_sheet_after_the_work_log_adds_nothing_twice(owner):
    _work_log(owner)
    client = Customer.objects.get(name="Light Board Client")
    assert customer_balance(client) == D("128951.80")

    result = _payments(owner)
    assert (result.created, result.skipped) == (0, 1)
    assert "already recorded as RCT-" in result.warnings[0].message
    assert customer_balance(client) == D("128951.80")  # not 21,048.20 Cr


def test_work_log_after_the_payments_sheet_adds_nothing_twice(owner):
    client = Customer.objects.create(name="Light Board Client")
    _payments(owner)
    result = _work_log(owner)
    assert "already recorded" in " ".join(w.message for w in result.warnings)
    assert Payment.objects.filter(customer=client).count() == 1
    assert customer_balance(client) == D("128951.80")


def test_two_real_payments_of_the_same_amount_are_both_kept(owner):
    _work_log(owner)
    rows = [*PAYMENTS, ["2083.05.01", "Light Board Client", "1,50,000.00", "", "Second cheque"]]
    result = _payments(owner, rows)
    assert (result.created, result.skipped) == (1, 1)


@pytest.fixture
def backups(monkeypatch):
    monkeypatch.setattr(
        duplicates,
        "run_backup",
        lambda trigger, user=None: SimpleNamespace(
            status=BackupStatus.SUCCESS, database_file="/b.dump", pk=1
        ),
    )


@pytest.fixture
def recorded_twice(owner):
    """What the earlier import made: the order's payment and a sheet copy of it."""
    _work_log(owner)
    client = Customer.objects.get(name="Light Board Client")
    billing.record_imported_payment(
        user=owner,
        customer=client,
        amount=D("150000"),
        mode="cash",
        payment_date=SHRAWAN_32,
        notes="Cash Received",
        import_ref="sheet-row-1",
    )
    return client


def test_cleanup_voids_the_sheet_copy_on_its_own_date(backups, recorded_twice, owner):
    assert customer_balance(recorded_twice) == D("-21048.20")  # the client's screenshot
    preview = duplicates.duplicates_preview()
    assert preview["count"] == 1 and preview["total"] == D("150000.00")

    result = duplicates.void_duplicates(user=owner, confirm="Confirm")
    assert result["voided"] == 1
    assert customer_balance(recorded_twice) == D("128951.80")
    copy = Payment.objects.get(import_ref="sheet-row-1")
    assert copy.status == PaymentStatus.VOID and copy.void_reason.startswith("Duplicate of RCT-")
    reversal = copy.ledger_entries.get(entry_type=LedgerEntryType.PAYMENT_VOID)
    assert reversal.entry_date == SHRAWAN_32
    month = customer_statement(recorded_twice, dt.date(2026, 8, 17), dt.date(2026, 9, 16))
    assert month["closing_balance"] == D("128951.80")
    assert duplicates.duplicates_preview()["count"] == 0
    # Uploading the payments sheet again does not bring it back.
    assert _payments(owner).created == 0


def test_cleanup_needs_the_owner_and_the_word(backups, recorded_twice, owner, desk):
    with pytest.raises(BusinessError):
        duplicates.void_duplicates(user=owner, confirm="yes")
    with pytest.raises(BusinessError, match="Only the owner"):
        duplicates.void_duplicates(user=desk, confirm="Confirm")
    assert duplicates.duplicates_preview()["count"] == 1


def test_api(api, backups, recorded_twice, owner, desk):
    url = "/api/v1/system/duplicate-payments/"
    assert api(desk).get(url).status_code == 403
    found = api(owner).get(url).json()
    assert found["count"] == 1 and found["sample"][0]["customer"] == "Light Board Client"
    assert api(owner).post(url, {"confirm": "no"}, format="json").status_code == 400
    done = api(owner).post(url, {"confirm": "Confirm"}, format="json").json()
    assert done["voided"] == 1
