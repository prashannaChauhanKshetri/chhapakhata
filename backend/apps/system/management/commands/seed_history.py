"""Simulate a print shop's whole history, from the day it opened until today.

Meant for an empty, separate database (``make history``). It starts on
1 Shrawan 2077 BS with only the new owner and a small rate card, then plays
out every working day: customers arrive, orders are priced, designed,
printed and delivered, rolls are bought and used up, staff are hired and
leave, rates rise each fiscal year, and money comes in by cash and, more and
more, by wallet.

Every event runs through the normal service functions with the clock set to
that moment, in date order, so invoice and receipt numbers, the ledger,
stock and the audit trail are exactly what real use would have produced.
The names, phone numbers and PAN numbers are invented.

    uv run python manage.py seed_history            # about 6 years
    uv run python manage.py seed_history --until 2078-04-01   # shorter, for a quick look
"""

from __future__ import annotations

import datetime as dt
import heapq
import itertools
import random
import time
from collections import Counter
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from unittest import mock

from django.core.management.base import CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.billing import services as billing
from apps.billing.models import Invoice, InvoiceStatus, Payment, PaymentMode
from apps.billing.selectors import balance_subquery, customer_balance, order_paid_amount
from apps.catalog.models import AddOn, AddOnBasis, MediaType, PricingUnit
from apps.core.dates import fiscal_year_for, from_bs, to_bs
from apps.core.exceptions import BusinessError
from apps.core.models import ShopSettings
from apps.core.permissions import Role
from apps.customers.models import Customer, CustomerType
from apps.inventory import services as stock
from apps.inventory.models import Roll, RollStatus, StockItem, StockKind, StockUnit, Supplier
from apps.orders import services as orders
from apps.orders.models import Order, OrderStatus
from apps.production.models import Stage
from apps.production.services import move_job, needs_material
from apps.tenancy.commands import BusinessCommand

D = Decimal
OPENING_BS = (2077, 4, 1)  # 1 Shrawan 2077: first day of FY 2077/78

# ---------- the shop's story ----------

STAFF = [
    # username, first, last, role, joined (BS), left (BS) or None
    ("hari", "Hari", "Bhandari", Role.OPERATOR, (2077, 5, 1), (2080, 3, 30)),
    ("sunita", "Sunita", "Karki", Role.FRONT_DESK, (2078, 1, 1), None),
    ("kamal", "Kamal", "Tharu", Role.OPERATOR, (2080, 3, 15), None),
    ("anjali", "Anjali", "Gupta", Role.FRONT_DESK, (2081, 4, 1), None),
    ("suresh", "Suresh", "Yadav", Role.OPERATOR, (2082, 4, 1), None),
]

# Rate card by fiscal year (start year): (name, unit, rate by year, stock item, first year offered)
RATE_CARD = [
    (
        "Star Flex",
        PricingUnit.SQFT,
        {2077: 25, 2078: 28, 2079: 30, 2080: 32, 2081: 33, 2082: 35},
        "Star Flex",
        2077,
    ),
    (
        "Normal Flex",
        PricingUnit.SQFT,
        {2077: 18, 2078: 20, 2079: 22, 2080: 23, 2081: 24, 2082: 25},
        "Normal Flex",
        2077,
    ),
    (
        "Vinyl",
        PricingUnit.SQFT,
        {2077: 55, 2078: 60, 2079: 62, 2080: 65, 2081: 68, 2082: 70},
        "Vinyl",
        2077,
    ),
    (
        "Sticker",
        PricingUnit.SQFT,
        {2077: 45, 2078: 48, 2079: 50, 2080: 52, 2081: 55, 2082: 55},
        "Sticker",
        2077,
    ),
    (
        "Backlit",
        PricingUnit.SQFT,
        {2078: 50, 2079: 55, 2080: 58, 2081: 60, 2082: 60},
        "Backlit Flex",
        2078,
    ),
    ("One-way Vision", PricingUnit.SQFT, {2080: 75, 2081: 80, 2082: 80}, "One-way Vision", 2080),
    (
        "Normal Photo",
        PricingUnit.PIECE,
        {2077: 120, 2078: 130, 2079: 140, 2080: 150, 2081: 160, 2082: 160},
        None,
        2077,
    ),
    (
        "Name Plate",
        PricingUnit.PIECE,
        {2078: 450, 2079: 500, 2080: 550, 2081: 600, 2082: 600},
        None,
        2078,
    ),
    ("3D Letters", PricingUnit.PIECE, {2080: 1000, 2081: 1100, 2082: 1200}, None, 2080),
    ("Acrylic Name Plate", PricingUnit.PIECE, {2081: 1000, 2082: 1100}, None, 2081),
]

ROLL_MEDIA = {
    # stock item: (roll widths ft, roll length ft, purchase rate per sq ft by year)
    "Star Flex": ((5, 10), 164, {2077: 9, 2078: 10, 2079: 11, 2080: 11.5, 2081: 12, 2082: 12.5}),
    "Normal Flex": (
        (5, 6, 10),
        164,
        {2077: 6.5, 2078: 7, 2079: 7.5, 2080: 8, 2081: 8.2, 2082: 8.5},
    ),
    "Vinyl": ((4,), 150, {2077: 22, 2078: 24, 2079: 25, 2080: 26, 2081: 27, 2082: 28}),
    "Sticker": ((4,), 150, {2077: 18, 2078: 19, 2079: 20, 2080: 21, 2081: 22, 2082: 22}),
    "Backlit Flex": ((5, 10), 164, {2078: 16, 2079: 17, 2080: 18, 2081: 19, 2082: 20}),
    "One-way Vision": ((4,), 150, {2080: 30, 2081: 32, 2082: 33}),
}

