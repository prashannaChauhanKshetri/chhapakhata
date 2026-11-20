"""Print orders from one date to another, item by item."""

import io
from decimal import Decimal as D

import pytest
from freezegun import freeze_time
from openpyxl import load_workbook

from apps.billing.selectors import orders_for_print
from apps.core.dates import local_today
from apps.customers.models import Customer

pytestmark = pytest.mark.django_db
URL = "/api/v1/orders/print/"


@pytest.fixture(autouse=True)
def _today():
    with freeze_time("2026-11-20 11:00"):
        yield


def _orders(make_order, customer):
    other = Customer.objects.create(name="Gita Tharu")
    a = make_order(items=[(D("6"), D("4"), 3)])
    b = make_order(items=[(D("2"), D("3"), 150)], customer=other)
    make_order(confirm=False)  # a quotation: not printed
    return a, b, other


def test_orders_between_two_dates_item_by_item(make_order, customer):
    a, b, _ = _orders(make_order, customer)
    data = orders_for_print(local_today(), local_today())
    assert [r["order_no"] for r in data["rows"]] == [a.order_no, b.order_no]
    first = data["rows"][0]["lines"][0]
    assert (first["width"], first["height"], first["sqft"], first["quantity"]) == (
        "6",
        "4",
        D("72.00"),
        3,
    )
    for row in data["rows"]:
        assert sum(line["amount"] for line in row["lines"]) == row["total"]
    assert data["totals"]["orders"] == 2
    assert data["totals"]["total"] == a.total + b.total


def test_print_pdf_excel_one_customer_and_permissions(api, desk, operator, make_order, customer):
    a, b, other = _orders(make_order, customer)
    params = {"from": "2026-11-01", "to": "2026-11-20", "export": "pdf"}
    pdf = api(desk).get(URL, params)
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
    xlsx = api(desk).get(URL, {**params, "export": "xlsx", "customer": other.pk})
    sheet = load_workbook(io.BytesIO(xlsx.content)).active
    cells = {c for row in sheet.iter_rows(values_only=True) for c in row}
    assert b.order_no in cells and a.order_no not in cells
    assert api(desk).get(URL, {**params, "customer": "x"}).status_code == 404
    assert api(desk).get(URL, {"from": "2026-11-20", "to": "2026-11-01"}).status_code == 400
    assert api(operator).get(URL, params).status_code == 403
