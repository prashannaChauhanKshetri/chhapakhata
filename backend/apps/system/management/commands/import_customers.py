"""Import customers with their opening dues and advances (the opening ledger).

Columns are matched loosely (see apps/system/go_live.py): Name, Phone, Address,
PAN, Type, Opening balance (positive = they owe, negative = advance), or
separate Debit/Credit columns. The same import is in Settings → Import.

    uv run python manage.py import_customers customers.xlsx --as-of 2026-11-09 --owner owner
"""

from __future__ import annotations

import datetime as dt

from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.system.go_live import run_from_command
from apps.tenancy.commands import BusinessCommand


class Command(BusinessCommand):
    help = "Import customers and opening balances from Excel or CSV."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--owner", required=True, help="Username recorded as the importer")
        parser.add_argument("--as-of", help="Date of the opening balances (YYYY-MM-DD)")
        parser.add_argument("--dry-run", action="store_true", help="Check the file without saving")

    def handle(self, *args, **options):
        owner = User.objects.filter(username=options["owner"], business=self.business).first()
        if owner is None:
            raise CommandError(f"No user '{options['owner']}'.")
        as_of = dt.date.fromisoformat(options["as_of"]) if options["as_of"] else None
        run_from_command(
            self, "customers", options["path"], user=owner, dry_run=options["dry_run"], as_of=as_of
        )