# Average orders per working day by fiscal year, before seasons.
DAILY_ORDERS = {2077: 2.6, 2078: 3.8, 2079: 5.2, 2080: 6.2, 2081: 7.2, 2082: 8.2, 2083: 8.8}
# BS month: Baisakh … Chaitra
SEASON = {
    1: 1.35,
    2: 1.15,
    3: 0.75,
    4: 0.75,
    5: 0.9,
    6: 1.6,
    7: 1.45,
    8: 1.1,
    9: 0.9,
    10: 1.0,
    11: 1.1,
    12: 1.25,
}

FIRST = [
    "Ram",
    "Sita",
    "Hari",
    "Gita",
    "Krishna",
    "Laxmi",
    "Bishnu",
    "Sarita",
    "Ramesh",
    "Sunita",
    "Dipak",
    "Anita",
    "Suman",
    "Puja",
    "Rajendra",
    "Kamala",
    "Bikash",
    "Manisha",
    "Santosh",
    "Rekha",
    "Prakash",
    "Nirmala",
    "Dinesh",
    "Saraswati",
    "Mohan",
    "Bimala",
    "Arjun",
    "Sabina",
    "Naresh",
    "Kiran",
]
LAST = [
    "Tharu",
    "Sharma",
    "Gupta",
    "Yadav",
    "Khan",
    "Shah",
    "Chaudhary",
    "Pandey",
    "Oli",
    "Thapa",
    "Bhandari",
    "Karki",
    "Rawal",
    "Shrestha",
    "Ansari",
    "Jaiswal",
    "Poudel",
    "Gurung",
    "BK",
    "Kurmi",
]
PLACES = [
    "Nepalgunj-1",
    "Nepalgunj-4",
    "Nepalgunj-8",
    "Nepalgunj-12",
    "Kohalpur",
    "Khajura",
    "Rapti Pari",
    "Gulariya",
    "Bhurigaun",
    "Tulsipur",
    "Ghorahi",
    "Sitapur, Bardiya",
    "Rajhena",
    "Dhamboji",
    "Surkhet Road",
    "BP Chowk",
    "Ranjha",
    "Jaispur",
    "Kalaphanta",
    "Puraina",
]
BUSINESS_KINDS = [
    ("{} Secondary School", 0.12),
    ("{} Academy", 0.08),
    ("{} Hospital", 0.05),
    ("{} Medical Hall", 0.07),
    ("{} Hotel", 0.06),
    ("{} Traders", 0.1),
    ("{} Electronics", 0.06),
    ("{} Suppliers", 0.06),
    ("{} Cooperative", 0.06),
    ("{} Youth Club", 0.06),
    ("{} Digital Studio", 0.05),
    ("{} Fancy Store", 0.05),
    ("{} Restaurant", 0.05),
    ("{} Campus", 0.04),
    ("{} Agro Center", 0.04),
    ("{} Mobile Shop", 0.05),
]
BUSINESS_WORDS = [
    "Bheri",
    "Rapti",
    "Karnali",
    "Banke",
    "Mahakali",
    "Shiva",
    "Laxmi",
    "Siddhartha",
    "Gorkha",
    "Janata",
    "Sagarmatha",
    "Om",
    "Saraswati",
    "Ganesh",
    "Himalaya",
    "Navajyoti",
    "Pashupati",
    "Bageshwori",
    "Narayan",
    "Kamana",
    "Prabhat",
    "Sunrise",
    "Everest",
    "Mangal",
]
DESCRIPTIONS = {
    "Star Flex": [
        "Shop banner",
        "Admission open",
        "Wedding backdrop",
        "Dashain greetings",
        "Event backdrop",
        "Grand opening",
        "Notice",
        "Puja banner",
        "Sale banner",
    ],
    "Normal Flex": ["Notice", "Program banner", "Rally banner", "Condolence banner", "Price list"],
    "Vinyl": ["Signboard", "Glass branding", "Vehicle branding", "Door sign"],
    "Sticker": ["Product labels", "Car sticker", "Logo stickers", "Shutter sticker"],
    "Backlit": ["Glow sign board", "Shop front glow sign", "Pharmacy glow sign"],
    "One-way Vision": ["Glass door", "Shop window"],
    "Normal Photo": ["Passport size", "Family photo", "Certificate photo"],
    "Name Plate": ["House name plate", "Office name plate"],
    "3D Letters": ["Shop front letters", "Reception letters"],
    "Acrylic Name Plate": ["Door name plate", "Desk name plate"],
}
SIZES = [  # (width, height, unit, weight)
    (D("10"), D("4"), "ft", 6),
    (D("6"), D("3"), "ft", 8),
    (D("3"), D("2"), "ft", 6),
    (D("8"), D("4"), "ft", 5),
    (D("12"), D("4"), "ft", 3),
    (D("5"), D("3"), "ft", 5),
    (D("24"), D("36"), "in", 4),
    (D("12"), D("18"), "in", 4),
    (D("20"), D("6"), "ft", 1),
    (D("4"), D("2.5"), "ft", 4),
    (D("8"), D("8"), "ft", 1),
]


