from __future__ import annotations

from django.conf import settings
from django.db import models


class BackupStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Succeeded"
    FAILED = "failed", "Failed"


class OffsiteStatus(models.TextChoices):
    SKIPPED = "skipped", "Not configured"
    PENDING = "pending", "Waiting for internet"
    SUCCESS = "success", "Copied online"
    FAILED = "failed", "Failed"


class BackupTrigger(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    MANUAL = "manual", "Manual"


class BackupRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=BackupStatus.choices, default=BackupStatus.RUNNING
    )
    trigger = models.CharField(
        max_length=10, choices=BackupTrigger.choices, default=BackupTrigger.SCHEDULED
    )
    database_file = models.CharField(max_length=255, blank=True)
    media_file = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    offsite_status = models.CharField(
        max_length=10, choices=OffsiteStatus.choices, default=OffsiteStatus.SKIPPED
    )
    offsite_message = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Backup {self.started_at:%Y-%m-%d %H:%M} ({self.status})"
