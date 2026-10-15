"""Import or update the rate card.

Media columns: kind=media, name, rate, min_sqft (optional), material (stock item
name, optional), active.
Add-on columns: kind=addon, name, rate, basis (fixed, per_piece, per_sqft,
per_running_ft, percent), default_quantity, active.

    uv run python manage.py import_rate_card rate_card.xlsx
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import AddOn, AddOnBasis, MediaType
from apps.inventory.models import StockItem
from apps.system.importers import boolean, decimal, read_rows, text


class Command(BaseCommand):
    help = "Create or update media types and add-ons from CSV or Excel."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        errors: list[str] = []
        counts = {"media": 0, "addon": 0}
        with transaction.atomic():
            for order, (number, row) in enumerate(read_rows(options["path"])):
                try:
                    kind = text(row, "kind").lower() or "media"
                    name = text(row, "name")
                    rate = decimal(row, "rate")
                    if not name or rate is None:
                        raise ValueError("name and rate are required")
                    if kind == "media":
                        material_name = text(row, "material")
                        material = None
                        if material_name:
                            material = StockItem.objects.filter(name__iexact=material_name).first()
                            if material is None:
                                raise ValueError(f"stock item '{material_name}' does not exist")
                        MediaType.objects.update_or_create(
                            name=name,
                            defaults={
                                "rate_per_sqft": rate,
                                "min_sqft": decimal(row, "min_sqft"),
                                "material": material,
                                "is_active": boolean(row, "active"),
                                "sort_order": order,
                            },
                        )
                    elif kind == "addon":
                        basis = text(row, "basis").lower()
                        if basis not in AddOnBasis.values:
                            raise ValueError(f"basis must be one of {', '.join(AddOnBasis.values)}")
                        AddOn.objects.update_or_create(
                            name=name,
                            defaults={
                                "basis": basis,
                                "rate": rate,
                                "default_quantity": decimal(row, "default_quantity", Decimal("1")),
                                "is_active": boolean(row, "active"),
                                "sort_order": order,
                            },
                        )
                    else:
                        raise ValueError("kind must be 'media' or 'addon'")
                    counts[kind] += 1
                except Exception as exc:
                    errors.append(f"row {number}: {exc}")
            if errors:
                for line in errors:
                    self.stderr.write(line)
                raise CommandError(f"{len(errors)} row(s) have problems; nothing was saved.")
            if options["dry_run"]:
                transaction.set_rollback(True)
        self.stdout.write(
            self.style.SUCCESS(f"Media types: {counts['media']}, add-ons: {counts['addon']}")
        )
