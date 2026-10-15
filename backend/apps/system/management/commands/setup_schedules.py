"""Create (or update) the nightly backup schedule. Safe to run on every start."""

from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.models import Schedule

TASK = "apps.system.services.scheduled_backup"


class Command(BaseCommand):
    help = "Register the nightly backup with the background worker."

    def handle(self, *args, **options):
        now = timezone.localtime()
        next_run = now.replace(hour=settings.BACKUP_HOUR, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += dt.timedelta(days=1)
        schedule, created = Schedule.objects.update_or_create(
            name="nightly-backup",
            defaults={
                "func": TASK,
                "schedule_type": Schedule.DAILY,
                "repeats": -1,
            },
        )
        if created or schedule.next_run is None or schedule.next_run.hour != next_run.hour:
            schedule.next_run = next_run
            schedule.save(update_fields=["next_run"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Nightly backup scheduled; next run {schedule.next_run:%Y-%m-%d %H:%M}"
            )
        )
