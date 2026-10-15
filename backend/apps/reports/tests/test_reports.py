from decimal import Decimal as D

import pytest

from apps.billing import services as billing
from apps.core.dates import local_today
from apps.production.models import Stage
from apps.production.services import move_job
from apps.reports import selectors

pytestmark = pytest.mark.django_db


@pytest.fixture
def busy_day(make_order, desk, operator, owner, star_flex_rolls, customer):
    """Two invoiced orders, one cash and one eSewa payment, one job printed from a roll."""
    first = make_order()
    job = first.jobs.get()
    move_job(job=job, user=desk, to_stage=Stage.READY_FOR_PRINT)
    move_job(job=job, user=operator, to_stage=Stage.PRINTING)
    move_job(
        job=job,
        user=operator,
        to_stage=Stage.FINISHING,
        material={"roll": star_flex_rolls[0], "used_sqft": D("41"), "wastage_sqft": D("2")},
    )
    second = make_order(items=[(D("3"), D("2"), 2)])
    billing.issue_invoice(order=first, user=desk)
    billing.issue_invoice(order=second, user=desk)
    billing.receive_payment(
        user=desk, customer=customer, order=first, amount=first.total, mode="cash"
    )
    billing.receive_payment(
        user=desk, customer=customer, order=second, amount=D("100"), mode="wallet", wallet="esewa"
    )
    return first, second


def _metric(report, label):
    return next(m.value for m in report.summary if m.label == label)


def test_daily_sales_reconciles(busy_day):
    first, second = busy_day
    report = selectors.daily_sales(local_today())
    assert _metric(report, "Invoiced") == first.total + second.total
    assert _metric(report, "Collected") == first.total + D("100")
    assert _metric(report, "Cash collected") == first.total
    modes = {r["mode"]: r["amount"] for r in report.tables[0].rows}
    assert modes["QR / Wallet: Esewa"] == D("100.00")


def test_sales_summary_by_media(busy_day):
    report = selectors.sales_summary(local_today(), local_today())
    media = report.tables[1].rows[0]
    assert media["media"] == "Star Flex"
    assert media["billable"] == D("52.00")  # 10×4 ft once + 3×2 ft twice
    assert media["amount"] == D("1820.00")  # 52 × Rs 35


def test_material_vs_sales(busy_day):
    report = selectors.material_vs_sales(local_today(), local_today())
    row = report.tables[0].rows[0]
    assert row["used"] == D("41.00")
    assert row["wastage"] == D("2.00")
    assert row["printed"] == D("52.00")


def test_pending_dues_and_operator_log(busy_day, operator, customer):
    _, second = busy_day
    dues = selectors.pending_dues(local_today())
    assert dues.tables[0].rows[0]["balance"] == second.total - D("100")
    log = selectors.operator_log(local_today(), local_today(), operator=operator)
    assert log.tables[0].rows[0]["sqft"] == D("41.00")


@pytest.mark.parametrize(
    "slug",
    [
        "daily-sales",
        "monthly-sales",
        "pending-dues",
        "collections",
        "material-vs-sales",
        "operator-log",
        "stock",
    ],
)
@pytest.mark.parametrize("export", ["json", "xlsx", "pdf"])
def test_report_endpoints_render(api, owner, busy_day, slug, export):
    response = api(owner).get(f"/api/v1/reports/{slug}/?export={export}")
    assert response.status_code == 200
    if export == "pdf":
        assert response.content.startswith(b"%PDF")
    if export == "xlsx":
        assert response.content[:2] == b"PK"
