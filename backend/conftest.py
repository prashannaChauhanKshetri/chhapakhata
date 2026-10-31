"""Shared pytest fixtures: users per role, a small rate card, stock and customers."""

from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import AddOn, AddOnBasis, MediaType
from apps.core.models import ShopSettings
from apps.core.permissions import Role
from apps.customers.models import Customer
from apps.inventory import services as stock
from apps.inventory.models import StockItem, StockKind, StockUnit, Supplier
from apps.orders import services as orders
from apps.tenancy.context import use_business
from apps.tenancy.models import Business

D = Decimal


DB_FIXTURES = {"db", "transactional_db", "django_db_setup"}


@pytest.fixture(autouse=True)
def business(request):
    """Database tests run inside one business, like a signed-in request.

    The first business comes from the migrations; transactional tests flush
    it, so it is created again when missing.
    """
    names = set(request.fixturenames)
    if not names & DB_FIXTURES and not request.node.get_closest_marker("django_db"):
        yield None
        return
    marker = request.node.get_closest_marker("django_db")
    transactional = "transactional_db" in names or (
        marker is not None and marker.kwargs.get("transaction")
    )
    request.getfixturevalue("transactional_db" if transactional else "db")
    current = Business.objects.order_by("pk").first() or Business.objects.create(
        name="OM Traders and Suppliers", slug="om-traders-and-suppliers"
    )
    with use_business(current):
        yield current


def make_user(username: str, role: str, **extra) -> User:
    user = User(username=username, role=role, first_name=username.title(), **extra)
    user.set_password("Test@12345")
    user.save()
    return user


@pytest.fixture
def owner(db) -> User:
    return make_user("owner", Role.OWNER)


@pytest.fixture
def desk(db) -> User:
    return make_user("desk", Role.FRONT_DESK)


@pytest.fixture
def operator(db) -> User:
    return make_user("operator", Role.OPERATOR)


@pytest.fixture
def shop(db) -> ShopSettings:
    shop = ShopSettings.load()
    shop.is_vat_registered = True
    shop.vat_rate = D("13")
    shop.default_min_sqft = D("5")
    shop.save()
    return shop


@pytest.fixture
def star_flex_stock(db) -> StockItem:
    return StockItem.objects.create(
        name="Star Flex", kind=StockKind.ROLL_MEDIA, unit=StockUnit.SQFT, low_stock_level=D("100")
    )


@pytest.fixture
def supplier(db) -> Supplier:
    return Supplier.objects.create(name="Test Supplier")


@pytest.fixture
def star_flex_rolls(owner, star_flex_stock, supplier):
    """Two Star Flex rolls: 10 × 100 ft (1,000 sq ft) and 5 × 50 ft (250 sq ft)."""
    stock.receive_purchase(
        user=owner,
        supplier=supplier,
        purchase_date=__import__("datetime").date.today(),
        lines=[
            {
                "stock_item": star_flex_stock,
                "roll_count": 1,
                "roll_width_ft": D("10"),
                "roll_length_ft": D("100"),
                "amount": D("9000"),
            },
            {
                "stock_item": star_flex_stock,
                "roll_count": 1,
                "roll_width_ft": D("5"),
                "roll_length_ft": D("50"),
                "amount": D("2250"),
            },
        ],
    )
    return list(star_flex_stock.rolls.order_by("-width_ft"))


@pytest.fixture
def star_flex(db, star_flex_stock) -> MediaType:
    return MediaType.objects.create(name="Star Flex", rate=D("35"), material=star_flex_stock)


@pytest.fixture
def vinyl(db) -> MediaType:
    return MediaType.objects.create(name="Vinyl", rate=D("70"), min_sqft=D("2"))


@pytest.fixture
def eyelets(db) -> AddOn:
    return AddOn.objects.create(
        name="Eyelets", basis=AddOnBasis.PER_PIECE, rate=D("5"), default_quantity=D("8")
    )


@pytest.fixture
def framing(db) -> AddOn:
    return AddOn.objects.create(name="Framing", basis=AddOnBasis.PER_RUNNING_FT, rate=D("60"))


@pytest.fixture
def customer(db) -> Customer:
    return Customer.objects.create(name="Hotel Kalpana", phone="9858020005", pan_no="304567890")


@pytest.fixture
def make_order(shop, desk, customer, star_flex):
    """Create an order: ``make_order(confirm=True, items=[(w, h, qty), ...])``."""

    def _make(*, items=None, confirm=True, user=None, media=None, **kwargs):
        items = items or [(D("10"), D("4"), 1)]
        data = orders.OrderInput(
            items=[
                orders.ItemInput(
                    media_type=media or star_flex, width=w, height=h, unit="ft", quantity=q
                )
                for (w, h, q) in items
            ]
        )
        return orders.create_order(
            user=user or desk,
            customer=kwargs.pop("customer", customer),
            data=data,
            confirm=confirm,
            **kwargs,
        )

    return _make


@pytest.fixture
def api():
    def _client(user=None) -> APIClient:
        client = APIClient()
        if user is not None:
            # A real session, so BusinessMiddleware scopes requests to the user's business.
            client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
        return client

    return _client
