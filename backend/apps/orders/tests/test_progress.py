"""Production progress on the order list."""

from decimal import Decimal as D

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.production.models import Stage
from apps.production.services import move_job

pytestmark = pytest.mark.django_db


def _progress(api, user, order):
    rows = api(user).get("/api/v1/orders/", {"page_size": 50}).json()["results"]
    return next(r["progress"] for r in rows if r["id"] == order.pk)


def test_progress_follows_the_slowest_item(api, make_order, desk, owner):
    order = make_order(confirm=True, items=[(D("10"), D("4"), 1), (D("6"), D("3"), 1)])
    progress = _progress(api, desk, order)
    assert progress == {
        "percent": round(2 / 12 * 100),  # both at Design (1 of 6)
        "stage": Stage.DESIGN,
        "stage_label": "Design pending / Proof sent",
        "jobs": 2,
        "jobs_ready": 0,
    }
    first = order.jobs.order_by("id").first()
    for stage in (Stage.READY_FOR_PRINT, Stage.PRINTING, Stage.FINISHING, Stage.READY):
        move_job(job=first, user=owner, to_stage=stage, skip_material=True)
        first.refresh_from_db()
    progress = _progress(api, desk, order)
    assert progress["percent"] == round((5 + 1) / 12 * 100)
    assert progress["stage"] == Stage.DESIGN  # the customer still waits for item 2
    assert progress["jobs_ready"] == 1


def test_quotations_have_no_progress(api, make_order, desk):
    quotation = make_order(confirm=False)
    assert _progress(api, desk, quotation) is None


def test_progress_costs_no_extra_query_per_row(api, make_order, desk):
    for _ in range(3):
        make_order(confirm=True)
    client = api(desk)
    with CaptureQueriesContext(connection) as few:
        client.get("/api/v1/orders/")
    for _ in range(5):
        make_order(confirm=True)
    with CaptureQueriesContext(connection) as many:
        client.get("/api/v1/orders/")
    assert len(many) == len(few)
