import datetime as dt
import shutil

import pytest

from apps.system.models import BackupStatus, OffsiteStatus
from apps.system.services import _bin, export_all_data, prune_backups, run_backup


def _touch(folder, day: dt.date):
    stamp = day.strftime("%Y%m%d") + "-210000"
    for name in (f"chhapakhata-db-{stamp}.dump", f"chhapakhata-media-{stamp}.tar.gz"):
        (folder / name).write_text("x")
    return stamp


def test_retention_keeps_daily_weekly_monthly(tmp_path):
    today = dt.date(2026, 10, 15)
    stamps = {
        (today - dt.timedelta(days=n)): _touch(tmp_path, today - dt.timedelta(days=n))
        for n in range(0, 400)
    }
    prune_backups(tmp_path, today)
    kept = {p.name.split("-db-")[1][:8] for p in tmp_path.glob("chhapakhata-db-*")}
    kept_days = {dt.datetime.strptime(s, "%Y%m%d").date() for s in kept}
    assert all(today - dt.timedelta(days=n) in kept_days for n in range(14))  # last 14 days
    assert max((today - d).days for d in kept_days) < 12 * 31
    assert 14 < len(kept_days) <= 14 + 8 + 12
    assert len(stamps) == 400


def _has_pg_dump() -> bool:
    try:
        _bin("pg_dump")
    except RuntimeError:
        return False
    return True


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(not _has_pg_dump(), reason="pg_dump not installed")
def test_run_backup_creates_dump(settings, tmp_path, owner):
    settings.BACKUP_DIR = tmp_path
    settings.RCLONE_REMOTE = ""
    run = run_backup("manual", user=owner)
    assert run.status == BackupStatus.SUCCESS, run.message
    assert run.size_bytes > 0 and len(run.sha256) == 64
    assert run.offsite_status == OffsiteStatus.SKIPPED
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.mark.django_db
def test_export_all_data(customer):
    content = export_all_data()
    assert content[:2] == b"PK"
