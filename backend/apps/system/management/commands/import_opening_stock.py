"""Import opening stock at go-live.

Columns: item, kind (roll_media, ink, eyelets, frame, standee, other),
low_stock_level, quantity (non-roll items) or roll_width_ft, roll_length_ft,
remaining_sqft (one row per roll; remaining empty = full roll).

    uv run python manage.py import_opening_stock stock.xlsx --owner owner
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.inventory.models import DEFAULT_UNIT, StockItem, StockKind
from apps.inventory.services import RollSpec, add_opening_stock
from apps.system.importers import decimal, read_rows, text


class Command(BaseCommand):
    help = "Create stock items and bring opening quantities and rolls into stock."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--owner", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        owner = User.objects.filter(username=options["owner"]).first()
        if owner is None:
            raise CommandError(f"No user '{options['owner']}'.")
        errors: list[str] = []
        entries = 0
        with transaction.atomic():
            for number, row in read_rows(options["path"]):
                try:
                    name = text(row, "item")
                    kind = text(row, "kind").lower() or StockKind.OTHER
                    if not name or kind not in StockKind.values:
                        raise ValueError("item and a valid kind are required")
                    item, _ = StockItem.objects.get_or_create(
                        name=name,
                        defaults={
                            "kind": kind,
                            "unit": DEFAULT_UNIT[StockKind(kind)],
                            "low_stock_level": decimal(row, "low_stock_level") or 0,
                        },
                    )
                    if item.is_roll_media:
                        width, length = (
                            decimal(row, "roll_width_ft"),
                            decimal(row, "roll_length_ft"),
                        )
                        if not width or not length:
                            raise ValueError(
                                "roll_width_ft and roll_length_ft are required for rolls"
                            )
                        add_opening_stock(
                            user=owner,
                            stock_item=item,
                            rolls=[RollSpec(width, length, decimal(row, "remaining_sqft"))],
                        )
                    else:
                        add_opening_stock(
                            user=owner, stock_item=item, quantity=decimal(row, "quantity")
                        )
                    entries += 1
                except Exception as exc:
                    errors.append(f"row {number}: {exc}")
            if errors:
                for line in errors:
                    self.stderr.write(line)
                raise CommandError(f"{len(errors)} row(s) have problems; nothing was saved.")
            if options["dry_run"]:
                transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS(f"Opening stock entries: {entries}"))
