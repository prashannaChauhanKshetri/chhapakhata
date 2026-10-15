from __future__ import annotations

import datetime as dt
from typing import Any

from django.utils import timezone

from .models import BackupRun, BackupStatus

STALE_AFTER = dt.timedelta(hours=26)


def backup_status() -> dict[str, Any]:
    last = BackupRun.objects.first()
    last_ok = BackupRun.objects.filter(status=BackupStatus.SUCCESS).first()
    stale = last_ok is None or timezone.now() - last_ok.started_at > STALE_AFTER
    return {
        "last_run_at": last.started_at.isoformat() if last else None,
        "last_run_status": last.status if last else None,
        "last_success_at": last_ok.started_at.isoformat() if last_ok else None,
        "offsite_status": last_ok.offsite_status if last_ok else None,
        "is_stale": stale,
    }
