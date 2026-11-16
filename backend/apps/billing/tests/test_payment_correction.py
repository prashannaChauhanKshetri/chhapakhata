"""Correcting a payment entered wrongly: the wrong receipt is voided and the right
one recorded, together, so nothing is overwritten and balances stay right."""

import datetime as dt
import io
from decimal import Decimal as D

import pytest
from freezegun import freeze_time
from openpyxl import Workbook

from apps.billing import services
from apps.billing.models import LedgerEntryType, Payment, PaymentStatus
from apps.billing.selectors import customer_balance, customer_statement
from apps.core.exceptions import BusinessError
from apps.customers.models import Customer
from apps.system.go_live import run_import

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _today():
    with freeze_time("2026-10-16 10:00"):
        yield


@pytest.fixture
def paid(customer, owner, desk):
    services.set_opening_balance(customer=customer, amount=D("5000"), user=owner)
    return services.receive_payment(
        user=desk,
        customer=customer,
        amount="1500",
        mode="cash",
        payment_date=dt.date(2026, 8, 20),
    )


def test_wrong_amount_is_corrected_with_both_receipts_kept(paid, customer, owner, desk):
    fixed = services.correct_payment(
        payment=paid, user=owner, reason="Typed 1500, it was 1000", amount=D("1000")
    )
    paid.refresh_from_db()
    assert paid.status == PaymentStatus.VOID
    assert paid.void_reason == f"Corrected by {fixed.receipt_no}: Typed 1500, it was 1000"
    assert (fixed.amount, fixed.payment_date, fixed.mode) == (
        D("1000.00"),
        paid.payment_date,
        "cash",
    )
    assert fixed.received_by == desk  # who took the money stays the same
    assert customer_balance(customer) == D("4000.00")
    void = customer.ledger_entries.get(entry_type=LedgerEntryType.PAYMENT_VOID)
    assert void.entry_date == dt.date(2026, 8, 20)  # undone on its own date


def test_that_months_statement_shows_the_corrected_figure(paid, customer, owner):
    services.correct_payment(payment=paid, user=owner, reason="Was 1000", amount=D("1000"))
    august = customer_statement(customer, dt.date(2026, 8, 1), dt.date(2026, 8, 31))
    assert august["closing_balance"] == D("4000.00")


def test_payment_moved_to_the_right_customer(paid, customer, owner):
    right = Customer.objects.create(name="Right Customer")
    fixed = services.correct_payment(
        payment=paid, user=owner, reason="Wrong customer chosen", customer=right
    )
    assert fixed.customer == right and fixed.order is None
    assert customer_balance(customer) == D("5000.00")
    assert customer_balance(right) == D("-1500.00")


def test_mode_and_date_can_change(paid, owner):
    fixed = services.correct_payment(
        payment=paid,
        user=owner,
        reason="It came by eSewa",
        mode="wallet",
        wallet="esewa",
        reference_no="ES123",
        payment_date=dt.date(2026, 8, 18),
    )
    assert (fixed.mode, fixed.wallet, fixed.reference_no) == ("wallet", "esewa", "ES123")
    assert fixed.payment_date == dt.date(2026, 8, 18)


def test_refusals(paid, owner):
    with pytest.raises(BusinessError, match="reason"):
        services.correct_payment(payment=paid, user=owner, reason="", amount=D("1"))
    with pytest.raises(BusinessError, match="Nothing was changed"):
        services.correct_payment(payment=paid, user=owner, reason="No change", amount=D("1500"))
    with pytest.raises(BusinessError, match="future"):
        services.correct_payment(
            payment=paid, user=owner, reason="Wrong day", payment_date=dt.date(2026, 12, 1)
        )
    with pytest.raises(BusinessError, match="wallet"):
        services.correct_payment(payment=paid, user=owner, reason="It was QR", mode="wallet")
    services.void_payment(payment=paid, user=owner, reason="Bounced cheque")
    with pytest.raises(BusinessError, match="void"):
        services.correct_payment(payment=paid, user=owner, reason="Too late", amount=D("10"))
    assert Payment.objects.count() == 1


def _sheet(rows):
    wb = Workbook()
    for row in rows:
        wb.active.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_an_imported_payment_is_corrected_and_not_imported_again(customer, owner):
    rows = [["Date", "Customer", "Amount", "Remark"], ["2083.04.10", customer.name, 900, "Cheque"]]
    run_import("payments", _sheet(rows), name="p.xlsx", user=owner, dry_run=False)
    imported = Payment.objects.get()
    assert imported.mode == "cheque" and imported.cheque_no == ""
    # No cheque number on record, yet the amount can be corrected.
    services.correct_payment(payment=imported, user=owner, reason="Was 990", amount=D("990"))
    again = run_import("payments", _sheet(rows), name="p.xlsx", user=owner, dry_run=False)
    assert again.created == 0
    assert Payment.objects.filter(status=PaymentStatus.VALID).get().amount == D("990.00")


def test_api_owner_only(api, paid, owner, desk):
    url = f"/api/v1/payments/{paid.pk}/correct/"
    body = {"amount": "1000", "reason": "Typed wrongly"}
    assert api(desk).post(url, body, format="json").status_code == 403
    assert api(owner).post(url, {"amount": "1000"}, format="json").status_code == 400
    response = api(owner).post(url, body, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["amount"] == "1000.00" and response.json()["status"] == "valid"
    on_account = api(owner).post(
        f"/api/v1/payments/{response.json()['id']}/correct/",
        {"order": None, "notes": "Towards old dues", "reason": "Note added"},
        format="json",
    )
    assert on_account.status_code == 200 and on_account.json()["notes"] == "Towards old dues"
