from decimal import Decimal as D

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.core.exceptions import BusinessError
from apps.inventory.models import MovementType
from apps.orders.models import OrderStatus
from apps.production.models import Stage
from apps.production.services import allowed_targets, move_job

pytestmark = pytest.mark.django_db


def test_stage_rules_follow_the_proposal(make_order, desk, operator, owner):
    job = make_order().jobs.get()
    # Operators cannot mark design approved, or start a job still awaiting proof approval.
    with pytest.raises(PermissionDenied):
        move_job(job=job, user=operator, to_stage=Stage.READY_FOR_PRINT)
    with pytest.raises(PermissionDenied):
        move_job(job=job, user=operator, to_stage=Stage.PRINTING)
    assert allowed_targets(operator, job) == []
    move_job(job=job, user=desk, to_stage=Stage.READY_FOR_PRINT)
    with pytest.raises(PermissionDenied):
        move_job(job=job, user=desk, to_stage=Stage.PRINTING)
    move_job(job=job, user=operator, to_stage=Stage.PRINTING)
    job.refresh_from_db()
    assert job.operator == operator
    assert allowed_targets(desk, job) == [Stage.DESIGN, Stage.READY_FOR_PRINT]  # not ready yet
    with pytest.raises(BusinessError):
        move_job(job=job, user=desk, to_stage=Stage.DELIVERED)
    assert Stage.FINISHING in allowed_targets(operator, job)
    assert len(allowed_targets(owner, job)) == 5


def test_leaving_printing_requires_material(make_order, desk, operator, star_flex_rolls):
    job = make_order().jobs.get()
    move_job(job=job, user=desk, to_stage=Stage.READY_FOR_PRINT)
    move_job(job=job, user=operator, to_stage=Stage.PRINTING)
    with pytest.raises(BusinessError) as exc:
        move_job(job=job, user=operator, to_stage=Stage.FINISHING)
    assert "material" in exc.value.detail
    roll = star_flex_rolls[0]
    result = move_job(
        job=job,
        user=operator,
        to_stage=Stage.FINISHING,
        material={
            "roll": roll,
            "used_sqft": D("42"),
            "wastage_sqft": D("3"),
            "wastage_reason": "Test print",
        },
    )
    assert result["warnings"] == []
    roll.refresh_from_db()
    assert roll.remaining_sqft == D("955.00")  # 1000 − 42 − 3
    kinds = sorted(job.stock_movements.values_list("movement_type", flat=True))
    assert kinds == [MovementType.CONSUMPTION, MovementType.WASTAGE]
    job.refresh_from_db()
    assert job.material_recorded


def test_owner_can_skip_material(make_order, owner):
    job = make_order().jobs.get()
    result = move_job(job=job, user=owner, to_stage=Stage.READY, skip_material=True)
    assert result["warnings"]


def test_narrow_roll_gives_warning(make_order, desk, operator, star_flex_rolls):
    job = make_order(items=[(D("8"), D("6"), 1)]).jobs.get()  # short side 6 ft
    narrow = star_flex_rolls[1]  # 5 ft wide
    move_job(job=job, user=desk, to_stage=Stage.READY_FOR_PRINT)
    move_job(job=job, user=operator, to_stage=Stage.PRINTING)
    result = move_job(
        job=job,
        user=operator,
        to_stage=Stage.FINISHING,
        material={"roll": narrow, "used_sqft": D("48")},
    )
    assert "wider than roll" in result["warnings"][0]


def test_order_status_follows_jobs(make_order, desk, owner):
    order = make_order(items=[(D("10"), D("4"), 1), (D("3"), D("2"), 1)])
    a, b = order.jobs.order_by("job_no")
    move_job(job=a, user=desk, to_stage=Stage.READY_FOR_PRINT)
    order.refresh_from_db()
    assert order.status == OrderStatus.IN_PRODUCTION
    move_job(job=a, user=owner, to_stage=Stage.READY, skip_material=True)
    order.refresh_from_db()
    assert order.status == OrderStatus.IN_PRODUCTION
    move_job(job=b, user=owner, to_stage=Stage.READY, skip_material=True)
    order.refresh_from_db()
    assert order.status == OrderStatus.READY


def test_delivered_jobs_only_reopened_by_owner(make_order, desk, owner):
    job = make_order().jobs.get()
    move_job(job=job, user=owner, to_stage=Stage.READY, skip_material=True)
    move_job(job=job, user=desk, to_stage=Stage.DELIVERED)
    with pytest.raises(PermissionDenied):
        move_job(job=job, user=desk, to_stage=Stage.READY)
    move_job(job=job, user=owner, to_stage=Stage.READY)
