"""The go-live import commands, run against the templates shipped in docs/templates."""

from decimal import Decimal as D
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command

from apps.billing.selectors import customer_balance
from apps.catalog.models import AddOn, MediaType
from apps.customers.models import Customer
from apps.inventory.models import StockItem

TEMPLATES = Path(__file__).resolve().parents[4] / "docs" / "templates"
pytestmark = pytest.mark.django_db


def test_import_all_templates(owner):
    call_command("import_opening_stock", str(TEMPLATES / "opening_stock.csv"), owner="owner")
    call_command("import_rate_card", str(TEMPLATES / "rate_card.csv"))
    call_command(
        "import_customers", str(TEMPLATES / "customers.csv"), owner="owner", as_of="2026-11-09"
    )

    star = StockItem.objects.get(name="Star Flex")
    assert star.rolls.count() == 2
    assert star.on_hand == D("2160.00")  # 1,640 full roll + 520 left on the part-used roll
    assert StockItem.objects.get(name="Eco-solvent ink").on_hand == D("6.00")

    assert MediaType.objects.get(name="Vinyl").min_sqft == D("2.00")
    assert MediaType.objects.get(name="Star Flex").material == star
    assert AddOn.objects.get(name="Eyelets").default_quantity == D("8.00")

    assert customer_balance(Customer.objects.get(name="Nepalgunj Medical Hall")) == D("4500.00")
    assert customer_balance(Customer.objects.get(name="Hotel Kalpana")) == D("-2000.00")

    # Re-running the customer import does not duplicate anyone.
    call_command("import_customers", str(TEMPLATES / "customers.csv"), owner="owner")
    assert Customer.objects.count() == 3


def test_bad_rows_save_nothing(owner, tmp_path):
    bad = tmp_path / "customers.csv"
    bad.write_text("name,phone,pan_no\nGood Customer,9800000000,\nBad PAN,9800000001,12345\n")
    with pytest.raises(CommandError):
        call_command("import_customers", str(bad), owner="owner")
    assert Customer.objects.count() == 0


def test_dry_run_saves_nothing(owner):
    call_command("import_opening_stock", str(TEMPLATES / "opening_stock.csv"), owner="owner")
    call_command("import_rate_card", str(TEMPLATES / "rate_card.csv"), dry_run=True)
    assert MediaType.objects.count() == 0
