from __future__ import annotations

import io
from importlib import import_module

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.accounts.models import User
from apps.core.models import ShopSettings
from apps.core.permissions import Role
from apps.customers.models import Customer
from apps.tenancy.context import use_business
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db


def test_create_business_makes_an_empty_shop_with_an_owner(business, owner):
    out = io.StringIO()
    call_command(
        "create_business",
        name="Sharma  Prints",
        owner_username="ram",
        first_name="Ram",
        password="Long-enough-1",
        stdout=out,
    )
    shop = Business.objects.get(slug="sharma-prints")
    assert shop.name == "Sharma Prints"
    ram = User.objects.get(username="ram")
    assert ram.business == shop and ram.role == Role.OWNER and ram.check_password("Long-enough-1")
    with use_business(shop):
        assert ShopSettings.load().name == "Sharma Prints"
        assert Customer.objects.count() == 0
    assert "Sharma Prints" in out.getvalue()


def test_create_business_refuses_a_taken_username_or_slug(business, owner):
    with pytest.raises(CommandError, match="site-wide"):
        call_command("create_business", name="Other", owner_username="owner", password="x" * 10)
    call_command("create_business", name="Other", owner_username="hari", password="Long-enough-1")
    with pytest.raises(CommandError, match="already exists"):
        call_command("create_business", name="Other", owner_username="gopal", password="x" * 10)


def test_list_businesses(business, owner):
    call_command("create_business", name="Sharma Prints", owner_username="ram", password="L" * 10)
    out = io.StringIO()
    call_command("list_businesses", stdout=out)
    lines = out.getvalue().splitlines()
    assert lines[0].split()[:2] == ["Slug", "Name"]
    assert any(line.startswith("sharma-prints") for line in lines)


def test_business_commands_need_a_choice_when_there_are_several(business):
    Business.objects.create(name="Second", slug="second")
    with pytest.raises(CommandError, match="--business"):
        call_command("create_owner", username="x", password="Long-enough-1")
    call_command("create_owner", username="x", password="Long-enough-1", business="second")
    assert User.objects.get(username="x").business.slug == "second"


def test_create_business_after_a_single_shop_install(business, owner):
    """Old sites saved their one settings row with id 1 by hand; the counter stayed at 1."""
    ShopSettings.load()
    sequence_fix = import_module("apps.core.migrations.0005_shopsettings_id_sequence")
    with connection.cursor() as cursor:
        cursor.execute("SELECT setval(pg_get_serial_sequence('core_shopsettings', 'id'), 1, false)")
        cursor.execute(sequence_fix.Migration.operations[0].sql)
    call_command("create_business", name="Second", owner_username="ram", password="Long-enough-1")
    with use_business(Business.objects.get(slug="second")):
        assert ShopSettings.load().name == "Second"
