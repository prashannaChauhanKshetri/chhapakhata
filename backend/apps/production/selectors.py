"""Read-side queries for production."""

from __future__ import annotations

from typing import Any

from django.db.models import Count, IntegerField, Min, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from .models import Job, Stage

STAGE_COUNT = Stage.DELIVERED  # stages 1–6; progress is measured against Delivered


def _job_value(aggregate: Any) -> Coalesce:
    sub = (
        Job.objects.filter(order=OuterRef("pk"))
        .exclude(stage=Stage.CANCELLED)
        .values("order")
        .annotate(v=aggregate)
        .values("v")[:1]
    )
    return Coalesce(Subquery(sub, output_field=IntegerField()), 0)


def job_progress_annotations() -> dict[str, Any]:
    """Per-order production progress, as subqueries (one query for a whole list).

    ``jobs_total``  items in production (cancelled jobs left out)
    ``jobs_ready``  of those, ready for collection or delivered
    ``stage_sum``   sum of their stages, for an overall percentage
    ``stage_min``   the furthest-behind job, which is what the customer waits for
    """
    return {
        "jobs_total": _job_value(Count("id")),
        "jobs_ready": _job_value(Count("id", filter=Q(stage__gte=Stage.READY))),
        "stage_sum": _job_value(Sum("stage")),
        "stage_min": _job_value(Min("stage")),
    }


def order_progress(order: Any) -> dict[str, Any] | None:
    """Progress for an order annotated with ``job_progress_annotations``.

    ``None`` for quotations and cancelled orders (no production to show).
    """
    from apps.orders.models import OrderStatus

    if order.status in (OrderStatus.QUOTATION, OrderStatus.CANCELLED):
        return None
    total = getattr(order, "jobs_total", 0) or 0
    if order.status == OrderStatus.DELIVERED:
        percent, stage = 100, int(Stage.DELIVERED)
    elif total == 0:
        percent, stage = 0, int(Stage.DESIGN)
    else:
        percent = round(order.stage_sum / (total * STAGE_COUNT) * 100)
        stage = int(order.stage_min)
    return {
        "percent": percent,
        "stage": stage,
        "stage_label": Stage(stage).label,
        "jobs": total,
        "jobs_ready": getattr(order, "jobs_ready", 0) or 0,
    }
