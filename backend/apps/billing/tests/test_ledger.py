"""Shop-wide ledger: balances summary, day book, statement extras."""

import datetime as dt
from decimal import Decimal as D

import pytest

from apps.billing import services
from apps.billing.selectors import customer_statement, ledger_summary
from apps.customers.models import Customer

pytestmark = pytest.mark.django_db


@pytest.fixture
def ledger_data(owner, customer):
    other = Customer.objects.create(name="Gita Tharu")
    services.post_opening_balance(
        customer=customer, amount=D("1000"), user=owner, as_of=dt.date(2026, 7, 1)
    )
    services.post_opening_balance(
        customer=other, amount=D("-200"), user=owner, as_of=dt.date(2026, 7, 1)
    )
    services.receive_payment(
        user=owner,
        customer=customer,
        amount=D("400"),
        mode="cash",
        payment_date=dt.date(2026, 9, 1),
    )
    return customer, other


def test_summary_splits_opening_period_and_closing(ledger_data):
    customer, other = ledger_data
    data = ledger_summary(dt.date(2026, 8, 1), dt.date(2026, 9, 30))
    rows = {r["customer_id"]: r for r in data["rows"]}
    assert rows[customer.pk]["opening_balance"] == D("1000.00")
    assert rows[customer.pk]["credit"] == D("400.00")
    assert rows[customer.pk]["closing_balance"] == D("600.00")
    assert rows[customer.pk]["last_payment_date"] == dt.date(2026, 9, 1)
    assert rows[other.pk]["closing_balance"] == D("-200.00")
    assert data["totals"]["receivable"] == D("600.00")
    assert data["totals"]["advances"] == D("200.00")
    assert [
        r["customer_id"]
        for r in ledger_summary(None, dt.date(2026, 9, 30), balance="advance")["rows"]
    ] == [other.pk]


def test_statement_has_type_totals_and_aging(ledger_data):
    customer, _ = ledger_data
    data = customer_statement(customer, dt.date(2026, 8, 1), dt.date(2026, 9, 30))
    assert data["opening_balance"] == D("1000.00")
    assert data["closing_balance"] == D("600.00")
    assert data["by_type"][0]["entry_type"] == "payment"
    assert data["aging"]["buckets"][-1] == {"label": "90+", "amount": D("600.00")}


def test_ledger_api_and_permissions(api, owner, desk, operator, ledger_data):
    assert api(desk).get("/api/v1/ledger/").json()["count"] == 3
    summary = api(desk).get("/api/v1/ledger/summary/", {"from": "2026-08-01", "to": "2026-09-30"})
    assert summary.json()["totals"]["customers"] == 2
    xlsx = api(owner).get("/api/v1/ledger/summary/", {"export": "xlsx"})
    assert xlsx.status_code == 200
    assert api(operator).get("/api/v1/ledger/").status_code == 403


def test_periods_endpoint(api, operator):
    keys = [p["key"] for p in api(operator).get("/api/v1/utils/periods/").json()]
    assert keys == ["today", "this_month", "last_month", "this_fy", "last_fy"]
