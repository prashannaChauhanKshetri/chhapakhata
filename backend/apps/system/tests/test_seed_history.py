"""The history generator produces data that obeys the same rules as real use."""

import io
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.billing.models import Invoice, LedgerEntry, Payment
from apps.billing.selectors import customer_balance
from apps.customers.models import Customer
from apps.orders.models import Order

pytestmark = pytest.mark.django_db(transaction=True)


def test_two_weeks_of_history_follow_the_rules():
    out = io.StringIO()
    call_command("seed_history", "--until", "2020-07-31", stdout=out)
    assert "History ready" in out.getvalue()

    owner = User.objects.get(username="newowner")
    assert owner.date_joined.date().isoformat() == "2020-07-16"  # 1 Shrawan 2077
    assert Order.objects.filter(order_date__lt="2020-07-16").count() == 0
    assert Order.objects.count() >= 5

    # Invoice and receipt numbers rise with their dates.
    invoices = list(Invoice.objects.order_by("sequence").values_list("invoice_date", flat=True))
    assert invoices == sorted(invoices)
    receipts = list(Payment.objects.order_by("sequence").values_list("payment_date", flat=True))
    assert receipts == sorted(receipts)

    # Each customer's ledger balance = issued invoices − valid payments (no other entries yet).
    assert not LedgerEntry.objects.exclude(entry_type__in=["invoice", "payment"]).exists()
    for customer in Customer.objects.all():
        billed = sum(
            (i.total for i in Invoice.objects.filter(customer=customer, status="issued")),
            Decimal(0),
        )
        paid = sum(
            (p.amount for p in Payment.objects.filter(customer=customer, status="valid")),
            Decimal(0),
        )
        assert customer_balance(customer) == billed - paid


def test_refuses_a_database_that_is_in_use(owner):
    with pytest.raises(CommandError):
        call_command("seed_history", "--until", "2020-07-20", stdout=io.StringIO())
