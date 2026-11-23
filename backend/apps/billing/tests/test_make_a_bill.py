"""Make a bill: several orders on one bill, VAT chosen at billing time and added once."""

import io
from decimal import Decimal as D

import pytest
from freezegun import freeze_time
from openpyxl import Workbook

from apps.billing import services
from apps.billing.models import InvoiceOrder, LedgerEntryType
from apps.billing.selectors import add_item_lines, customer_balance, customer_statement
from apps.core.exceptions import BusinessError
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.system.work_log import import_work_log

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _today():
    with freeze_time("2026-10-16 10:00"):
        yield


def test_several_orders_one_bill_vat_added_once(make_order, owner, customer):
    first = make_order(items=[(D("10"), D("4"), 1)])  # 1,400 + 182 VAT on the order
    second = make_order(items=[(D("5"), D("2"), 2)])  # 700 + 91
    invoice = services.issue_bill(customer=customer, orders=[second, first], user=owner)
    assert [link.order for link in invoice.order_links.order_by("id")] == [first, second]
    assert invoice.taxable_amount == D("2100.00")  # before VAT: no VAT on VAT
    assert (invoice.vat_amount, invoice.total) == (D("273.00"), D("2373.00"))
    assert invoice.lines.count() == 2
    assert invoice.lines.order_by("line_no").first().details.startswith(first.order_no)
    assert customer_balance(customer) == D("2373.00")
    assert set(customer.invoices.get().orders.all()) == {first, second}
    assert first.invoices.get() == invoice


def test_vat_chosen_at_billing_time(make_order, owner, customer):
    order = make_order()  # the order has VAT
    invoice = services.issue_invoice(
        order=order, user=owner, add_vat=False, vat_note="Exempt: PAN 609876543"
    )
    assert (invoice.is_vat_invoice, invoice.vat_amount, invoice.total) == (
        False,
        D("0.00"),
        D("1400.00"),
    )
    assert invoice.vat_note == "Exempt: PAN 609876543"


def test_bill_follows_the_customer_setting_for_mixed_orders(make_order, owner, shop):
    plain = Customer.objects.create(name="No VAT Traders", add_vat=False)
    a = make_order(customer=plain)
    b = make_order(customer=plain)
    invoice = services.issue_bill(customer=plain, orders=[a, b], user=owner)
    assert invoice.vat_amount == 0


def test_refuses_billed_quotation_and_other_customers_orders(make_order, owner, customer):
    other = Customer.objects.create(name="Gita Tharu")
    billed = make_order()
    services.issue_invoice(order=billed, user=owner)
    quote = make_order(confirm=False)
    theirs = make_order(customer=other)
    with pytest.raises(BusinessError) as caught:
        services.issue_bill(customer=customer, orders=[billed, quote, theirs], user=owner)
    problems = caught.value.detail["orders"]
    assert any("already on bill" in str(p) for p in problems)
    assert any("quotation" in str(p) for p in problems)
    assert any("another customer" in str(p) for p in problems)


def test_cancelling_frees_the_orders_for_a_new_bill(make_order, owner, customer):
    a, b = make_order(), make_order()
    invoice = services.issue_bill(customer=customer, orders=[a, b], user=owner)
    services.cancel_invoice(invoice=invoice, user=owner, reason="Billed by mistake")
    assert not InvoiceOrder.objects.filter(is_active=True).exists()
    again = services.issue_bill(customer=customer, orders=[a], user=owner)
    assert again.total == a.total
    # a is on the new bill; b, still confirmed, is back on the account.
    assert customer_balance(customer) == a.total + b.total


def _work_log(owner, rows):
    wb = Workbook()
    for row in [["Date", "Particular", "Items", "Size", "Qty", "Rate", "Amount"], *rows]:
        wb.active.append(row)
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    import_work_log(out, name="w.xlsx", user=owner, dry_run=False)


def test_work_log_orders_from_one_to_another(owner, shop):
    _work_log(
        owner,
        [
            ["2083.04.10", "Rapti Stores", "Flex", "6x4", 3, 100, 7200],
            ["2083.05.02", "Rapti Stores", "Forex", "2x3", 150, 120, 108000],
        ],
    )
    customer = Customer.objects.get()
    orders = list(Order.objects.order_by("order_date"))
    assert customer_balance(customer) == D("115200.00")
    invoice = services.issue_bill(customer=customer, orders=orders, user=owner, add_vat=True)
    assert (invoice.taxable_amount, invoice.vat_amount) == (D("115200.00"), D("14976.00"))
    assert customer_balance(customer) == D("130176.00")  # only the VAT is new
    moved = invoice.ledger_entries.filter(entry_type=LedgerEntryType.WORK_BILLED)
    assert sum(e.credit for e in moved) == D("115200.00")
    # The statement lists the bill line by line, with VAT once.
    entries = add_item_lines(customer_statement(customer))["entries"]
    bill = next(e for e in entries if e["entry_type"] == "invoice")
    assert [line["particular"] for line in bill["lines"]] == ["Flex", "Forex", "VAT 13%"]
    assert sum(line["amount"] for line in bill["lines"]) == bill["debit"]


def test_preview_unbilled_and_make_a_bill_api(api, desk, owner, operator, make_order, customer):
    a, b = make_order(), make_order()
    listed = api(desk).get(f"/api/v1/customers/{customer.pk}/unbilled-orders/").json()
    assert [o["order_no"] for o in listed] == [a.order_no, b.order_no]
    body = {"customer": customer.pk, "orders": [a.pk, b.pk], "add_vat": False}
    preview = api(desk).post("/api/v1/invoices/preview/", body, format="json").json()
    assert (preview["vat_amount"], preview["total"], preview["default_add_vat"]) == (
        "0.00",
        "2800.00",
        True,
    )
    made = api(desk).post("/api/v1/invoices/", body, format="json")
    assert made.status_code == 201
    assert [o["order_no"] for o in made.json()["orders"]] == [a.order_no, b.order_no]
    assert api(desk).get(f"/api/v1/customers/{customer.pk}/unbilled-orders/").json() == []
    pdf = api(desk).post(f"/api/v1/invoices/{made.json()['id']}/print/?size=a4")
    assert pdf.status_code == 200
    assert api(operator).post("/api/v1/invoices/preview/", body, format="json").status_code == 403
