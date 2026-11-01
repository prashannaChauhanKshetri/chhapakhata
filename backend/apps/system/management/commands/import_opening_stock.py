"""Import opening stock at go-live.

Columns are matched loosely (see apps/system/go_live.py): Item, Kind,
Quantity, Unit, Roll width, Roll length, Rolls, Sq ft left, Low-stock level.
The same import is in Settings → Import.

    uv run python manage.py import_opening_stock stock.xlsx --owner owner
"""

from __future__ import annotations

from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.system.go_live import run_from_command
from apps.tenancy.commands import BusinessCommand


class Command(BusinessCommand):
    help = "Import opening stock from Excel or CSV."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--owner", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        owner = User.objects.filter(username=options["owner"], business=self.business).first()
        if owner is None:
            raise CommandError(f"No user '{options['owner']}'.")
        run_from_command(
            self, "opening-stock", options["path"], user=owner, dry_run=options["dry_run"]
        )
