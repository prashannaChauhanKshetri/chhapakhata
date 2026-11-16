"""Importing payments received from a sheet, after the opening balances."""

import datetime as dt
import io
from decimal import Decimal as D

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.billing import services as billing
from apps.billing.models import Payment
from apps.billing.selectors import customer_balance
from apps.core.permissions import Role
from apps.customers.models import Customer
from apps.system.go_live import run_import
from apps.tenancy.context import use_business
from apps.tenancy.models import Business
from conftest import make_user

pytestmark = pytest.mark.django_db

SHRAWAN_1 = dt.date(2026, 7, 17)  # 2083.04.01 BS
UNDATED_ON = dt.date(2026, 7, 20)  # chosen in the form for rows without a date

# OM Traders' payment sheet (screenshot, 16 Nov 2026): undated rows on top,
# Mode empty, the way of payment written in the remark.
OM_PAYMENTS = [
    ["DATE", "CUSTOMER", "AMOUNT", "MODE", "REMARK"],
    [None, "Prem Sir Yog Samiti", 250, "—", "Esewa"],
    [None, "Ather", "5,000.00", "—", "Esewa"],
    [None, "Rara IT Hub", "5,300.00", "—", "QR: Om Trade"],
    [None, "Sanjeevani College of Medical Sciences", "1,78,098.00", "—", "ChequeM Mahalaxmi"],
    [None, "Nita Films", "88,448.00", "—", "Krishna Dai ko chadako"],
    [None, "Digital Nepal", "36,000.00", "—", "Cash Received"],
    ["2083.04.01", "Aayan Digital", 820, "—", "Bill payment"],
    ["2083.04.01", "Prakash Digital", 960, "—", "Bill payment"],
    ["2083.04.02", "Denisha Photo Studio", 450, "—", "Bill payment"],
]


def _xlsx(rows):
    wb = Workbook()
    for row in rows:
        wb.active.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


@pytest.fixture
def om_customers(owner):
    names = {row[1] for row in OM_PAYMENTS[1:]}
    for name in names:
        customer = Customer.objects.create(name=name)
        billing.set_opening_balance(customer=customer, amount=D("200000"), user=owner)
    return names


def _run(owner, rows, **kwargs):
    kwargs.setdefault("as_of", UNDATED_ON)
    return run_import("payments", _xlsx(rows), name="payments.xlsx", user=owner, **kwargs)


def test_the_clients_payment_sheet(owner, om_customers):
    result = _run(owner, OM_PAYMENTS, dry_run=False)
    assert result.errors == [] and result.created == 9
    assert result.summary["amount"] == "315326"

    def payment(name):
        return Payment.objects.get(customer__name=name)

    assert (payment("Ather").mode, payment("Ather").wallet) == ("wallet", "esewa")
    assert payment("Rara IT Hub").wallet == "other_qr"
    assert payment("Sanjeevani College of Medical Sciences").mode == "cheque"
    assert payment("Sanjeevani College of Medical Sciences").amount == D("178098.00")
    assert payment("Digital Nepal").mode == "cash" and payment("Nita Films").mode == "cash"
    assert payment("Nita Films").notes == "Krishna Dai ko chadako"
    assert payment("Ather").payment_date == UNDATED_ON
    assert payment("Aayan Digital").payment_date == SHRAWAN_1
    assert sum("No date" in w.message for w in result.warnings) == 6

    # Opening balance minus the payment, received on account.
    aayan = Customer.objects.get(name="Aayan Digital")
    assert customer_balance(aayan) == D("199180.00")

    again = _run(owner, OM_PAYMENTS, dry_run=False)
    assert again.created == 0 and again.skipped == 9
    assert Payment.objects.count() == 9


def test_a_longer_sheet_adds_only_the_new_rows(owner, om_customers):
    _run(owner, OM_PAYMENTS, dry_run=False)
    longer = [*OM_PAYMENTS, ["2083.04.03", "Aayan Digital", 820, "", "Bill payment"]]
    result = _run(owner, longer, dry_run=False)
    assert (result.created, result.skipped) == (1, 9)


def test_another_layout_with_merged_dates_and_totals(owner):
    Customer.objects.create(name="Ram Traders")
    Customer.objects.create(name="Sita Stores", phone="9800000001")
    Customer.objects.create(name="Sita Stores", phone="9800000002")
    rows = [
        ["Collections register 2083"],
        ["Miti", "Party Name", "Mob. No.", "Received (Rs.)", "Narration", "Txn No."],
        ["2083.04.05", "ram traders", "", "Rs. 1,500/-", "khalti", "KH123"],
        [None, "Sita Stores", "9800000002", "700", "bank deposit", ""],
        ["", "Grand Total", "", "2,200", "", ""],
    ]
    result = _run(owner, rows, dry_run=False)
    assert result.errors == [], result.errors
    ram = Payment.objects.get(customer__name="Ram Traders")
    assert (ram.wallet, ram.reference_no, ram.amount) == ("khalti", "KH123", D("1500.00"))
    sita = Payment.objects.get(customer__phone="9800000002")
    assert sita.payment_date == ram.payment_date and sita.mode == "bank"
    assert "used the date from the row above" in result.warnings[0].message


def test_unknown_or_ambiguous_customers_are_problems(owner, om_customers):
    Customer.objects.create(name="Twin Prints")
    Customer.objects.create(name="Twin Prints")
    rows = [
        ["Date", "Customer", "Amount"],
        ["2083.04.01", "Sanjivani College of Medical Science", 100],
        ["2083.04.01", "Twin Prints", 100],
        ["2083.04.01", "Aayan Digital", -50],
    ]
    result = _run(owner, rows, dry_run=False)
    messages = [e.message for e in result.errors]
    assert "Did you mean 'Sanjeevani College of Medical Sciences'?" in messages[0]
    assert "add a Phone column" in messages[1]
    assert "negative" in messages[2]
    assert result.dry_run is True and Payment.objects.count() == 0


def test_another_business_customers_are_never_matched(owner):
    other = Business.objects.create(name="Sharma Prints", slug="sharma-prints")
    with use_business(other):
        make_user("ram", Role.OWNER)
        Customer.objects.create(name="Only There")
    result = _run(owner, [["Date", "Customer", "Amount"], ["2083.04.01", "Only There", 100]])
    assert "is not in the system" in result.errors[0].message


def test_api_and_sample_sheet(api, owner, desk, om_customers):
    url = "/api/v1/system/import/payments/"
    upload = SimpleUploadedFile("payments.xlsx", _xlsx(OM_PAYMENTS))
    assert api(desk).post(url, {"file": upload}).status_code == 403
    checked = (
        api(owner)
        .post(
            url, {"file": SimpleUploadedFile("p.xlsx", _xlsx(OM_PAYMENTS)), "as_of": "2026-07-20"}
        )
        .json()
    )
    assert checked["dry_run"] is True and checked["created"] == 9
    assert Payment.objects.count() == 0
    assert api(owner).get(f"{url}template/").status_code == 200


def test_payments_dated_inside_the_opening_balance_are_not_added(owner, om_customers):
    """Opening balances (fixture) are dated 16 Jul 2026, the end of last fiscal year."""
    rows = [
        ["Date", "Customer", "Amount", "Remark"],
        ["2083.03.20", "Aayan Digital", 820, "Paid last year"],
        ["2083.04.05", "Aayan Digital", 500, "Paid this year"],
    ]
    result = _run(owner, rows, dry_run=False)
    assert (result.created, result.skipped) == (1, 1)
    assert "already counted in it" in result.warnings[0].message
    assert customer_balance(Customer.objects.get(name="Aayan Digital")) == D("199500.00")
