"""Erase one business's data to start entering again (after a backup).

Staff accounts, shop settings and the activity log are kept.

    docker compose exec api python manage.py erase_business_data \
        --business om-traders --owner omtraders
"""

from __future__ import annotations

from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.core.exceptions import BusinessError
from apps.system import erase
from apps.tenancy.commands import BusinessCommand


class Command(BusinessCommand):
    help = "Erase a business's customers, orders, bills, ledger and stock (after a backup)."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="Owner username, recorded as the eraser")
        parser.add_argument(
            "--keep-catalog",
            action="store_true",
            help="Keep the rate card and the stock item list (quantities go to 0)",
        )
        parser.add_argument("--confirm", help=f'Pass "{erase.CONFIRM_WORD}" to skip the question')

    def handle(self, *args, **options):
        owner = User.objects.filter(username=options["owner"], business=self.business).first()
        if owner is None:
            raise CommandError(f"No user '{options['owner']}' in {self.business.name}.")
        counts = ", ".join(
            f"{row['count']} {row['title'].lower()}"
            for row in erase.erase_preview()
            if row["count"] and not (options["keep_catalog"] and row["catalog"])
        )
        self.stdout.write(f"{self.business.name}: this erases {counts or 'nothing'}.")
        confirm = options["confirm"] or input(f"Type {erase.CONFIRM_WORD} to erase: ")
        try:
            result = erase.erase_business_data(
                user=owner, confirm=confirm, keep_catalog=options["keep_catalog"]
            )
        except BusinessError as exc:
            raise CommandError(str(exc.detail)) from exc
        self.stdout.write(f"Backup taken first: {result['backup_file']}")
        self.stdout.write(self.style.SUCCESS(f"Erased from {self.business.name}."))
