"""Media typed by hand, rates entered by hand, and Qty × Rate when no size is given."""

from decimal import Decimal as D

import pytest

from apps.catalog.models import MediaType

pytestmark = pytest.mark.django_db


def _item(**kwargs):
    return {"unit": "ft", "quantity": 1, **kwargs}


def _order(api, user, customer, *items, confirm=True):
    body = {"customer": customer.pk, "items": list(items), "confirm": confirm}
    return api(user).post("/api/v1/orders/", body, format="json")


def test_a_new_media_name_is_typed_and_added_to_the_list(api, desk, shop, customer):
    item = _item(media_name="Forex Sticker 2mm", width="1", height="1", quantity=10, rate="50")
    response = _order(api, desk, customer, item)
    assert response.status_code == 201, response.json()
    line = response.json()["items"][0]
    assert line["media_name"] == "Forex Sticker 2mm"
    assert line["line_total"] == "500.00"  # 1 sq ft × 10 × 50: no minimum for typed media
    media = MediaType.objects.get(name="Forex Sticker 2mm")
    assert (media.rate, media.min_sqft) == (D("50.00"), D("0"))
    # Typed again, in other letters: the same list entry, not a second one.
    again = _order(api, desk, customer, _item(media_name="forex sticker 2MM", rate="55"))
    assert again.status_code == 201
    assert MediaType.objects.filter(name__iexact="forex sticker 2mm").count() == 1


def test_no_width_and_height_means_qty_times_rate(api, desk, shop, customer, star_flex):
    response = _order(api, desk, customer, _item(media_type=star_flex.pk, quantity=5, rate="120"))
    line = response.json()["items"][0]
    assert (line["pricing_unit"], line["line_total"]) == ("piece", "600.00")
    typed = _order(api, desk, customer, _item(media_name="Stamp", quantity=3, rate="250"))
    assert typed.json()["items"][0]["line_total"] == "750.00"


def test_a_typed_media_needs_its_rate_and_both_sides(api, desk, shop, customer, star_flex):
    no_rate = _order(api, desk, customer, _item(media_name="Brand new thing", quantity=2))
    assert no_rate.status_code == 400 and no_rate.json()["errors"][0]["attr"] == "items.0.rate"
    one_side = _order(api, desk, customer, _item(media_type=star_flex.pk, width="3"))
    assert one_side.status_code == 400
    assert "both width and height" in one_side.json()["errors"][0]["detail"]
    nothing = _order(api, desk, customer, _item())
    assert nothing.status_code == 400


def test_preview_prices_a_typed_media_without_saving_it(api, desk, shop, customer):
    body = {
        "customer": customer.pk,
        "items": [_item(media_name="Mug print", quantity=4, rate="300")],
    }
    preview = api(desk).post("/api/v1/orders/price-preview/", body, format="json")
    assert preview.status_code == 200
    assert preview.json()["totals"]["subtotal"] == "1200.00"
    assert not MediaType.objects.filter(name="Mug print").exists()
