from django.core.management.base import BaseCommand, CommandError

from apps.system.models import BackupStatus, BackupTrigger
from apps.system.services import run_backup


class Command(BaseCommand):
    help = "Take a backup now (database + uploaded images) and copy it online if configured."

    def handle(self, *args, **options):
        run = run_backup(BackupTrigger.MANUAL)
        if run.status != BackupStatus.SUCCESS:
            raise CommandError(f"Backup failed: {run.message}")
        self.stdout.write(
            self.style.SUCCESS(f"Backup saved: {run.database_file} ({run.size_bytes} bytes)")
        )
        self.stdout.write(f"Online copy: {run.get_offsite_status_display()} {run.offsite_message}")
