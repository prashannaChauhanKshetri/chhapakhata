from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Stage(models.IntegerChoices):
    CANCELLED = 0, "Cancelled"
    DESIGN = 1, "Design pending / Proof sent"
    READY_FOR_PRINT = 2, "Ready for print"
    PRINTING = 3, "Printing"
    FINISHING = 4, "Finishing / Framing"
    READY = 5, "Ready for collection"
    DELIVERED = 6, "Delivered"


ACTIVE_STAGES = (
    Stage.DESIGN,
    Stage.READY_FOR_PRINT,
    Stage.PRINTING,
    Stage.FINISHING,
    Stage.READY,
)


class Priority(models.IntegerChoices):
    NORMAL = 0, "Normal"
    URGENT = 1, "Urgent"


class Job(TimeStampedModel):
    """Production work for one order item, tracked through the shop's six stages."""

    job_no = models.CharField(max_length=30, unique=True)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="jobs")
    order_item = models.OneToOneField(
        "orders.OrderItem", on_delete=models.CASCADE, related_name="job"
    )
    stage = models.PositiveSmallIntegerField(
        choices=Stage.choices, default=Stage.DESIGN, db_index=True
    )
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, default=Priority.NORMAL)
    deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
        help_text="Operator who printed (or will print) this job.",
    )
    design_file_ref = models.CharField("Design file", max_length=255, blank=True)
    notes = models.TextField(blank=True)
    stage_changed_at = models.DateTimeField(null=True, blank=True)
    material_recorded = models.BooleanField(default=False)

    class Meta:
        ordering = ["deadline", "id"]

    def __str__(self) -> str:
        return self.job_no


class JobStageEvent(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="events")
    from_stage = models.PositiveSmallIntegerField(choices=Stage.choices, null=True, blank=True)
    to_stage = models.PositiveSmallIntegerField(choices=Stage.choices)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.job.job_no}: {self.from_stage} → {self.to_stage}"
