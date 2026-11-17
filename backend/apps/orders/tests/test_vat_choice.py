"""Add VAT or not: per customer (the default) and per order."""

from decimal import Decimal as D

import pytest

from apps.customers.models import Customer
from apps.orders import services as orders

pytestmark = pytest.mark.django_db


def _input(star_flex, add_vat=None):
    return orders.OrderInput(
        items=[
            orders.ItemInput(
                media_type=star_flex, width=D("10"), height=D("4"), unit="ft", quantity=1
            )
        ],
        add_vat=add_vat,
    )


def test_new_orders_follow_the_customers_setting(make_order, shop):
    plain = Customer.objects.create(name="No VAT Traders", add_vat=False)
    assert make_order().vat_rate == D("13.00")
    order = make_order(customer=plain)
    assert order.vat_rate == 0 and order.vat_amount == 0 and order.total == order.taxable_amount


def test_the_order_can_differ_from_the_customer(shop, desk, customer, star_flex):
    order = orders.create_order(
        user=desk, customer=customer, data=_input(star_flex, add_vat=False), confirm=True
    )
    assert order.vat_amount == 0
    order = orders.update_order(order=order, user=desk, data=_input(star_flex, add_vat=True))
    assert order.vat_rate == D("13.00") and order.vat_amount == D("182.00")
    # Saved again without saying: the order keeps its choice.
    order = orders.update_order(order=order, user=desk, data=_input(star_flex))
    assert order.vat_amount == D("182.00")


def test_no_vat_when_the_shop_is_not_registered(shop, desk, customer, star_flex):
    shop.is_vat_registered = False
    shop.save()
    order = orders.create_order(user=desk, customer=customer, data=_input(star_flex, add_vat=True))
    assert order.vat_amount == 0


def test_price_preview_and_customer_api(api, desk, shop, customer, star_flex):
    item = {"media_type": star_flex.pk, "width": "10", "height": "4", "unit": "ft"}
    body = {"customer": customer.pk, "items": [item], "add_vat": False}
    preview = api(desk).post("/api/v1/orders/price-preview/", body, format="json").json()
    assert preview["totals"]["vat_amount"] == "0.00"
    response = api(desk).patch(
        f"/api/v1/customers/{customer.pk}/", {"add_vat": False}, format="json"
    )
    assert response.status_code == 200 and response.json()["add_vat"] is False
    del body["add_vat"]
    preview = api(desk).post("/api/v1/orders/price-preview/", body, format="json").json()
    assert preview["totals"]["vat_amount"] == "0.00"
