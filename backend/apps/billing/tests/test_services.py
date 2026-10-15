import datetime as dt
from decimal import Decimal as D

import pytest
from freezegun import freeze_time

from apps.billing import services
from apps.billing.models import InvoiceStatus, LedgerEntryType
from apps.billing.selectors import customer_balance, customer_statement, outstanding_by_customer
from apps.core.exceptions import BusinessError

pytestmark = pytest.mark.django_db


def test_invoice_snapshot_numbering_and_ledger(make_order, desk, customer):
    order = make_order(items=[(D("2"), D("2"), 3)])  # min sq ft applies
    invoice = services.issue_invoice(order=order, user=desk)
    assert invoice.invoice_no.startswith("INV-") and invoice.sequence == 1
    assert invoice.customer_name == customer.name and invoice.customer_pan == customer.pan_no
    assert invoice.is_vat_invoice
    assert invoice.total == order.total
    assert invoice.invoice_date_bs
    line = invoice.lines.get()
    assert line.quantity == D("15.00") and line.sqft == D("12.00")
    assert "min. 5 sq ft" in line.details
    assert customer_balance(customer) == order.total
    # Later customer edits never change the issued invoice.
    customer.name = "Renamed"
    customer.save()
    invoice.refresh_from_db()
    assert invoice.customer_name == "Hotel Kalpana"


def test_only_one_active_invoice_per_order(make_order, desk):
    order = make_order()
    services.issue_invoice(order=order, user=desk)
    with pytest.raises(BusinessError):
        services.issue_invoice(order=order, user=desk)


def test_quotation_cannot_be_invoiced(make_order, desk):
    with pytest.raises(BusinessError):
        services.issue_invoice(order=make_order(confirm=False), user=desk)


def test_cancel_keeps_number_and_reverses_ledger(make_order, desk, owner, customer):
    order = make_order()
    invoice = services.issue_invoice(order=order, user=desk)
    with pytest.raises(BusinessError):
        services.cancel_invoice(invoice=invoice, user=owner, reason="no")  # reason too short
    services.cancel_invoice(invoice=invoice, user=owner, reason="Wrong size billed")
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.CANCELLED
    assert customer_balance(customer) == D("0.00")
    reissued = services.issue_invoice(order=order, user=desk)
    assert reissued.sequence == 2  # cancelled number is never reused


def test_print_count_marks_copies(make_order, desk):
    invoice = services.issue_invoice(order=make_order(), user=desk)
    assert services.record_invoice_print(invoice=invoice, user=desk, size="a4") == 1
    assert services.record_invoice_print(invoice=invoice, user=desk, size="a5") == 2


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"mode": "cheque", "bank_name": "Nabil"}, "cheque_no"),
        ({"mode": "bank"}, "bank_name"),
        ({"mode": "wallet"}, "wallet"),
    ],
)
def test_payment_mode_details_required(customer, desk, data, field):
    with pytest.raises(BusinessError) as exc:
        services.receive_payment(user=desk, customer=customer, amount=D("100"), **data)
    assert field in exc.value.detail


def test_advance_then_settle_then_void(make_order, desk, owner, customer):
    order = make_order()
    advance = services.receive_payment(
        user=desk, customer=customer, order=order, amount=D("500"), mode="cash"
    )
    assert advance.is_advance and advance.receipt_no.startswith("RCT-")
    services.issue_invoice(order=order, user=desk)
    rest = services.receive_payment(
        user=desk,
        customer=customer,
        order=order,
        amount=order.total - D("500"),
        mode="wallet",
        wallet="esewa",
        reference_no="TX1",
    )
    assert not rest.is_advance
    assert customer_balance(customer) == D("0.00")
    services.void_payment(payment=rest, user=owner, reason="Transaction reversed")
    assert customer_balance(customer) == order.total - D("500")


def test_payment_rules(make_order, desk, customer):
    with pytest.raises(BusinessError):
        services.receive_payment(
            user=desk,
            customer=customer,
            order=make_order(confirm=False),
            amount=D("1"),
            mode="cash",
        )
    with pytest.raises(BusinessError):
        services.receive_payment(user=desk, customer=customer, amount=D("0"), mode="cash")
    with pytest.raises(BusinessError):
        services.receive_payment(
            user=desk,
            customer=customer,
            amount=D("1"),
            mode="cash",
            payment_date=dt.date.today() + dt.timedelta(days=2),
        )


def test_opening_balance_and_statement(customer, owner, desk, make_order):
    with freeze_time("2026-09-01 10:00:00+05:45"):
        services.post_opening_balance(customer=customer, amount=D("4500"), user=owner)
    with freeze_time("2026-09-10 10:00:00+05:45"):
        services.receive_payment(user=desk, customer=customer, amount=D("1500"), mode="cash")
    with freeze_time("2026-10-01 10:00:00+05:45"):
        order = make_order()
        services.issue_invoice(order=order, user=desk)
    statement = customer_statement(customer, dt.date(2026, 9, 5), dt.date(2026, 10, 31))
    assert statement["opening_balance"] == D("4500.00")
    assert [e["entry_type"] for e in statement["entries"]] == [
        LedgerEntryType.PAYMENT,
        LedgerEntryType.INVOICE,
    ]
    assert statement["entries"][0]["balance"] == D("3000.00")
    assert statement["closing_balance"] == D("3000.00") + order.total
    with pytest.raises(BusinessError):
        services.post_opening_balance(customer=customer, amount=D("100"), user=owner)


def test_outstanding_ages_oldest_debits_first(customer, owner, desk):
    with freeze_time("2026-06-01 10:00:00+05:45"):
        services.post_opening_balance(customer=customer, amount=D("1000"), user=owner)
    with freeze_time("2026-09-20 10:00:00+05:45"):
        services.post_adjustment(
            customer=customer, amount=D("2000"), narration="Old board repair", user=owner
        )
    with freeze_time("2026-10-10 10:00:00+05:45"):
        services.receive_payment(user=desk, customer=customer, amount=D("1500"), mode="cash")
    result = outstanding_by_customer(dt.date(2026, 10, 15))[customer.pk]
    assert result.balance == D("1500.00")
    assert result.oldest_due_date == dt.date(2026, 9, 20)  # June debt fully paid first
    assert result.buckets["0-30"] == D("1500.00")
