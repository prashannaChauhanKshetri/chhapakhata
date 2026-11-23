"""A confirmed order counts on the customer's statement and dues straight away.

Before, an order reached the statement only when billed, so a customer who had
paid part of an unbilled order showed as "advance with the shop". Now:

* confirming posts the order total (dated the order day);
* editing posts the difference; cancelling takes it off;
* making a bill moves it onto the bill (no double counting); cancelling the bill
  puts it back on the account.
"""

import datetime as dt
import importlib
from decimal import Decimal as D

import pytest
from django.apps import apps as django_apps

from apps.billing import services
from apps.billing.models import LedgerEntry, LedgerEntryType
from apps.billing.selectors import customer_balance, customer_statement
from apps.orders import services as orders

pytestmark = pytest.mark.django_db


def charges(order):
    return list(
        order.ledger_entries.filter(entry_type=LedgerEntryType.ORDER_CHARGE).values_list(
            "debit", "credit"
        )
    )


def test_a_quotation_is_not_owed_and_a_confirmed_order_is(make_order, customer):
    quotation = make_order(confirm=False)
    assert customer_balance(customer) == 0
    orders.confirm_order(order=quotation, user=quotation.created_by)
    assert charges(quotation) == [(quotation.total, D("0"))]
    entry = quotation.ledger_entries.get()
    assert entry.entry_date == quotation.order_date
    assert entry.narration == f"Order {quotation.order_no}"
    assert customer_balance(customer) == quotation.total


def test_paid_part_of_an_unbilled_order_leaves_the_rest_owed(make_order, customer, desk):
    # The shop's case: an order partly paid leaves the rest owed, not "an advance".
    order = make_order(items=[(D("10"), D("4"), 8)])
    paid = order.total - D("1000")
    services.receive_payment(user=desk, customer=customer, amount=paid, mode="cash", order=order)
    assert customer_balance(customer) == D("1000.00")
    today = dt.date.today()
    statement = customer_statement(customer, today - dt.timedelta(days=30), today)
    kinds = [e["entry_type"] for e in statement["entries"]]
    assert LedgerEntryType.ORDER_CHARGE in kinds
    assert statement["closing_balance"] == D("1000.00")


def test_editing_posts_the_difference_and_cancelling_takes_it_off(make_order, customer, desk):
    order = make_order(items=[(D("10"), D("4"), 1)])
    first = order.total
    data = orders.OrderInput(
        items=[
            orders.ItemInput(
                id=order.items.get().pk,
                media_type=order.items.get().media_type,
                width=D("10"),
                height=D("4"),
                unit="ft",
                quantity=2,
            )
        ]
    )
    order = orders.update_order(order=order, user=desk, data=data)
    assert order.total > first
    assert customer_balance(customer) == order.total
    assert charges(order)[-1] == (order.total - first, D("0"))

    orders.cancel_order(order=order, user=desk, reason="Customer changed mind")
    assert customer_balance(customer) == 0
    assert services.work_on_account(order) == 0


def test_a_bill_moves_the_order_onto_it_without_double_counting(make_order, customer, owner):
    a, b = make_order(), make_order()
    assert customer_balance(customer) == a.total + b.total
    invoice = services.issue_bill(customer=customer, orders=[a, b], user=owner)
    assert customer_balance(customer) == invoice.total
    assert services.work_on_account(a) == services.work_on_account(b) == 0

    # Cancelling the bill puts both orders back on the account, as orders.
    services.cancel_invoice(invoice=invoice, user=owner, reason="Wrong customer")
    assert customer_balance(customer) == a.total + b.total
    back = LedgerEntry.objects.filter(order=a).order_by("-id").first()
    assert back.entry_type == LedgerEntryType.ORDER_CHARGE


def test_billing_without_vat_owes_the_bill_not_the_order(make_order, customer, owner, shop):
    order = make_order()
    invoice = services.issue_bill(customer=customer, orders=[order], user=owner, add_vat=False)
    assert invoice.total < order.total  # the order had VAT; the bill does not
    assert customer_balance(customer) == invoice.total


def test_orders_confirmed_before_this_change_are_brought_on_the_account(make_order, customer):
    order = make_order()
    # As if confirmed under the old rule: no order line on the account yet.
    LedgerEntry.objects.filter(order=order).delete()
    assert customer_balance(customer) == 0
    billed = make_order()
    services.issue_invoice(order=billed, user=billed.created_by)
    quotation = make_order(confirm=False)

    migration = importlib.import_module("apps.billing.migrations.0011_charge_open_orders")
    migration.charge(django_apps, None)
    assert charges(order) == [(order.total, D("0"))]
    assert services.work_on_account(billed) == 0  # billed: already on its bill
    assert charges(quotation) == []
    assert customer_balance(customer) == order.total + billed.total
    # Running it again changes nothing.
    migration.charge(django_apps, None)
    assert customer_balance(customer) == order.total + billed.total


# -- Totals and ageing: a moved or cancelled charge is not money received -------------


def test_billed_and_received_totals_do_not_double_count(make_order, customer, owner, desk):
    from apps.billing.selectors import ledger_summary

    order = make_order()
    invoice = services.issue_bill(customer=customer, orders=[order], user=owner)
    services.receive_payment(user=desk, customer=customer, amount=D("100"), mode="cash")
    today = dt.date.today()
    statement = customer_statement(customer, today - dt.timedelta(days=30), today)
    assert statement["total_debit"] == invoice.total  # not order + invoice
    assert statement["total_credit"] == D("100")  # only the money received
    row = ledger_summary(today - dt.timedelta(days=30), today)["rows"][0]
    assert (row["debit"], row["credit"]) == (invoice.total, D("100.00"))
    assert row["closing_balance"] == invoice.total - D("100")


def test_a_moved_order_does_not_age_older_unpaid_bills(make_order, customer, owner):
    from freezegun import freeze_time

    from apps.billing.selectors import outstanding_by_customer

    with freeze_time("2026-09-01 10:00:00+05:45"):
        old = make_order()
        services.issue_invoice(order=old, user=owner)  # unpaid since 1 Sep
    with freeze_time("2026-10-01 10:00:00+05:45"):
        new = make_order()
    with freeze_time("2026-10-05 10:00:00+05:45"):
        services.issue_invoice(order=new, user=owner)
    result = outstanding_by_customer(dt.date(2026, 10, 10))[customer.pk]
    assert result.oldest_due_date == dt.date(2026, 9, 1)
    assert result.balance == customer_balance(customer)


def test_cancelling_a_bill_made_before_this_change_puts_the_order_back(make_order, customer, owner):
    order = make_order()
    LedgerEntry.objects.filter(order=order).delete()  # confirmed under the old rule
    invoice = services.issue_invoice(order=order, user=owner)  # moves nothing
    assert customer_balance(customer) == invoice.total
    services.cancel_invoice(invoice=invoice, user=owner, reason="Wrong amount")
    assert customer_balance(customer) == order.total  # still a confirmed order, owed
