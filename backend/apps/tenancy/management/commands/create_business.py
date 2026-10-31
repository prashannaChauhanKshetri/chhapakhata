"""Add a new, empty business to this site, with its first owner account.

docker compose exec api python manage.py create_business --name "Sharma Prints" --owner-username ram
"""

from __future__ import annotations

import getpass

from django.core.management.base import CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.accounts import services
from apps.accounts.models import User
from apps.core.exceptions import BusinessError
from apps.core.models import ShopSettings
from apps.core.permissions import Role
from apps.tenancy.commands import PlatformCommand
from apps.tenancy.context import use_business
from apps.tenancy.models import Business


class Command(PlatformCommand):
    help = "Create a business (its own separate data) and its owner account."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Shop name, shown on bills")
        parser.add_argument("--slug", help="Short id for commands (default: from the name)")
        parser.add_argument("--owner-username", required=True)
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--password", help="Omit to be asked (recommended).")

    def handle(self, *args, **options):
        name = " ".join(options["name"].split())
        slug = options["slug"] or slugify(name)[:60]
        username = options["owner_username"]
        if not slug:
            raise CommandError("Give a --slug made of letters, numbers and hyphens.")
        if Business.objects.filter(slug=slug).exists():
            raise CommandError(f"A business with the slug '{slug}' already exists.")
        if User.objects.filter(username=username).exists():
            raise CommandError(f"The username '{username}' is taken (usernames are site-wide).")
        password = options["password"]
        if not password:
            password = getpass.getpass("Owner password: ")
            if password != getpass.getpass("Repeat password: "):
                raise CommandError("Passwords do not match.")

        with transaction.atomic():
            business = Business.objects.create(name=name, slug=slug)
            with use_business(business):
                ShopSettings.load()
                try:
                    owner = services.create_user(
                        actor=None,
                        password=password,
                        username=username,
                        first_name=options["first_name"],
                        last_name=options["last_name"],
                        role=Role.OWNER,
                    )
                except BusinessError as exc:
                    raise CommandError(str(exc.detail)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Business '{business.name}' ({business.slug}) created. "
                f"Owner '{owner.username}' can sign in now."
            )
        )
