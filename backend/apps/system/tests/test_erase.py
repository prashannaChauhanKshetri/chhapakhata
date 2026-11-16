"""Erasing a shop's data to start again: owner only, typed "Confirm", backup first,
and never another business's data."""

from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from apps.billing import services as billing
from apps.billing.models import Invoice, LedgerEntry, Payment
from apps.catalog.models import AddOn, MediaType
from apps.core.exceptions import BusinessError
from apps.core.models import ActivityLog, ShopSettings
from apps.core.permissions import Role
from apps.customers.models import Customer
from apps.inventory.models import Roll, StockItem, StockMovement, Supplier
from apps.orders.models import Order
from apps.production.models import Job
from apps.system import erase
from apps.system.models import BackupStatus
from apps.tenancy.context import use_business
from apps.tenancy.models import Business
from conftest import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def backups(monkeypatch):
    """Record backup calls instead of running pg_dump (one test below runs it for real)."""
    calls = []

    def fake_backup(trigger, user=None):
        calls.append(user)
        return SimpleNamespace(status=BackupStatus.SUCCESS, database_file="/backups/x.dump", pk=1)

    monkeypatch.setattr(erase, "run_backup", fake_backup)
    return calls


@pytest.fixture
def full_shop(owner, desk, star_flex_rolls, make_order, eyelets):
    order = make_order(items=[(D("10"), D("4"), 2)])
    billing.issue_invoice(order=order, user=desk)
    billing.receive_payment(user=desk, customer=order.customer, amount="500", mode="cash")
    billing.set_opening_balance(customer=order.customer, amount=D("1200"), user=owner)
    return order


@pytest.fixture
def other_shop(db):
    shop = Business.objects.create(name="Sharma Prints", slug="sharma-prints")
    with use_business(shop):
        make_user("ram", Role.OWNER)
        Customer.objects.create(name="Sharma's customer")
        MediaType.objects.create(name="Flex", rate=D("30"))
    return shop


def test_owner_erases_everything_but_staff_settings_and_history(
    backups, full_shop, other_shop, owner, desk
):
    shop_name = ShopSettings.load().name
    preview = {row["title"]: row["count"] for row in erase.erase_preview()}
    assert preview["Orders"] == 1 and preview["Customers"] == 1 and preview["Rolls"] == 2

    result = erase.erase_business_data(user=owner, confirm="Confirm")
    assert backups == [owner]  # a backup first
    assert result["erased"]["Orders"] == 1 and result["erased"]["Invoices"] == 1
    for model in (
        Order,
        Job,
        Invoice,
        Payment,
        LedgerEntry,
        Customer,
        Roll,
        StockMovement,
        Supplier,
        StockItem,
        MediaType,
        AddOn,
    ):
        assert model.objects.count() == 0, model.__name__
    # Kept: staff, settings, and the record of who erased what.
    assert {owner.pk, desk.pk} <= set(owner.business.users.values_list("pk", flat=True))
    assert ShopSettings.load().name == shop_name
    assert ActivityLog.objects.filter(action="data.erased", actor=owner).exists()

    # The other business is untouched.
    with use_business(other_shop):
        assert Customer.objects.count() == 1 and MediaType.objects.count() == 1


def test_numbering_starts_again_after_an_erase(backups, full_shop, owner, make_order):
    first_no = full_shop.order_no
    erase.erase_business_data(user=owner, confirm="confirm")
    # Everything is re-entered from scratch, rate card included.
    flex = MediaType.objects.create(name="Star Flex", rate=D("35"))
    again = make_order(customer=Customer.objects.create(name="New start"), media=flex)
    assert again.order_no == first_no


def test_keep_the_rate_card_and_stock_list(backups, full_shop, owner, star_flex, eyelets):
    erase.erase_business_data(user=owner, confirm="Confirm", keep_catalog=True)
    assert Order.objects.count() == 0 and Roll.objects.count() == 0
    assert set(MediaType.objects.values_list("name", flat=True)) == {"Star Flex"}
    assert AddOn.objects.get().name == "Eyelets"
    stock = StockItem.objects.get(name="Star Flex")
    assert stock.on_hand == D("0") and star_flex.material_id == stock.pk


def test_wrong_word_or_not_the_owner_erases_nothing(backups, full_shop, owner, desk):
    with pytest.raises(BusinessError):
        erase.erase_business_data(user=owner, confirm="yes")
    with pytest.raises(BusinessError, match="Only the owner"):
        erase.erase_business_data(user=desk, confirm="Confirm")
    assert backups == [] and Order.objects.count() == 1


def test_a_failed_backup_erases_nothing(monkeypatch, full_shop, owner):
    monkeypatch.setattr(
        erase,
        "run_backup",
        lambda trigger, user=None: SimpleNamespace(status=BackupStatus.FAILED),
    )
    with pytest.raises(BusinessError, match="backup failed"):
        erase.erase_business_data(user=owner, confirm="Confirm")
    assert Order.objects.count() == 1 and Customer.objects.count() == 1


def test_api(api, backups, full_shop, owner, desk):
    url = "/api/v1/system/erase/"
    assert api(desk).get(url).status_code == 403
    assert api(desk).post(url, {"confirm": "Confirm"}, format="json").status_code == 403
    preview = api(owner).get(url).json()
    assert {"title": "Orders", "count": 1, "catalog": False} in preview
    wrong = api(owner).post(url, {"confirm": "ok"}, format="json")
    assert wrong.status_code == 400 and Order.objects.count() == 1
    done = api(owner).post(url, {"confirm": "Confirm"}, format="json")
    assert done.status_code == 200, done.content
    assert done.json()["erased"]["Orders"] == 1 and Order.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_real_backup_runs_before_the_erase(settings, tmp_path, owner, customer):
    pytest.importorskip("xlrd")  # any installed dependency; pg_dump is checked below
    from apps.system.services import _bin

    try:
        _bin("pg_dump")
    except RuntimeError:
        pytest.skip("pg_dump not installed")
    settings.BACKUP_DIR = tmp_path
    settings.RCLONE_REMOTE = ""
    result = erase.erase_business_data(user=owner, confirm="Confirm")
    assert result["backup_file"].endswith(".dump")
    assert (tmp_path / "sets").exists() and Customer.objects.count() == 0
