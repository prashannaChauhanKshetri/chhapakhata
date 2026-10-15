"""Fill an empty database with a realistic demo shop.

All data goes through the normal service functions, so invoices, ledger
entries and stock movements are exactly what real use would produce.
Rates are placeholders until the client's rate card arrives.

    uv run python manage.py seed_demo
"""

from __future__ import annotations

import datetime as dt
import random
from contextlib import contextmanager
from decimal import Decimal
from unittest import mock

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.billing import services as billing
from apps.billing.selectors import order_paid_amount
from apps.catalog.models import AddOn, AddOnBasis, MediaType
from apps.core.models import ShopSettings
from apps.core.permissions import Role
from apps.customers.models import Customer, CustomerType
from apps.inventory import services as stock
from apps.inventory.models import Roll, RollStatus, StockItem, StockKind, StockUnit, Supplier
from apps.orders import services as orders
from apps.orders.models import Order
from apps.production.models import Stage
from apps.production.services import move_job

D = Decimal


@contextmanager
def travel_to(moment: dt.datetime):
    with mock.patch("django.utils.timezone.now", return_value=moment):
        yield


class Command(BaseCommand):
    help = "Create demo users, rate card, stock, customers and three weeks of orders."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="Demo@2083", help="Password for all demo users")
        parser.add_argument("--days", type=int, default=21, help="Days of order history")

    def handle(self, *args, **options):
        if Order.objects.exists():
            raise CommandError("The database already has orders. Run `manage.py flush` first.")
        self.rng = random.Random(2083)
        tz = timezone.get_current_timezone()
        start = timezone.localdate() - dt.timedelta(days=options["days"])
        opening = timezone.make_aware(dt.datetime.combine(start, dt.time(9, 0)), tz)
        with travel_to(opening), transaction.atomic():
            self._settings()
            self._users(options["password"])
            self._catalog_and_stock()
            self._customers()
        self._history(options["days"])
        self._today()
        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(
            "Sign in as owner / frontdesk / operator with password "
            f"'{options['password']}' (change these before real use)."
        )

    # -- setup -------------------------------------------------------------

    def _settings(self):
        shop = ShopSettings.load()
        shop.name = "OM Traders and Suppliers"
        shop.tagline = "Flex printing · Signage · 2D/3D boards · Glow signs"
        shop.address = "Nepalgunj-12, Banke, Nepal"
        shop.phone = "081-000000"
        shop.pan_vat_number = "000000000"
        shop.is_vat_registered = True
        shop.save()

    def _users(self, password: str):
        people = [
            ("owner", "Anil", "Pokhrel", Role.OWNER),
            ("frontdesk", "Sita", "Sharma", Role.FRONT_DESK),
            ("operator", "Ram", "Thapa", Role.OPERATOR),
        ]
        for username, first, last, role in people:
            user = User(username=username, first_name=first, last_name=last, role=role)
            user.set_password(password)
            user.save()
        self.owner = User.objects.get(username="owner")
        self.desk = User.objects.get(username="frontdesk")
        self.op = User.objects.get(username="operator")

    def _catalog_and_stock(self):
        rolls = {}
        for name in ["Star Flex", "Normal Flex", "Vinyl", "Backlit Flex", "Sticker"]:
            rolls[name] = StockItem.objects.create(
                name=name, kind=StockKind.ROLL_MEDIA, unit=StockUnit.SQFT, low_stock_level=D("400")
            )
        others = [
            ("Eco-solvent ink", StockKind.INK, StockUnit.LITRE, D("2"), D("6")),
            ("Eyelets", StockKind.EYELETS, StockUnit.BOX, D("2"), D("5")),
            ("Frame pipe (1 inch)", StockKind.FRAME, StockUnit.RUNNING_FT, D("100"), D("80")),
            ("Roll-up standee", StockKind.STANDEE, StockUnit.PIECE, D("3"), D("2")),
        ]
        for name, kind, unit, low, qty in others:
            item = StockItem.objects.create(name=name, kind=kind, unit=unit, low_stock_level=low)
            stock.add_opening_stock(user=self.owner, stock_item=item, quantity=qty)

        supplier = Supplier.objects.create(name="Kathmandu Flex House", phone="01-0000000")
        stock.receive_purchase(
            user=self.owner,
            supplier=supplier,
            purchase_date=timezone.localdate(),
            bill_no="KFH-2210",
            lines=[
                {
                    "stock_item": rolls["Star Flex"],
                    "roll_count": 2,
                    "roll_width_ft": D("10"),
                    "roll_length_ft": D("164"),
                    "amount": D("29520"),
                },
                {
                    "stock_item": rolls["Star Flex"],
                    "roll_count": 1,
                    "roll_width_ft": D("5"),
                    "roll_length_ft": D("164"),
                    "amount": D("7380"),
                },
                {
                    "stock_item": rolls["Normal Flex"],
                    "roll_count": 2,
                    "roll_width_ft": D("6"),
                    "roll_length_ft": D("164"),
                    "amount": D("13776"),
                },
                {
                    "stock_item": rolls["Vinyl"],
                    "roll_count": 1,
                    "roll_width_ft": D("4"),
                    "roll_length_ft": D("164"),
                    "amount": D("19680"),
                },
                {
                    "stock_item": rolls["Backlit Flex"],
                    "roll_count": 1,
                    "roll_width_ft": D("5"),
                    "roll_length_ft": D("100"),
                    "amount": D("12500"),
                },
                {
                    "stock_item": rolls["Sticker"],
                    "roll_count": 1,
                    "roll_width_ft": D("4"),
                    "roll_length_ft": D("100"),
                    "amount": D("8800"),
                },
            ],
        )
        media = [
            ("Star Flex", D("35"), rolls["Star Flex"]),
            ("Normal Flex", D("25"), rolls["Normal Flex"]),
            ("Vinyl", D("70"), rolls["Vinyl"]),
            ("Backlit", D("60"), rolls["Backlit Flex"]),
            ("Sticker", D("55"), rolls["Sticker"]),
            ("Glossy photo paper", D("65"), None),
        ]
        for order, (name, rate, material) in enumerate(media):
            MediaType.objects.create(
                name=name, rate_per_sqft=rate, material=material, sort_order=order
            )
        addons = [
            ("Design / editing", AddOnBasis.FIXED, D("500"), D("1")),
            ("Eyelets", AddOnBasis.PER_PIECE, D("5"), D("8")),
            ("Framing", AddOnBasis.PER_RUNNING_FT, D("60"), D("1")),
            ("Lamination", AddOnBasis.PER_SQFT, D("15"), D("1")),
            ("Pockets", AddOnBasis.PER_PIECE, D("50"), D("2")),
            ("Urgent / express", AddOnBasis.PERCENT, D("20"), D("1")),
        ]
        for order, (name, basis, rate, qty) in enumerate(addons):
            AddOn.objects.create(
                name=name, basis=basis, rate=rate, default_quantity=qty, sort_order=order
            )

    def _customers(self):
        people = [
            (
                "Nepalgunj Medical Hall",
                "9858020001",
                "Dhamboji, Nepalgunj",
                "301234567",
                CustomerType.BUSINESS,
                D("4500"),
            ),
            (
                "Bheri Hospital Pharmacy",
                "9858020002",
                "Nepalgunj-8",
                "302345678",
                CustomerType.BUSINESS,
                D("0"),
            ),
            (
                "Rapti Academy",
                "9858020003",
                "Kohalpur, Banke",
                "",
                CustomerType.BUSINESS,
                D("12000"),
            ),
            (
                "Sagar Electronics",
                "9858020004",
                "Surkhet Road, Nepalgunj",
                "303456789",
                CustomerType.BUSINESS,
                D("0"),
            ),
            (
                "Hotel Kalpana",
                "9858020005",
                "BP Chowk, Nepalgunj",
                "304567890",
                CustomerType.BUSINESS,
                D("-2000"),
            ),
            ("Ramesh Gupta", "9848030006", "Nepalgunj-4", "", CustomerType.INDIVIDUAL, D("0")),
            ("Banke Youth Club", "9848030007", "Khajura, Banke", "", CustomerType.BUSINESS, D("0")),
            ("Gita Tharu", "9848030008", "Nepalgunj-12", "", CustomerType.INDIVIDUAL, D("0")),
        ]
        self.customers = []
        for name, phone, address, pan, kind, opening in people:
            c = Customer.objects.create(
                name=name,
                phone=phone,
                address=address,
                pan_no=pan,
                customer_type=kind,
                created_by=self.owner,
            )
            billing.post_opening_balance(customer=c, amount=opening, user=self.owner)
            self.customers.append(c)

    # -- orders ------------------------------------------------------------

    def _random_items(self):
        media = list(MediaType.objects.filter(is_active=True))
        addons = {a.name: a for a in AddOn.objects.all()}
        sizes = [
            (D("10"), D("4"), "ft"),
            (D("6"), D("3"), "ft"),
            (D("3"), D("2"), "ft"),
            (D("24"), D("36"), "in"),
            (D("8"), D("4"), "ft"),
            (D("12"), D("18"), "in"),
        ]
        items = []
        for _ in range(self.rng.choice([1, 1, 1, 2, 2, 3])):
            w, h, unit = self.rng.choice(sizes)
            mt = self.rng.choice(media[:5])
            chosen = []
            if mt.name in ("Star Flex", "Normal Flex") and self.rng.random() < 0.6:
                chosen.append(orders.AddOnInput(addon=addons["Eyelets"], quantity=D("8")))
            if self.rng.random() < 0.25:
                chosen.append(orders.AddOnInput(addon=addons["Design / editing"], quantity=D("1")))
            if mt.name == "Backlit" and self.rng.random() < 0.7:
                chosen.append(orders.AddOnInput(addon=addons["Framing"], quantity=D("1")))
            items.append(
                orders.ItemInput(
                    media_type=mt,
                    width=w,
                    height=h,
                    unit=unit,
                    quantity=self.rng.choice([1, 1, 2, 5]),
                    description=self.rng.choice(
                        [
                            "Shop banner",
                            "Event backdrop",
                            "Notice board",
                            "Promotion",
                            "Signboard",
                            "",
                        ]
                    ),
                    finishing=self.rng.choice(["", "Hemmed edges", "Wooden frame", ""]),
                    addons=chosen,
                )
            )
        return items

    def _material(self, job):
        material = job.order_item.media_type.material
        if material is None:
            return None
        need = job.order_item.sqft * job.order_item.quantity
        short = min(job.order_item.width_ft, job.order_item.height_ft)
        roll = (
            Roll.objects.filter(
                stock_item=material,
                status=RollStatus.ACTIVE,
                remaining_sqft__gte=need + 5,
                width_ft__gte=short,
            )
            .order_by("width_ft")
            .first()
        )
        if roll is None:
            return None
        waste = D("0") if self.rng.random() < 0.7 else D(str(self.rng.choice([2, 3, 5])))
        return {
            "roll": roll,
            "used_sqft": need + D("1.5"),
            "wastage_sqft": waste,
            "wastage_reason": "Test print" if waste else "",
        }

    def _advance(self, job, user, to_stage):
        material = self._material(job) if job.stage <= Stage.PRINTING < to_stage else None
        move_job(
            job=job,
            user=user,
            to_stage=to_stage,
            material=material,
            skip_material=material is None and user == self.owner,
        )

    def _produce(self, order, until: int):
        for job in order.jobs.all():
            for stage, user in [
                (Stage.READY_FOR_PRINT, self.desk),
                (Stage.PRINTING, self.op),
                (Stage.FINISHING, self.op),
                (Stage.READY, self.op),
            ]:
                if stage > until:
                    break
                job.refresh_from_db()
                actor = (
                    user
                    if (stage != Stage.FINISHING or self._material(job) or job.material_recorded)
                    else self.owner
                )
                self._advance(job, actor, stage)

    def _history(self, days: int):
        tz = timezone.get_current_timezone()
        modes = ["cash", "cash", "cash", "wallet", "bank"]
        for offset in range(days, 0, -1):
            day = timezone.localdate() - dt.timedelta(days=offset)
            if day.weekday() == 5 and self.rng.random() < 0.7:  # Saturday is quieter
                continue
            for hour in sorted(
                self.rng.sample([10, 11, 12, 14, 15, 16], self.rng.choice([1, 2, 3]))
            ):
                moment = timezone.make_aware(dt.datetime.combine(day, dt.time(hour, 15)), tz)
                with travel_to(moment), transaction.atomic():
                    customer = self.rng.choice(self.customers)
                    order = orders.create_order(
                        user=self.desk,
                        customer=customer,
                        data=orders.OrderInput(items=self._random_items()),
                        deadline=moment + dt.timedelta(days=self.rng.choice([1, 2, 3])),
                        confirm=True,
                    )
                    if self.rng.random() < 0.5:
                        billing.receive_payment(
                            user=self.desk,
                            customer=customer,
                            order=order,
                            amount=(order.total * D("0.5")).quantize(D("1")),
                            mode="cash",
                        )
                    self._produce(order, Stage.READY)
                    order.refresh_from_db()
                    paid = order_paid_amount(order)
                    remaining = order.total - paid
                    settle = None
                    if remaining > 0 and self.rng.random() < 0.75:
                        mode = self.rng.choice(modes)
                        settle = {"amount": remaining, "mode": mode}
                        if mode == "wallet":
                            settle["wallet"] = self.rng.choice(["esewa", "khalti", "fonepay"])
                            settle["reference_no"] = f"TX{self.rng.randint(100000, 999999)}"
                        if mode == "bank":
                            settle["bank_name"] = "Nabil Bank"
                            settle["reference_no"] = f"NB{self.rng.randint(10000, 99999)}"
                    orders.deliver_order(order=order, user=self.desk, payment=settle)

    def _today(self):
        tz = timezone.get_current_timezone()
        now = timezone.now()
        plans = [
            ("quotation", None),
            ("confirmed", Stage.DESIGN),
            ("confirmed", Stage.READY_FOR_PRINT),
            ("confirmed", Stage.PRINTING),
            ("confirmed", Stage.FINISHING),
            ("confirmed", Stage.READY),
            ("overdue", Stage.READY_FOR_PRINT),
            ("quotation", None),
        ]
        for index, (kind, stage) in enumerate(plans):
            moment = min(
                now,
                timezone.make_aware(
                    dt.datetime.combine(timezone.localdate(), dt.time(9, 30 + index * 3)), tz
                ),
            )
            if kind == "overdue":
                moment = moment - dt.timedelta(days=2)
            with travel_to(moment), transaction.atomic():
                customer = self.customers[index % len(self.customers)]
                order = orders.create_order(
                    user=self.desk,
                    customer=customer,
                    data=orders.OrderInput(items=self._random_items()),
                    deadline=moment + dt.timedelta(days=1, hours=6),
                    is_urgent=index == 3,
                    notes="Customer will send final text by phone." if index == 1 else "",
                    confirm=kind != "quotation",
                )
                if kind != "quotation" and index % 2 == 0:
                    billing.receive_payment(
                        user=self.desk,
                        customer=customer,
                        order=order,
                        amount=(order.total * D("0.4")).quantize(D("1")),
                        mode="cash",
                    )
                if stage and stage > Stage.DESIGN:
                    self._produce(order, stage)
