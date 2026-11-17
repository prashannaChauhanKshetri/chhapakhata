"""The statement printed with every item: size, sq ft, qty, rate and amount."""

import datetime as dt
import io
from decimal import Decimal as D

import pytest
from freezegun import freeze_time
from openpyxl import Workbook, load_workbook

from apps.billing import services
from apps.billing.selectors import add_item_lines, customer_statement
from apps.customers.models import Customer
from apps.system.work_log import import_work_log

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _today():
    with freeze_time("2026-10-16 10:00"):
        yield


def _billed(make_order, owner):
    order = make_order(items=[(D("10"), D("4"), 2), (D("2"), D("1"), 1)])
    services.issue_invoice(order=order, user=owner)
    return order


def test_bill_lines_add_up_to_the_bill(make_order, owner, customer):
    order = _billed(make_order, owner)
    data = add_item_lines(customer_statement(customer))
    entry = data["entries"][0]
    items = [line for line in entry["lines"] if line["kind"] == "item"]
    assert [(i["width"], i["height"], i["quantity"]) for i in items] == [
        ("10", "4", 2),
        ("2", "1", 1),
    ]
    assert items[0]["sqft"] == D("80.00")
    assert sum(line["amount"] for line in entry["lines"]) == entry["debit"] == order.total
    assert any(line["particular"] == "VAT 13%" for line in entry["lines"])


def test_imported_work_is_listed_item_by_item(owner):
    wb = Workbook()
    for row in (
        ["Date", "Particular", "Items", "Size", "Qty", "Rate", "Amount", "Discount"],
        ["2083.04.10", "Rapti Stores", "Flex", "3x2", 2, 20, 240, 40],
    ):
        wb.active.append(row)
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    import_work_log(out, name="w.xlsx", user=owner, dry_run=False)
    customer = Customer.objects.get()
    entry = add_item_lines(customer_statement(customer))["entries"][0]
    assert [line["particular"] for line in entry["lines"]] == ["Flex", "Discount"]
    assert sum(line["amount"] for line in entry["lines"]) == entry["debit"] == D("200.00")


def test_payments_and_openings_have_no_lines(owner, customer):
    services.post_opening_balance(
        customer=customer, amount=D("1000"), user=owner, as_of=dt.date(2026, 7, 1)
    )
    services.receive_payment(user=owner, customer=customer, amount=D("400"), mode="cash")
    data = add_item_lines(customer_statement(customer))
    assert [e["lines"] for e in data["entries"]] == [[], []]


def test_print_and_excel_with_items(api, desk, make_order, owner, customer):
    _billed(make_order, owner)
    url = f"/api/v1/customers/{customer.pk}/statement/"
    pdf = api(desk).get(url, {"export": "pdf", "items": "1"})
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
    xlsx = api(desk).get(url, {"export": "xlsx", "items": "1"})
    assert "Sq ft" in _cells(xlsx.content)
    assert "Sq ft" not in _cells(api(desk).get(url, {"export": "xlsx"}).content)


def _cells(content: bytes) -> set:
    sheet = load_workbook(io.BytesIO(content)).active
    return {cell for row in sheet.iter_rows(values_only=True) for cell in row}
