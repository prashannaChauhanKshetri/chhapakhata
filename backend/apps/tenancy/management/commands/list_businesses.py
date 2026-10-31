from __future__ import annotations

from django.db.models import Count

from apps.accounts.models import User
from apps.orders.models import Order
from apps.tenancy.commands import PlatformCommand
from apps.tenancy.models import Business


class Command(PlatformCommand):
    help = "List the businesses on this site with their user and order counts."

    def handle(self, *args, **options):
        users = dict(
            User.objects.filter(is_active=True)
            .values_list("business")
            .annotate(n=Count("id"))
            .values_list("business", "n")
        )
        orders = dict(
            Order.objects.values_list("business")
            .annotate(n=Count("id"))
            .values_list("business", "n")
        )
        rows = [("Slug", "Name", "Active", "Users", "Orders")]
        for b in Business.objects.order_by("pk"):
            rows.append(
                (
                    b.slug,
                    b.name,
                    "yes" if b.is_active else "no",
                    str(users.get(b.pk, 0)),
                    str(orders.get(b.pk, 0)),
                )
            )
        widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
        for row in rows:
            self.stdout.write("  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)))
