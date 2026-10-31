"""Management commands that work inside one business."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from .context import rls_bypass, use_business
from .models import Business


def resolve_business(slug: str | None) -> Business:
    """The business named by ``--business``, or the only one there is."""
    if slug:
        business = Business.objects.filter(slug=slug).first()
        if business is None:
            raise CommandError(f"No business '{slug}'. See: manage.py list_businesses")
        return business
    businesses = list(Business.objects.all()[:2])
    if not businesses:
        raise CommandError("No business exists yet. Create one with: manage.py create_business")
    if len(businesses) > 1:
        raise CommandError(
            "This site has several businesses: pass --business <slug> "
            "(see manage.py list_businesses)."
        )
    return businesses[0]


class BusinessCommand(BaseCommand):
    """A command that reads and writes one business's data (``--business``)."""

    business: Business

    def create_parser(self, prog_name: str, subcommand: str, **kwargs: Any):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.add_argument(
            "--business", help="Business slug; needed only when the site has several."
        )
        return parser

    def execute(self, *args: Any, **options: Any) -> Any:
        self.business = resolve_business(options.get("business"))
        with use_business(self.business):
            return super().execute(*args, **options)


class PlatformCommand(BaseCommand):
    """A command for the site operator that sees every business."""

    def execute(self, *args: Any, **options: Any) -> Any:
        with rls_bypass():
            return super().execute(*args, **options)
