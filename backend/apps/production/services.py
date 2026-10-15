"""Production board rules.

Who may move a job *into* each stage follows the proposal (section 3.3):

=====  ===========================  =====================
Stage  Name                         Moved there by
=====  ===========================  =====================
1      Design pending / Proof sent  Front desk / designer
2      Ready for print              Front desk
3      Printing                     Operator
4      Finishing / Framing          Operator
5      Ready for collection         Operator
6      Delivered                    Front desk
=====  ===========================  =====================

Operators pick up a job only once front desk has marked it ready for print
(so nothing is printed before the customer approves the proof).

The owner can make any move. A job that passes the Printing stage must have
its material recorded first (roll + sq ft used), unless the owner skips it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.core.activity import log_activity
from apps.core.exceptions import BusinessError
from apps.core.permissions import Role
from apps.core.sequences import DocType, next_number
from apps.orders.models import Order, OrderStatus

from .models import Job, JobStageEvent, Priority, Stage

STAGE_MOVERS: dict[int, frozenset[str]] = {
    Stage.DESIGN: frozenset({Role.FRONT_DESK}),
    Stage.READY_FOR_PRINT: frozenset({Role.FRONT_DESK}),
    Stage.PRINTING: frozenset({Role.OPERATOR}),
    Stage.FINISHING: frozenset({Role.OPERATOR}),
    Stage.READY: frozenset({Role.OPERATOR}),
    Stage.DELIVERED: frozenset({Role.FRONT_DESK}),
}

ROLE_NAMES = {Role.FRONT_DESK: "front desk", Role.OPERATOR: "operator"}


def _is_owner(user: Any) -> bool:
    return bool(user.is_superuser or user.role == Role.OWNER)


def can_move_to(user: Any, stage: int) -> bool:
    if _is_owner(user):
        return stage in STAGE_MOVERS
    return user.role in STAGE_MOVERS.get(stage, frozenset())


def allowed_targets(user: Any, job: Job) -> list[int]:
    """Stages this user may move this job to (for the UI's move menu)."""
    if job.stage == Stage.CANCELLED:
        return []
    if job.stage == Stage.DELIVERED and not _is_owner(user):
        return []
    if _awaiting_proof(user, job):
        return []
    return [
        s
        for s in STAGE_MOVERS
        if s != job.stage
        and can_move_to(user, s)
        and (s != Stage.DELIVERED or job.stage == Stage.READY or _is_owner(user))
    ]


def _awaiting_proof(user: Any, job: Job) -> bool:
    """Operators start work only after front desk marks the job ready for print."""
    return user.role == Role.OPERATOR and not _is_owner(user) and job.stage == Stage.DESIGN


def needs_material(job: Job, to_stage: int) -> bool:
    """True when this move passes Printing and no material has been recorded yet."""
    passes_printing = job.stage <= Stage.PRINTING < to_stage
    material = job.order_item.media_type.material_id
    return passes_printing and not job.material_recorded and material is not None


@transaction.atomic
def create_jobs_for_order(order: Order, user: Any) -> list[Job]:
    jobs = []
    for item in order.items.select_related("media_type").order_by("line_no"):
        if hasattr(item, "job"):
            continue
        job = Job.objects.create(
            job_no=next_number(DocType.JOB).number,
            order=order,
            order_item=item,
            stage=Stage.DESIGN,
            priority=Priority.URGENT if order.is_urgent else Priority.NORMAL,
            deadline=order.deadline,
            design_file_ref=item.design_file_ref,
            stage_changed_at=timezone.now(),
        )
        JobStageEvent.objects.create(
            job=job, from_stage=None, to_stage=Stage.DESIGN, created_by=user
        )
        jobs.append(job)
    return jobs


def refresh_order_status(order: Order) -> Order:
    """Derive the order's production status from its jobs."""
    if order.status in (OrderStatus.QUOTATION, OrderStatus.CANCELLED):
        return order
    stages = list(order.jobs.exclude(stage=Stage.CANCELLED).values_list("stage", flat=True))
    if not stages:
        return order
    if all(s == Stage.DELIVERED for s in stages):
        status = OrderStatus.DELIVERED
    elif all(s >= Stage.READY for s in stages):
        status = OrderStatus.READY
    elif any(s > Stage.DESIGN for s in stages):
        status = OrderStatus.IN_PRODUCTION
    else:
        status = OrderStatus.CONFIRMED
    if status != order.status:
        order.status = status
        order.delivered_at = timezone.now() if status == OrderStatus.DELIVERED else None
        order.save(update_fields=["status", "delivered_at", "updated_at"])
    return order


@transaction.atomic
def move_job(
    *,
    job: Job,
    user: Any,
    to_stage: int,
    note: str = "",
    material: dict[str, Any] | None = None,
    skip_material: bool = False,
    request: Any = None,
    refresh_order: bool = True,
) -> dict[str, Any]:
    """Move a job to another stage, recording material use when it leaves Printing."""
    from apps.inventory.services import record_job_consumption

    job = (
        Job.objects.select_for_update(of=("self",))
        .select_related("order", "order_item__media_type__material")
        .get(pk=job.pk)
    )
    if job.stage == Stage.CANCELLED:
        raise BusinessError("This job was cancelled with its order.")
    try:
        target = Stage(int(to_stage))
    except ValueError as exc:
        raise BusinessError({"to_stage": ["Choose a valid stage."]}) from exc
    if target == Stage.CANCELLED:
        raise BusinessError({"to_stage": ["Cancel the order to cancel its jobs."]})
    if target == job.stage:
        raise BusinessError({"to_stage": ["The job is already in this stage."]})
    if job.stage == Stage.DELIVERED and not _is_owner(user):
        raise PermissionDenied("Only the owner can reopen a delivered job.")
    if _awaiting_proof(user, job):
        raise PermissionDenied(
            "This job is waiting for design approval. Front desk marks it ready for print."
        )
    if target == Stage.DELIVERED and job.stage != Stage.READY and not _is_owner(user):
        raise BusinessError(
            {"to_stage": ["Only jobs that are ready for collection can be delivered."]}
        )
    if not can_move_to(user, target):
        movers = " or ".join(ROLE_NAMES[r] for r in STAGE_MOVERS[target])
        raise PermissionDenied(f"Only the owner or {movers} can move a job to '{target.label}'.")

    warnings: list[str] = []
    if needs_material(job, target):
        if material:
            result = record_job_consumption(user=user, job=job, request=request, **material)
            warnings.extend(result["warnings"])
        elif skip_material and _is_owner(user):
            warnings.append("Material was not recorded for this job.")
        else:
            raise BusinessError(
                {"material": ["Record the roll and sq ft used before moving past Printing."]},
                code="material_required",
            )
    elif material:
        result = record_job_consumption(user=user, job=job, request=request, **material)
        warnings.extend(result["warnings"])
        job.refresh_from_db()

    previous = Stage(job.stage)
    if target == Stage.PRINTING and user.role == Role.OPERATOR:
        job.operator = user
    job.stage = target
    job.stage_changed_at = timezone.now()
    job.save(
        update_fields=["stage", "stage_changed_at", "operator", "material_recorded", "updated_at"]
    )
    JobStageEvent.objects.create(
        job=job, from_stage=previous, to_stage=target, note=note[:255], created_by=user
    )
    if refresh_order:
        refresh_order_status(job.order)
    log_activity(
        user,
        "job.moved",
        job,
        message=f"{previous.label} → {target.label}",
        metadata={"from": int(previous), "to": int(target)},
        request=request,
    )
    return {"job": job, "warnings": warnings}


@transaction.atomic
def cancel_jobs_for_order(order: Order, user: Any, reason: str) -> None:
    for job in order.jobs.select_for_update().exclude(stage=Stage.CANCELLED):
        previous = job.stage
        job.stage = Stage.CANCELLED
        job.stage_changed_at = timezone.now()
        job.save(update_fields=["stage", "stage_changed_at", "updated_at"])
        JobStageEvent.objects.create(
            job=job,
            from_stage=previous,
            to_stage=Stage.CANCELLED,
            note=reason[:255],
            created_by=user,
        )


@transaction.atomic
def update_job_details(*, job: Job, user: Any, request: Any = None, **fields: Any) -> Job:
    """Edit operator assignment, deadline, priority, design file or notes."""
    allowed = {"operator", "deadline", "priority", "design_file_ref", "notes"}
    unknown = set(fields) - allowed
    if unknown:
        raise BusinessError(f"These fields cannot be edited here: {', '.join(sorted(unknown))}.")
    for key, value in fields.items():
        setattr(job, key, value)
    job.save()
    log_activity(user, "job.updated", job, metadata={"fields": sorted(fields)}, request=request)
    return job


def default_used_sqft(job: Job) -> Decimal:
    """Pre-fill for the material dialog: actual printed area of the item."""
    item = job.order_item
    return item.sqft * item.quantity