@contextmanager
def travel_to(moment: dt.datetime):
    with mock.patch("django.utils.timezone.now", return_value=moment):
        yield


@dataclass
class Person:
    """A customer and how they behave."""

    customer: Customer
    regular: bool
    weight: float
    pays_on_delivery: float  # chance of settling in full at delivery
    rate_cut: Decimal = Decimal(0)  # negotiated discount on the rate card, for regulars
    slow: bool = False


@dataclass(order=True)
class Event:
    at: dt.datetime
    seq: int
    action: Callable[[], None] = field(compare=False)


class Command(BusinessCommand):
    help = "Simulate the shop from its first day (1 Shrawan 2077 BS) until today, in an empty database."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="Shop@2077", help="Password for every account")
        parser.add_argument("--until", help="Stop at this AD date (default: today)")
        parser.add_argument("--scale", type=float, default=1.0, help="Multiply order volume")
        parser.add_argument("--seed", type=int, default=2077)

    # -- entry -----------------------------------------------------------------

    def handle(self, *args, **options):
        if Order.objects.exists() or User.objects.filter(business=self.business).exists():
            raise CommandError(
                f"The business '{self.business.slug}' is not empty. Use a new business "
                "(manage.py create_business) or a fresh database (`make history`)."
            )
        self.rng = random.Random(options["seed"])
        self.tz = timezone.get_current_timezone()
        self.password = options["password"]
        self.scale = options["scale"]
        self.opening = from_bs(*OPENING_BS)
        self.until = (
            dt.date.fromisoformat(options["until"]) if options["until"] else timezone.localdate()
        )
        self.now = timezone.make_aware(dt.datetime.combine(self.until, dt.time(15, 30)), self.tz)
        if self.until <= self.opening:
            raise CommandError("--until must be after the opening day.")

        self.queue: list[Event] = []
        self.counter = itertools.count()
        self.people: list[Person] = []
        self.staff: dict[str, User] = {}
        self.stats: dict[str, int] = {"orders": 0, "skipped": 0}
        self.skipped: Counter[str] = Counter()
        with connection.cursor() as cursor:
            # A one-off build: skip waiting for each commit to reach the disk.
            cursor.execute("SET synchronous_commit TO OFF")
        started = time.monotonic()

        self._open_shop()
        self._schedule_calendar()
        self._run()

        took = time.monotonic() - started
        self.stdout.write(
            self.style.SUCCESS(
                f"History ready: {self.stats['orders']} orders, {Customer.objects.count()} customers, "
                f"{Invoice.objects.count()} invoices, {Payment.objects.count()} receipts "
                f"from {self.opening} to {self.until} in {took / 60:.1f} min."
            )
        )
        if self.stats["skipped"]:
            self.stdout.write(
                f"{self.stats['skipped']} events stopped by business rules, as in real use:"
            )
            for reason, n in self.skipped.most_common(5):
                self.stdout.write(f"  {n} × {reason}")
        self.stdout.write(
            f"Sign in as newowner (owner), sunita / anjali (front desk), kamal / suresh (operators); "
            f"password '{self.password}'. Hari (operator 2077–2080) has left and cannot sign in."
        )

    # -- clock helpers -----------------------------------------------------------

    def at(self, day: dt.date, hour: int, minute: int = 0) -> dt.datetime:
        return timezone.make_aware(dt.datetime.combine(day, dt.time(hour, minute)), self.tz)

    def schedule(self, moment: dt.datetime, action: Callable[[], None]) -> None:
        if moment <= self.now:
            heapq.heappush(self.queue, Event(moment, next(self.counter), action))

    def fy(self, day: dt.date) -> int:
        return int(fiscal_year_for(day).split("/")[0])

    def is_open(self, day: dt.date) -> bool:
        if day.weekday() == 5:  # Saturday
            return False
        if day >= self.until - dt.timedelta(days=4):
            return True  # keep the last few days busy, so the app shows a working week
        bs = to_bs(day)
        # Dashain (late Asoj) and Tihar (mid Kartik): a few days closed.
        return not ((bs.month == 6 and bs.day >= 26) or (bs.month == 7 and 12 <= bs.day <= 14))

    # -- day one -----------------------------------------------------------------

    def _open_shop(self):
        with travel_to(self.at(self.opening, 8, 30)), transaction.atomic():
            shop = ShopSettings.load()
            shop.name = "OM Traders and Suppliers"
            shop.tagline = "Flex printing · Signage · 2D/3D boards · Glow signs"
            shop.address = "Nepalgunj-12, Banke, Nepal"
            shop.phone = "081-000000"
            shop.pan_vat_number = "609999999"
            shop.is_vat_registered = False  # registers for VAT from FY 2079/80
            shop.round_total_to_rupee = True  # bills are rounded to the rupee, as at the counter
            shop.save()

            owner = User(
                username="newowner",
                first_name="Anil",
                last_name="Pokhrel",
                role=Role.OWNER,
                date_joined=timezone.now(),
            )
            owner.set_password(self.password)
            owner.save()
            self.owner = owner

            self.suppliers = [
                Supplier.objects.create(name="Kathmandu Flex House", phone="01-0000001"),
                Supplier.objects.create(name="Birgunj Print Suppliers", phone="051-000002"),
                Supplier.objects.create(name="Nepalgunj Sign Materials", phone="081-000003"),
            ]
            self.items: dict[str, StockItem] = {}
            for name in ROLL_MEDIA:
                self.items[name] = StockItem.objects.create(
                    name=name,
                    kind=StockKind.ROLL_MEDIA,
                    unit=StockUnit.SQFT,
                    low_stock_level=D("300"),
                    is_active=name in ("Star Flex", "Normal Flex", "Vinyl", "Sticker"),
                )
            self.ink = StockItem.objects.create(
                name="Eco-solvent ink",
                kind=StockKind.INK,
                unit=StockUnit.LITRE,
                low_stock_level=D("2"),
            )
            self.eyelet_stock = StockItem.objects.create(
                name="Eyelets", kind=StockKind.EYELETS, unit=StockUnit.BOX, low_stock_level=D("2")
            )
            self.media: dict[str, MediaType] = {}
            for order_no, (name, unit, rates, item, first_year) in enumerate(RATE_CARD):
                self.media[name] = MediaType.objects.create(
                    name=name,
                    pricing_unit=unit,
                    rate=D(str(rates.get(2077, next(iter(rates.values()))))),
                    material=self.items.get(item) if item else None,
                    is_active=first_year <= 2077,
                    sort_order=order_no,
                )
            self.addons = {
                "design": AddOn.objects.create(
                    name="Design / editing", basis=AddOnBasis.FIXED, rate=D("300")
                ),
                "eyelets": AddOn.objects.create(
                    name="Eyelets", basis=AddOnBasis.PER_PIECE, rate=D("5"), default_quantity=D("8")
                ),
                "framing": AddOn.objects.create(
                    name="Framing", basis=AddOnBasis.PER_RUNNING_FT, rate=D("50")
                ),
                "lamination": AddOn.objects.create(
                    name="Lamination", basis=AddOnBasis.PER_SQFT, rate=D("12")
                ),
                "urgent": AddOn.objects.create(
                    name="Urgent (same day)", basis=AddOnBasis.PERCENT, rate=D("20")
                ),
            }
            # Opening stock: what the owner bought to start the shop.
            self._buy(self.opening, ["Star Flex", "Normal Flex", "Vinyl", "Sticker"], rolls_each=2)
            stock.receive_purchase(
                user=self.owner,
                supplier=self.suppliers[0],
                purchase_date=self.opening,
                bill_no="KFH-0001",
                lines=[
                    {"stock_item": self.ink, "quantity": D("8"), "amount": D("24000")},
                    {"stock_item": self.eyelet_stock, "quantity": D("10"), "amount": D("3500")},
                ],
            )

    # -- the calendar ---------------------------------------------------------------

    def _schedule_calendar(self):
        day = self.opening
        while day <= self.until:
            bs = to_bs(day)
            if bs.month == 4 and bs.day == 1 and day != self.opening:
                self.schedule(self.at(day, 8, 0), lambda d=day: self._new_fiscal_year(d))
            for username, first, last, role, joined, left in STAFF:
                if from_bs(*joined) == day:
                    self.schedule(
                        self.at(day, 8, 15),
                        lambda u=username, f=first, la=last, r=role: self._hire(u, f, la, r),
                    )
                if left and from_bs(*left) == day:
                    self.schedule(self.at(day, 18, 0), lambda u=username: self._leave(u))
            if self.is_open(day):
                self.schedule(self.at(day, 9, 30), lambda d=day: self._open_day(d))
            day += dt.timedelta(days=1)

    def _run(self):
        last_month = None
        while self.queue:
            event = heapq.heappop(self.queue)
            month = (event.at.year, event.at.month)
            if month != last_month:
                last_month = month
                bs = to_bs(event.at.date())
                self.stdout.write(
                    f"  {bs.year}-{bs.month:02d} BS · {self.stats['orders']} orders so far"
                )
            with travel_to(event.at):
                try:
                    with transaction.atomic():
                        event.action()
                except BusinessError as exc:
                    self.stats["skipped"] += 1
                    self.skipped[str(exc.detail)[:120]] += 1

    # -- yearly and staff events ------------------------------------------------------

    def _new_fiscal_year(self, day: dt.date):
        year = self.fy(day)
        for name, _unit, rates, _item, first_year in RATE_CARD:
            media = self.media[name]
            if year in rates:
                media.rate = D(str(rates[year]))
            media.is_active = first_year <= year
            media.save()
        for name in ROLL_MEDIA:
            item = self.items[name]
            if not item.is_active and any(r[3] == name and r[4] <= year for r in RATE_CARD):
                item.is_active = True
                item.save()
        if year >= 2079:
            shop = ShopSettings.load()
            if not shop.is_vat_registered:
                shop.is_vat_registered = True
                shop.save()
        if year >= 2080:
            self.addons["design"].rate = D("500")
            self.addons["design"].save()

    def _hire(self, username: str, first: str, last: str, role: str):
        user = User(
            username=username,
            first_name=first,
            last_name=last,
            role=role,
            date_joined=timezone.now(),
        )
        user.set_password(self.password)
        user.save()
        self.staff[username] = user

    def _leave(self, username: str):
        user = self.staff.pop(username)
        user.is_active = False
        user.save()

    def desk(self) -> User:
        desks = [u for u in self.staff.values() if u.role == Role.FRONT_DESK]
        return self.rng.choice(desks) if desks else self.owner

    def operator(self) -> User:
        ops = [u for u in self.staff.values() if u.role == Role.OPERATOR]
        return self.rng.choice(ops) if ops else self.owner

    # -- a working day ------------------------------------------------------------------

    def _open_day(self, day: dt.date):
        year, bs = self.fy(day), to_bs(day)
        rate = DAILY_ORDERS.get(year, 9.0) * SEASON[bs.month] * self.scale
        if bs.year == 2077 and bs.month in (4, 5):  # Covid restrictions after reopening
            rate *= 0.6
        if bs.year == 2078 and bs.month in (1, 2):  # second lockdown, Baisakh–Jestha 2078
            rate *= 0.25
        if bs.year == 2079 and bs.month in (7, 8):  # election campaign, Kartik–Mangsir 2079
            rate *= 2.2
        count = self._poisson(rate)
        for minute in sorted(self.rng.sample(range(10 * 60, 17 * 60 + 30, 5), min(count, 90))):
            self.schedule(
                self.at(day, minute // 60, minute % 60), lambda d=day: self._customer_walks_in(d)
            )
        # Regulars pay something towards old dues now and then.
        self.schedule(self.at(day, 16, 40), self._collect_dues)
        # Weekly stock check (Sunday) and monthly ink use.
        if day.weekday() == 6:
            self.schedule(self.at(day, 9, 45), lambda d=day: self._restock(d))
        if bs.day <= 2 and day.weekday() != 5:
            self.schedule(self.at(day, 17, 50), self._month_end)

    def _poisson(self, lam: float) -> int:
        # Knuth's method; fine for the small rates here.
        limit, k, p = pow(2.718281828, -lam), 0, 1.0
        while True:
            p *= self.rng.random()
            if p <= limit:
                return k
            k += 1

    # -- customers ------------------------------------------------------------------------

    def _new_person(self, day: dt.date) -> Person:
        regular = self.rng.random() < 0.2
        place = self.rng.choice(PLACES)
        if regular:
            template = self.rng.choices(
                [k for k, _ in BUSINESS_KINDS], weights=[w for _, w in BUSINESS_KINDS]
            )[0]
            name = template.format(self.rng.choice(BUSINESS_WORDS))
            kind = CustomerType.BUSINESS
            pan = f"{self.rng.randint(300000000, 699999999)}" if self.rng.random() < 0.6 else ""
        else:
            name = f"{self.rng.choice(FIRST)} {self.rng.choice(LAST)}"
            kind = CustomerType.INDIVIDUAL
            pan = ""
        if Customer.objects.filter(name=name).exists():
            name = f"{name} ({place.split(',')[0]})"
        customer = Customer.objects.create(
            name=name,
            phone=f"98{self.rng.choice([4, 5, 6])}{self.rng.randint(1000000, 9999999)}"
            if self.rng.random() < 0.85
            else "",
            address=place,
            pan_no=pan,
            customer_type=kind,
            created_by=self.desk(),
        )
        person = Person(
            customer=customer,
            regular=regular,
            weight=self.rng.uniform(3, 12) if regular else 1.0,
            pays_on_delivery=self.rng.uniform(0.15, 0.55) if regular else 0.95,
            rate_cut=D(str(self.rng.choice([0, 0, 4, 5, 6, 8]))) if regular else D("0"),
            slow=regular and self.rng.random() < 0.18,
        )
        self.people.append(person)
        return person

    def _pick_person(self, day: dt.date) -> Person:
        new_share = 0.55 if len(self.people) < 40 else 0.22
        if not self.people or self.rng.random() < new_share:
            return self._new_person(day)
        return self.rng.choices(self.people, weights=[p.weight for p in self.people])[0]

    # -- an order, from counter to delivery ---------------------------------------------------

    def _items(self, person: Person, day: dt.date) -> list[orders.ItemInput]:
        active = [m for m in self.media.values() if m.is_active]
        weights = {
            "Star Flex": 30,
            "Normal Flex": 18,
            "Vinyl": 10,
            "Sticker": 8,
            "Backlit": 7,
            "One-way Vision": 2,
            "Normal Photo": 9,
            "Name Plate": 3,
            "3D Letters": 2,
            "Acrylic Name Plate": 2,
        }
        bs = to_bs(day)
        if bs.year == 2079 and bs.month in (7, 8):
            weights["Normal Flex"] = 60  # election banners
        items = []
        for _ in range(self.rng.choices([1, 2, 3], weights=[70, 22, 8])[0]):
            media = self.rng.choices(active, weights=[weights.get(m.name, 1) for m in active])[0]
            addons = []
            if media.pricing_unit == PricingUnit.PIECE:
                width = height = D("0")
                unit = "ft"
                qty = (
                    self.rng.choice([1, 1, 2, 4, 6])
                    if media.name == "Normal Photo"
                    else self.rng.choice([1, 1, 2])
                )
            else:
                width, height, unit, _ = self.rng.choices(SIZES, weights=[s[3] for s in SIZES])[0]
                if (
                    media.name in ("Vinyl", "Sticker", "One-way Vision")
                    and min(width, height) > 4
                    and unit == "ft"
                ):
                    width, height = D("4"), D("3")
                qty = self.rng.choices([1, 2, 3, 5, 10], weights=[70, 14, 6, 6, 4])[0]
                if media.name in ("Star Flex", "Normal Flex") and self.rng.random() < 0.55:
                    addons.append(orders.AddOnInput(addon=self.addons["eyelets"], quantity=D("8")))
                if media.name == "Backlit" and self.rng.random() < 0.8:
                    addons.append(orders.AddOnInput(addon=self.addons["framing"], quantity=D("1")))
                if media.name == "Sticker" and self.rng.random() < 0.3:
                    addons.append(
                        orders.AddOnInput(addon=self.addons["lamination"], quantity=D("1"))
                    )
            if self.rng.random() < 0.22:
                addons.append(orders.AddOnInput(addon=self.addons["design"], quantity=D("1")))
            rate = None
            if person.rate_cut:
                rate = (media.rate * (D("100") - person.rate_cut) / D("100")).quantize(D("1"))
            items.append(
                orders.ItemInput(
                    media_type=media,
                    width=width,
                    height=height,
                    unit=unit,
                    quantity=qty,
                    rate=rate,
                    description=self.rng.choice(DESCRIPTIONS.get(media.name, [""])),
                    finishing=self.rng.choice(
                        ["", "", "Hemmed edges", "Wooden frame", "Pasting on board"]
                    )
                    if media.pricing_unit == PricingUnit.SQFT
                    else "",
                    addons=addons,
                )
            )
        return items

    def _customer_walks_in(self, day: dt.date):
        person = self._pick_person(day)
        clerk = self.desk()
        now = timezone.now()
        quotation_only = self.rng.random() < 0.06
        discount = (
            ("percent", D(str(self.rng.choice([2, 5, 5, 10]))))
            if self.rng.random() < 0.12
            else ("none", D("0"))
        )
        items = self._items(person, day)
        needs_proof = any(
            a.addon.pk == self.addons["design"].pk for item in items for a in item.addons
        )
        urgent = not needs_proof and self.rng.random() < 0.08
        lead_days = (
            0 if urgent else self.rng.choices([0, 1, 2, 3, 5], weights=[15, 40, 25, 12, 8])[0]
        )
        if needs_proof:
            lead_days = max(lead_days, 2)  # the customer approves the design first
        promise = day + dt.timedelta(days=lead_days)
        while not self.is_open(promise) and promise < self.until:
            promise += dt.timedelta(days=1)  # never promise a day the shop is closed
        deadline = max(self.at(promise, 17, 0), now + dt.timedelta(hours=2))
        order = orders.create_order(
            user=clerk,
            customer=person.customer,
            data=orders.OrderInput(
                items=items,
                discount_type=discount[0],
                discount_value=discount[1],
            ),
            deadline=deadline,
            is_urgent=urgent,
            confirm=not quotation_only,
        )
        self.stats["orders"] += 1
        if quotation_only:
            # Most quotations are confirmed after a day or two; some never come back.
            if self.rng.random() < 0.6:
                self.schedule(
                    now + dt.timedelta(days=self.rng.choice([1, 2, 3]), hours=1),
                    lambda o=order: self._confirm(o),
                )
            else:
                self.schedule(now + dt.timedelta(days=30), lambda o=order: self._expire(o))
            return
        self._after_confirm(order, person, now, deadline)

    def _confirm(self, order: Order):
        order.refresh_from_db()
        if order.status != OrderStatus.QUOTATION:
            return
        orders.confirm_order(order=order, user=self.desk())
        person = next(p for p in self.people if p.customer.pk == order.customer_id)
        now = timezone.now()
        self._after_confirm(order, person, now, now + dt.timedelta(days=2))

    def _expire(self, order: Order):
        order.refresh_from_db()
        if order.status == OrderStatus.QUOTATION:
            orders.cancel_order(
                order=order, user=self.owner, reason="Customer did not confirm the quotation"
            )

    def _after_confirm(self, order: Order, person: Person, now: dt.datetime, deadline: dt.datetime):
        if self.rng.random() < 0.02:  # changed their mind
            self.schedule(now + dt.timedelta(hours=2), lambda: self._cancel(order))
            return
        if not person.regular and self.rng.random() < 0.45:
            advance = (order.total * D(str(self.rng.choice([0.3, 0.5, 0.5, 1.0])))).quantize(D("1"))
            if advance > 0:
                billing.receive_payment(
                    user=self.desk(),
                    customer=person.customer,
                    order=order,
                    amount=advance,
                    **self._mode(person),
                )
        # Production, one step after another: design approved, printed, finished,
        # ready, then collected. Each step schedules the next once it is done.
        needs_proof = any(
            i.addons.filter(name="Design / editing").exists() for i in order.items.all()
        )
        # Work back from the promise: most jobs are ready a little before the
        # deadline, about one in ten runs late.
        start = now + dt.timedelta(hours=20.0 if needs_proof else self.rng.uniform(0.2, 1.0))
        if self.rng.random() < 0.1:
            ready_at = deadline + dt.timedelta(hours=self.rng.uniform(2, 30))
        else:
            ready_at = deadline - dt.timedelta(hours=self.rng.uniform(0.5, 4))
        ready_at = max(ready_at, start + dt.timedelta(hours=1))
        span = ready_at - start
        plan = [
            (Stage.READY_FOR_PRINT, start),
            (Stage.PRINTING, start + span * 0.4),
            (Stage.FINISHING, start + span * 0.75),
            (Stage.READY, ready_at),
        ]
        self._next_step(order, person, plan, now)

    def _next_step(self, order: Order, person: Person, plan: list, after: dt.datetime):
        if not plan:
            pickup = after + dt.timedelta(hours=self.rng.choice([0.5, 1, 3, 20, 26, 48, 70]))
            self.schedule(self._working_hours(pickup), lambda: self._deliver(order, person))
            return
        stage, target = plan[0]
        when = self._working_hours(max(target, after + dt.timedelta(minutes=5)))
        self.schedule(when, lambda: self._do_step(order, person, stage, plan[1:]))

    def _do_step(self, order: Order, person: Person, stage: int, rest: list):
        order.refresh_from_db()
        if order.status == OrderStatus.CANCELLED:
            return
        self._stage(order, stage)
        self._next_step(order, person, rest, timezone.now())

    def _working_hours(self, moment: dt.datetime) -> dt.datetime:
        local = timezone.localtime(moment)
        day = local.date()
        if local.hour >= 18:
            day += dt.timedelta(days=1)
            local = self.at(day, 10, self.rng.randint(0, 50))
        elif local.hour < 9:
            local = self.at(day, 9, self.rng.randint(30, 59))
        while not self.is_open(local.date()) and local.date() <= self.until:
            local = self.at(local.date() + dt.timedelta(days=1), 10, self.rng.randint(0, 50))
        return local

    def _cancel(self, order: Order):
        orders.cancel_order(
            order=order,
            user=self.desk(),
            reason=self.rng.choice(
                ["Customer changed the design", "Program postponed", "Ordered elsewhere"]
            ),
        )

    def _stage(self, order: Order, to_stage: int):
        for job in order.jobs.exclude(stage__in=[Stage.CANCELLED, Stage.DELIVERED]):
            if job.stage >= to_stage:
                continue
            actor = self.desk() if to_stage == Stage.READY_FOR_PRINT else self.operator()
            material = None
            if needs_material(job, to_stage):
                material = self._material(job)
                if material is None:
                    actor = self.owner  # only the owner may skip recording material
            move_job(
                job=job,
                user=actor,
                to_stage=to_stage,
                material=material,
                skip_material=material is None and actor == self.owner,
            )

    def _material(self, job) -> dict[str, Any] | None:
        item = job.order_item.media_type.material
        if item is None:
            return None
        need = (job.order_item.sqft * job.order_item.quantity).quantize(D("0.01"))
        if need <= 0:
            return None
        short = min(job.order_item.width_ft, job.order_item.height_ft)
        waste = D("0") if self.rng.random() < 0.75 else D(str(self.rng.choice([1, 2, 3, 5, 8])))
        for attempt in range(2):
            roll = (
                Roll.objects.filter(
                    stock_item=item,
                    status=RollStatus.ACTIVE,
                    remaining_sqft__gte=need + waste + 1,
                    width_ft__gte=short,
                )
                .order_by("width_ft", "remaining_sqft")
                .first()
            )
            if roll is not None:
                return {
                    "roll": roll,
                    "used_sqft": need + D("1"),
                    "wastage_sqft": waste,
                    "wastage_reason": self.rng.choice(["Test print", "Colour mismatch", "Misprint"])
                    if waste
                    else "",
                }
            if attempt == 0:  # ran out: an urgent purchase that day
                self._buy(timezone.localdate(), [item.name], rolls_each=1, wide=short > 5)
        return None

    def _deliver(self, order: Order, person: Person):
        order.refresh_from_db()
        if order.status in (OrderStatus.CANCELLED, OrderStatus.DELIVERED):
            return
        if order.status != OrderStatus.READY:  # not finished yet: come back tomorrow
            tomorrow = self._working_hours(timezone.now() + dt.timedelta(days=1))
            self.schedule(tomorrow, lambda: self._deliver(order, person))
            return
        due = order.total - order_paid_amount(order)
        payment = None
        if due > 0 and self.rng.random() < person.pays_on_delivery:
            payment = {"amount": due, **self._mode(person)}
        elif due > 0 and not person.regular and self.rng.random() < 0.6:
            part = (due * D("0.7")).quantize(D("1"))
            payment = {"amount": part, **self._mode(person)} if part > 0 else None
        orders.deliver_order(order=order, user=self.desk(), payment=payment)
        # Rare: wrong buyer details on the bill; cancelled and re-issued.
        if self.rng.random() < 0.003:
            invoice = order.invoices.filter(status=InvoiceStatus.ISSUED).first()
            if invoice is not None:
                billing.cancel_invoice(
                    invoice=invoice, user=self.owner, reason="Wrong buyer name on the bill"
                )
                billing.issue_invoice(order=order, user=self.owner)

    def _mode(self, person: Person) -> dict[str, Any]:
        year = self.fy(timezone.localdate())
        digital = min(0.08 + (year - 2077) * 0.09, 0.55)
        roll = self.rng.random()
        if person.regular and roll < 0.12:
            return {
                "mode": PaymentMode.CHEQUE,
                "bank_name": self.rng.choice(
                    ["Nabil Bank", "NIC Asia", "Global IME", "Rastriya Banijya"]
                ),
                "cheque_no": str(self.rng.randint(1000000, 9999999)),
                "cheque_date": timezone.localdate(),
            }
        if roll < digital:
            wallet = self.rng.choices(
                ["fonepay", "esewa", "khalti"], weights=[3 if year >= 2080 else 1, 4, 2]
            )[0]
            return {
                "mode": PaymentMode.WALLET,
                "wallet": wallet,
                "reference_no": f"TX{self.rng.randint(10**8, 10**9)}",
            }
        if roll < digital + 0.08:
            return {
                "mode": PaymentMode.BANK,
                "bank_name": "Nabil Bank",
                "reference_no": f"NB{self.rng.randint(10**5, 10**6)}",
            }
        return {"mode": PaymentMode.CASH}

    # -- money and stock routines ------------------------------------------------------------

    def _collect_dues(self):
        """Customers with dues come in to pay: regulars about once a month, slow
        payers every few months, walk-ins who left a little owing within weeks."""
        owing = {
            row["pk"]: row["due"]
            for row in Customer.objects.annotate(due=balance_subquery())
            .filter(due__gt=0)
            .values("pk", "due")
        }
        if not owing:
            return
        by_id = {p.customer.pk: p for p in self.people}
        for customer_id, due in owing.items():
            person = by_id.get(customer_id)
            if person is None:
                continue
            chance = 1 / 120 if person.slow else (1 / 24 if person.regular else 1 / 12)
            if self.rng.random() >= chance:
                continue
            share = D("1") if not person.regular else D(str(self.rng.choice([0.5, 0.8, 1, 1])))
            amount = (due * share).quantize(D("1"))
            if amount <= 0:
                continue
            payment = billing.receive_payment(
                user=self.desk(),
                customer=person.customer,
                amount=amount,
                notes="Towards dues",
                **self._mode(person),
            )
            if payment.mode == PaymentMode.CHEQUE and self.rng.random() < 0.04:
                self.schedule(
                    timezone.now() + dt.timedelta(days=3),
                    lambda p=payment: billing.void_payment(
                        payment=p, user=self.owner, reason="Cheque bounced"
                    ),
                )

    def _restock(self, day: dt.date):
        low = [
            name
            for name, item in self.items.items()
            if item.is_active
            and StockItem.objects.get(pk=item.pk).on_hand < item.low_stock_level * 2
        ]
        if low:
            self._buy(day, low, rolls_each=self.rng.choice([1, 2]))
        for roll in Roll.objects.filter(
            status=RollStatus.ACTIVE, remaining_sqft__lt=12, remaining_sqft__gt=0
        ):
            stock.finish_roll(user=self.operator(), roll=roll, reason="Roll end too short to use")

    def _buy(self, day: dt.date, names: list[str], rolls_each: int = 1, wide: bool = False):
        year = self.fy(day)
        lines = []
        for name in names:
            widths, length, prices = ROLL_MEDIA[name]
            price = D(str(prices.get(year) or prices[max(k for k in prices if k <= year)]))
            width = max(widths) if wide else self.rng.choice(widths)
            lines.append(
                {
                    "stock_item": self.items[name],
                    "roll_count": rolls_each,
                    "roll_width_ft": D(str(width)),
                    "roll_length_ft": D(str(length)),
                    "amount": (price * width * length * rolls_each).quantize(D("1")),
                }
            )
        supplier = self.rng.choice(self.suppliers)
        stock.receive_purchase(
            user=self.owner,
            supplier=supplier,
            purchase_date=day,
            bill_no=f"{supplier.name[:3].upper()}-{self.rng.randint(1000, 9999)}",
            lines=lines,
        )

    def _month_end(self):
        # Ink used over the month, and a box of eyelets; buy more when low.
        used = D(str(round(self.rng.uniform(1.5, 3.5), 2)))
        ink = StockItem.objects.get(pk=self.ink.pk)
        if ink.on_hand < used + 1:
            stock.receive_purchase(
                user=self.owner,
                supplier=self.suppliers[0],
                purchase_date=timezone.localdate(),
                lines=[{"stock_item": self.ink, "quantity": D("8"), "amount": D("8") * D("3200")}],
            )
        stock.record_usage(
            user=self.operator(), stock_item=self.ink, quantity=used, reason="Ink used this month"
        )
        eyelets = StockItem.objects.get(pk=self.eyelet_stock.pk)
        if eyelets.on_hand < 2:
            stock.receive_purchase(
                user=self.owner,
                supplier=self.suppliers[2],
                purchase_date=timezone.localdate(),
                lines=[{"stock_item": self.eyelet_stock, "quantity": D("10"), "amount": D("3800")}],
            )
        stock.record_usage(
            user=self.operator(),
            stock_item=self.eyelet_stock,
            quantity=D("1"),
            reason="Eyelets used",
        )
        # Year-end clean-up of a long-unpaid small due (owner's decision).
        bs = to_bs(timezone.localdate())
        if bs.month == 3 and self.rng.random() < 0.5:
            for person in self.people:
                bal = customer_balance(person.customer)
                if person.slow and D("0") < bal < D("1500"):
                    billing.post_adjustment(
                        customer=person.customer,
                        amount=-bal,
                        user=self.owner,
                        narration="Small old due written off at year end",
                    )
                    break
