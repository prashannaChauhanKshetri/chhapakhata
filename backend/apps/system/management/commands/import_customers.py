"""Import customers with their opening dues.

Columns: name, phone, alt_phone, address, pan_no, customer_type (individual or
business), opening_balance (positive = they owe, negative = advance), notes.

    uv run python manage.py import_customers customers.xlsx --as-of 2026-11-09 --owner owner
"""

from __future__ import annotations

import datetime as dt

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.billing.services import post_opening_balance
from apps.customers.models import Customer, CustomerType
from apps.system.importers import decimal, read_rows, text


class Command(BaseCommand):
    help = "Import customers and opening balances from CSV or Excel."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--owner", required=True, help="Username recorded as the importer")
        parser.add_argument("--as-of", help="Date of the opening balances (YYYY-MM-DD)")
        parser.add_argument("--dry-run", action="store_true", help="Check the file without saving")

    def handle(self, *args, **options):
        owner = User.objects.filter(username=options["owner"]).first()
        if owner is None:
            raise CommandError(f"No user '{options['owner']}'.")
        as_of = dt.date.fromisoformat(options["as_of"]) if options["as_of"] else None
        created = skipped = 0
        errors: list[str] = []
        with transaction.atomic():
            for number, row in read_rows(options["path"]):
                try:
                    name = text(row, "name")
                    if not name:
                        raise ValueError("name is required")
                    phone = text(row, "phone")
                    if Customer.objects.filter(name__iexact=name, phone=phone).exists():
                        skipped += 1
                        continue
                    kind = text(row, "customer_type").lower() or CustomerType.INDIVIDUAL
                    if kind not in CustomerType.values:
                        raise ValueError("customer_type must be 'individual' or 'business'")
                    customer = Customer(
                        name=name,
                        phone=phone,
                        alt_phone=text(row, "alt_phone"),
                        address=text(row, "address"),
                        pan_no=text(row, "pan_no"),
                        customer_type=kind,
                        notes=text(row, "notes"),
                        created_by=owner,
                    )
                    customer.full_clean()
                    customer.save()
                    opening = decimal(row, "opening_balance")
                    if opening:
                        post_opening_balance(
                            customer=customer, amount=opening, user=owner, as_of=as_of
                        )
                    created += 1
                except Exception as exc:
                    errors.append(f"row {number}: {exc}")
            if errors:
                for line in errors:
                    self.stderr.write(line)
                raise CommandError(f"{len(errors)} row(s) have problems; nothing was saved.")
            if options["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run: nothing saved."))
        self.stdout.write(
            self.style.SUCCESS(f"Customers created: {created}, already present: {skipped}")
        )
