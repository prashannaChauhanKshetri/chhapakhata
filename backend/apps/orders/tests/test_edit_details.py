"""Edit details: the words on an order's items change; the money never does."""

import io
from decimal import Decimal as D

import pytest
from openpyxl import Workbook

from apps.billing import services as billing
from apps.billing.selectors import add_item_lines, customer_statement
from apps.core.models import ActivityLog
from apps.orders.models import Order
from apps.system.work_log import import_work_log

pytestmark = pytest.mark.django_db


def _post(api, user, order, items):
    return api(user).post(f"/api/v1/orders/{order.pk}/details/", {"items": items}, format="json")


def test_details_change_on_a_billed_order_but_the_bill_keeps_its_words(
    api, desk, owner, make_order, customer
):
    order = make_order()
    invoice = billing.issue_invoice(order=order, user=owner)
    item = order.items.get()
    total = order.total
    response = _post(api, desk, order, [{"id": item.pk, "description": "Information board"}])
    assert response.status_code == 200
    assert response.json()["items"][0]["description"] == "Information board"
    order.refresh_from_db()
    assert order.total == total
    assert invoice.lines.get().details == ""  # issued bills never change
    statement = add_item_lines(customer_statement(customer))
    assert statement["entries"][0]["lines"][0]["details"].endswith("Information board")
    assert ActivityLog.objects.filter(action="order.details_edited").count() == 1


def test_work_log_orders_can_have_their_details_edited(api, desk, owner):
    wb = Workbook()
    for row in (
        ["Date", "Particular", "Items", "Size", "Qty", "Rate", "Amount"],
        ["2083.04.10", "Rapti Stores", "Flex", "3x2", 2, 20, 240],
    ):
        wb.active.append(row)
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    import_work_log(out, name="w.xlsx", user=owner, dry_run=False)
    order = Order.objects.get()
    item = order.items.get()
    response = _post(
        api, desk, order, [{"id": item.pk, "description": "Shop front", "finishing": "Hemmed"}]
    )
    assert response.status_code == 200
    item.refresh_from_db()
    assert (item.description, item.finishing, item.line_total) == (
        "Shop front",
        "Hemmed",
        D("240.00"),
    )


def test_items_of_another_order_and_operators_are_refused(api, desk, operator, make_order):
    first, second = make_order(), make_order()
    other = second.items.get()
    assert _post(api, desk, first, [{"id": other.pk, "description": "x"}]).status_code == 400
    mine = first.items.get()
    assert _post(api, operator, first, [{"id": mine.pk, "description": "x"}]).status_code == 403
