"""Orders entered late: any past date, never a future one."""

import pytest
from freezegun import freeze_time

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _today():
    with freeze_time("2026-11-20 11:00"):
        yield


def _body(customer, star_flex, **extra):
    item = {"media_type": star_flex.pk, "width": "3", "height": "2", "unit": "ft"}
    return {"customer": customer.pk, "items": [item], "confirm": True, **extra}


def test_an_order_from_two_days_ago(api, desk, shop, customer, star_flex):
    body = _body(customer, star_flex, order_date="2026-11-18", deadline="2026-11-19T11:00:00Z")
    response = api(desk).post("/api/v1/orders/", body, format="json")
    assert response.status_code == 201, response.json()
    assert response.json()["order_date"] == "2026-11-18"
    assert response.json()["order_date_bs"] == "2083-08-02"


def test_today_when_no_date_is_given(api, desk, shop, customer, star_flex):
    response = api(desk).post("/api/v1/orders/", _body(customer, star_flex), format="json")
    assert response.json()["order_date"] == "2026-11-20"


def test_future_dates_and_deadlines_before_the_date_are_refused(
    api, desk, shop, customer, star_flex
):
    future = api(desk).post(
        "/api/v1/orders/", _body(customer, star_flex, order_date="2026-11-21"), format="json"
    )
    assert future.status_code == 400 and future.json()["errors"][0]["attr"] == "order_date"
    early = _body(customer, star_flex, order_date="2026-11-18", deadline="2026-11-17T11:00:00Z")
    refused = api(desk).post("/api/v1/orders/", early, format="json")
    assert refused.status_code == 400 and refused.json()["errors"][0]["attr"] == "deadline"


def test_the_date_can_be_corrected_before_billing(api, desk, shop, customer, star_flex):
    order = api(desk).post("/api/v1/orders/", _body(customer, star_flex), format="json").json()
    body = _body(customer, star_flex, order_date="2026-11-15")
    response = api(desk).put(f"/api/v1/orders/{order['id']}/", body, format="json")
    assert response.status_code == 200 and response.json()["order_date"] == "2026-11-15"
