import datetime as dt
from decimal import Decimal as D

import pytest

from apps.billing import services as billing
from apps.core.dates import local_today
from apps.reports.insights import insights

pytestmark = pytest.mark.django_db


def test_insights_reconcile_with_orders_and_payments(make_order, desk, customer):
    order = make_order(confirm=True, items=[(D("10"), D("4"), 2)])
    billing.issue_invoice(order=order, user=desk)
    billing.receive_payment(user=desk, customer=customer, order=order, amount=D("500"), mode="cash")
    today = local_today()

    data = insights(today - dt.timedelta(days=6), today)
    assert data["summary"]["work_done"] == order.total
    assert data["summary"]["invoiced"] == order.total
    assert data["summary"]["collected"] == D("500.00")
    assert data["summary"]["orders"] == 1
    assert data["granularity"] == "day"
    assert len(data["trend"]) == 7
    assert data["trend"][-1]["work_done"] == float(order.total)
    assert data["top_items"][0]["name"] == "Star Flex"
    assert data["top_items"][0]["sqft"] == D("80.00")
    assert data["top_customers"][0]["name"] == customer.name
    assert data["payment_modes"] == [{"mode": "Cash", "amount": D("500.00"), "count": 1}]
    assert data["dues_total"] == order.total - D("500.00")
    assert data["aging"][0] == {"label": "0-30", "amount": order.total - D("500.00")}


def test_long_periods_are_grouped_by_bs_month():
    today = local_today()
    data = insights(today - dt.timedelta(days=120), today)
    assert data["granularity"] == "month"
    assert 4 <= len(data["trend"]) <= 6
    assert data["trend"][0]["date_from"] == (today - dt.timedelta(days=120)).isoformat()


def test_insights_api_is_owner_only(api, owner, desk):
    response = api(owner).get("/api/v1/insights/")
    assert response.status_code == 200
    assert {"summary", "trend", "production"} <= set(response.json())
    assert api(desk).get("/api/v1/insights/").status_code == 403


def test_front_desk_dashboard_lists_dues_to_follow_up(api, make_order, desk, customer):
    order = make_order(confirm=True)
    billing.issue_invoice(order=order, user=desk)
    rows = api(desk).get("/api/v1/dashboard/").json()["dues_follow_up"]
    assert rows[0]["name"] == customer.name
    assert rows[0]["balance"] == f"{order.total:.2f}"
