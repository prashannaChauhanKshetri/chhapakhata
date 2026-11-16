"""Void payments-sheet receipts that repeat a payment already recorded with its order.

    docker compose exec api python manage.py void_duplicate_payments \
        --business om-traders --owner omtraders
"""

from __future__ import annotations

from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.core.exceptions import BusinessError
from apps.system import duplicates
from apps.system.erase import CONFIRM_WORD
from apps.tenancy.commands import BusinessCommand


class Command(BusinessCommand):
    help = "Void payments recorded twice (payments sheet + order), after a backup."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="Owner username, recorded as the voider")
        parser.add_argument("--confirm", help=f'Pass "{CONFIRM_WORD}" to skip the question')

    def handle(self, *args, **options):
        owner = User.objects.filter(username=options["owner"], business=self.business).first()
        if owner is None:
            raise CommandError(f"No user '{options['owner']}' in {self.business.name}.")
        preview = duplicates.duplicates_preview()
        if not preview["count"]:
            self.stdout.write(self.style.SUCCESS("No duplicate payments found."))
            return
        self.stdout.write(
            f"{preview['count']} duplicate payments, Rs {preview['total']}. For example:"
        )
        for row in preview["sample"][:5]:
            self.stdout.write(
                f"  {row['receipt_no']} repeats {row['original_receipt_no']}: "
                f"{row['customer']} {row['payment_date']} Rs {row['amount']}"
            )
        confirm = options["confirm"] or input(f"Type {CONFIRM_WORD} to void them: ")
        try:
            result = duplicates.void_duplicates(user=owner, confirm=confirm)
        except BusinessError as exc:
            raise CommandError(str(exc.detail)) from exc
        self.stdout.write(f"Backup taken first: {result['backup_file']}")
        self.stdout.write(
            self.style.SUCCESS(f"Voided {result['voided']} duplicates, Rs {result['total']}.")
        )
