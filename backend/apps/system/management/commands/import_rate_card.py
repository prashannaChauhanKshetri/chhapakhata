"""Import or update the rate card (media and add-ons).

Columns are matched loosely (see apps/system/go_live.py): Kind (media or
add-on), Name, Rate, Per (sq ft or piece), Minimum sq ft, Material, Basis,
Default quantity, Active. The same import is in Settings → Import.

    uv run python manage.py import_rate_card rate_card.xlsx
"""

from __future__ import annotations

from apps.accounts.models import User
from apps.core.permissions import Role
from apps.system.go_live import run_from_command
from apps.tenancy.commands import BusinessCommand


class Command(BusinessCommand):
    help = "Create or update media types and add-ons from Excel or CSV."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        owner = User.objects.filter(business=self.business, role=Role.OWNER, is_active=True).first()
        run_from_command(self, "rate-card", options["path"], user=owner, dry_run=options["dry_run"])
