"""Create the first owner account at installation.

docker compose run --rm api python manage.py create_owner --username anil --first-name Anil
"""

from __future__ import annotations

import getpass

from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services
from apps.accounts.models import User
from apps.core.exceptions import BusinessError
from apps.core.permissions import Role


class Command(BaseCommand):
    help = "Create an owner (admin) account."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--password", help="Omit to be asked (recommended).")

    def handle(self, *args, **options):
        if User.objects.filter(username=options["username"]).exists():
            raise CommandError(f"User '{options['username']}' already exists.")
        password = options["password"]
        if not password:
            password = getpass.getpass("Password: ")
            if password != getpass.getpass("Repeat password: "):
                raise CommandError("Passwords do not match.")
        actor = User.objects.filter(role=Role.OWNER, is_active=True).first()
        try:
            user = services.create_user(
                actor=actor,
                password=password,
                username=options["username"],
                first_name=options["first_name"],
                last_name=options["last_name"],
                role=Role.OWNER,
            )
        except BusinessError as exc:
            raise CommandError(str(exc.detail)) from exc
        self.stdout.write(self.style.SUCCESS(f"Owner account '{user.username}' created."))
