"""The balance a customer carried in from the previous year: set it, correct it, see why."""

import datetime as dt
import io
from decimal import Decimal as D

import pytest
from freezegun import freeze_time
from openpyxl import Workbook

from apps.billing import services
from apps.billing.models import LedgerEntryType
from apps.billing.selectors import customer_balance, customer_statement
from apps.core.exceptions import BusinessError
from apps.customers.models import Customer
from apps.system.go_live import run_import

pytestmark = pytest.mark.django_db

LAST_YEAR_END = dt.date(2026, 7, 16)  # 31 Asar 2083: FY 2083/84 starts 1 Shrawan = 17 Jul 2026


@pytest.fixture(autouse=True)
def _today():
    with freeze_time("2026-10-16 10:00"):
        yield


def test_previous_year_end_is_the_day_before_shrawan_1():
    assert services.previous_year_end() == LAST_YEAR_END
    assert services.previous_year_end(dt.date(2026, 7, 10)) == dt.date(2025, 7, 16)


def test_first_opening_balance_is_last_year_closing(customer, owner, desk, make_order):
    services.set_opening_balance(customer=customer, amount=D("4500"), user=owner)
    entry = customer.ledger_entries.get()
    assert (entry.entry_type, entry.entry_date, entry.debit) == (
        LedgerEntryType.OPENING,
        LAST_YEAR_END,
        D("4500.00"),
    )
    # This year's statement opens with it instead of listing it as a charge.
    statement = customer_statement(customer, dt.date(2026, 7, 17), dt.date(2026, 10, 16))
    assert statement["opening_balance"] == D("4500.00")
    assert statement["entries"] == []


def test_correction_needs_a_reason_and_keeps_the_history(customer, owner):
    services.set_opening_balance(
        customer=customer, amount=D("4500"), user=owner, as_of=dt.date(2026, 7, 10)
    )
    with pytest.raises(BusinessError, match="reason"):
        services.set_opening_balance(customer=customer, amount=D("4000"), user=owner)
    services.set_opening_balance(
        customer=customer, amount=D("4000"), user=owner, reason="Old khata showed 4,000"
    )
    services.set_opening_balance(
        customer=customer, amount=D("-250"), user=owner, reason="He had paid an advance"
    )
    entries = list(services.opening_entries(customer))
    assert [(e.debit, e.credit) for e in entries] == [
        (D("4500.00"), D("0.00")),
        (D("0.00"), D("500.00")),
        (D("0.00"), D("4250.00")),
    ]
    assert {e.entry_date for e in entries} == {dt.date(2026, 7, 10)}
    assert entries[2].narration == (
        "Opening balance changed from Rs. 4,000.00 due to Rs. 250.00 advance: "
        "He had paid an advance"
    )
    assert customer_balance(customer) == D("-250.00")


def test_the_same_figure_a_future_date_or_a_moved_date_are_refused(customer, owner):
    with pytest.raises(BusinessError, match="future"):
        services.set_opening_balance(
            customer=customer, amount=D("100"), user=owner, as_of=dt.date(2026, 11, 1)
        )
    with pytest.raises(BusinessError, match="amount carried in"):
        services.set_opening_balance(customer=customer, amount=D("0"), user=owner)
    services.set_opening_balance(customer=customer, amount=D("100"), user=owner)
    with pytest.raises(BusinessError, match=r"already Rs\. 100\.00 due"):
        services.set_opening_balance(
            customer=customer, amount=D("100"), user=owner, reason="Same again"
        )
    with pytest.raises(BusinessError, match="keeps the date"):
        services.set_opening_balance(
            customer=customer,
            amount=D("200"),
            user=owner,
            reason="Wrong year",
            as_of=dt.date(2025, 7, 16),
        )
    # Clearing it to zero is a correction too.
    services.set_opening_balance(customer=customer, amount=D("0"), user=owner, reason="No dues")
    assert customer_balance(customer) == D("0.00")


def test_api_shows_history_and_only_the_owner_changes_it(api, customer, owner, desk):
    url = f"/api/v1/customers/{customer.pk}/opening-balance/"
    empty = api(owner).get(url).json()
    assert empty["amount"] == "0.00" and empty["date"] is None
    assert empty["default_date"] == "2026-07-16" and empty["default_date_bs"] == "2083-03-32"

    assert api(desk).post(url, {"amount": "900"}, format="json").status_code == 403
    first = api(owner).post(url, {"amount": "900"}, format="json")
    assert first.status_code == 200, first.content
    assert first.json()["amount"] == "900.00" and first.json()["date"] == "2026-07-16"

    no_reason = api(owner).post(url, {"amount": "800"}, format="json")
    assert no_reason.status_code == 400
    fixed = api(owner).post(url, {"amount": "800", "reason": "Counted again"}, format="json").json()
    assert fixed["amount"] == "800.00" and len(fixed["entries"]) == 2
    assert fixed["entries"][1]["created_by"] == owner.get_full_name()
    assert api(desk).get(url).status_code == 200


def test_new_customer_with_last_years_balance(api, owner):
    response = api(owner).post(
        "/api/v1/customers/",
        {"name": "Bheri Traders", "opening_balance": "1200"},
        format="json",
    )
    assert response.status_code == 201, response.content
    customer = Customer.objects.get(name="Bheri Traders")
    assert customer.ledger_entries.get().entry_date == LAST_YEAR_END
    dated = api(owner).post(
        "/api/v1/customers/",
        {"name": "Rapti Stores", "opening_balance": "-300", "opening_date": "2026-08-01"},
        format="json",
    )
    assert dated.status_code == 201
    entry = Customer.objects.get(name="Rapti Stores").ledger_entries.get()
    assert (entry.entry_date, entry.credit) == (dt.date(2026, 8, 1), D("300.00"))


def _sheet(rows):
    wb = Workbook()
    for row in rows:
        wb.active.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_a_corrected_ledger_sheet_fixes_opening_balances(owner):
    first = [["Name", "Phone", "Balance"], ["Hotel Kalpana", "9858020005", 4500]]
    run_import("customers", _sheet(first), name="ledger.xlsx", user=owner, dry_run=False)
    kalpana = Customer.objects.get(name="Hotel Kalpana")
    assert kalpana.ledger_entries.get().entry_date == LAST_YEAR_END

    fixed = [["Name", "Phone", "Balance"], ["Hotel Kalpana", "9858020005", 4200]]
    result = run_import(
        "customers", _sheet(fixed), name="ledger-v2.xlsx", user=owner, dry_run=False
    )
    assert result.updated == 1
    assert "changed from 4500 to 4200" in result.warnings[0].message
    assert customer_balance(kalpana) == D("4200.00")
    assert "ledger-v2.xlsx" in services.opening_entries(kalpana).last().narration
