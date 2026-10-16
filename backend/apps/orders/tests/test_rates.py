"""Customer's last rate, custom rates and per-piece items on orders."""

from decimal import Decimal as D

import pytest

from apps.catalog.models import MediaType, PricingUnit
from apps.core.exceptions import BusinessError
from apps.orders import services
from apps.orders.models import RateSource
from apps.orders.selectors import last_rates_for

pytestmark = pytest.mark.django_db


def _input(media, rate=None, w=D("10"), h=D("4"), qty=1):
    return services.OrderInput(
        items=[
            services.ItemInput(
                media_type=media, width=w, height=h, unit="ft", quantity=qty, rate=rate
            )
        ]
    )


def test_last_rate_is_the_most_recent_sold_order(make_order, customer, star_flex, owner):
    make_order(confirm=True)  # Rs 35
    services.create_order(
        user=owner, customer=customer, data=_input(star_flex, rate=D("30")), confirm=True
    )
    services.create_order(  # a quotation is not a sale
        user=owner, customer=customer, data=_input(star_flex, rate=D("25")), confirm=False
    )
    last = last_rates_for(customer)[star_flex.pk]
    assert last.rate == D("30.00")
    assert last.times == 2


def test_previous_rate_is_recognised_and_skips_the_discount_limit(
    make_order, customer, star_flex, owner, desk
):
    services.create_order(
        user=owner, customer=customer, data=_input(star_flex, rate=D("25")), confirm=True
    )
    order = services.create_order(
        user=desk, customer=customer, data=_input(star_flex, rate=D("25"))
    )
    item = order.items.get()
    assert item.rate == D("25.00")
    assert item.rate_source == RateSource.PREVIOUS
    assert item.card_rate == D("35.00")


def test_custom_rate_below_card_counts_against_the_limit(customer, star_flex, desk, owner, shop):
    with pytest.raises(BusinessError) as exc:  # 20% below; front desk limit is 10%
        services.create_order(user=desk, customer=customer, data=_input(star_flex, rate=D("28")))
    assert "items.0.rate" in exc.value.detail
    order = services.create_order(
        user=desk, customer=customer, data=_input(star_flex, rate=D("33"))
    )
    assert order.items.get().rate_source == RateSource.CUSTOM
    order = services.create_order(
        user=owner, customer=customer, data=_input(star_flex, rate=D("20"))
    )
    assert order.items.get().line_total == D("800.00")


def test_custom_rate_above_card_is_always_allowed(customer, star_flex, desk, shop):
    order = services.create_order(
        user=desk, customer=customer, data=_input(star_flex, rate=D("50"))
    )
    assert order.items.get().line_total == D("2000.00")


def test_editing_keeps_an_approved_rate(customer, star_flex, owner, desk, shop):
    order = services.create_order(
        user=owner, customer=customer, data=_input(star_flex, rate=D("20"))
    )
    item = order.items.get()
    data = services.OrderInput(
        items=[
            services.ItemInput(
                id=item.pk,
                media_type=star_flex,
                width=D("10"),
                height=D("4"),
                unit="ft",
                quantity=2,
                rate=D("20"),
            )
        ]
    )
    order = services.update_order(order=order, user=desk, data=data)
    assert order.items.get().line_total == D("1600.00")


def test_per_piece_order_line(customer, desk, shop):
    photo = MediaType.objects.create(
        name="Normal Photo", pricing_unit=PricingUnit.PIECE, rate=D("160")
    )
    order = services.create_order(
        user=desk, customer=customer, data=_input(photo, w=D("0"), h=D("0"), qty=5)
    )
    item = order.items.get()
    assert item.pricing_unit == PricingUnit.PIECE
    assert item.line_total == D("800.00")
    assert item.size_label == ""


def test_customer_rates_endpoint(api, make_order, customer, desk, operator, star_flex):
    make_order(confirm=True)
    rows = api(desk).get(f"/api/v1/customers/{customer.pk}/rates/").json()
    assert rows[0]["media_name"] == "Star Flex"
    assert rows[0]["last_rate"] == "35.00"
    assert rows[0]["card_rate"] == "35.00"
    assert api(operator).get(f"/api/v1/customers/{customer.pk}/rates/").status_code == 403


def test_price_preview_reports_rate_source(api, customer, desk, star_flex, shop):
    body = {
        "customer": customer.pk,
        "items": [{"media_type": star_flex.pk, "width": "10", "height": "4", "rate": "40"}],
    }
    data = api(desk).post("/api/v1/orders/price-preview/", body, format="json").json()
    assert data["items"][0]["rate_source"] == "custom"
    assert data["items"][0]["card_rate"] == "35.00"
