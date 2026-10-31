from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.catalog.models import AddOnBasis, LengthUnit, PricingUnit
from apps.core.dates import local_today
from apps.core.models import TimeStampedModel
from apps.core.money import fmt_qty
from apps.tenancy.models import BusinessOwned

MONEY = {"max_digits": 12, "decimal_places": 2, "default": Decimal("0.00")}


class OrderStatus(models.TextChoices):
    QUOTATION = "quotation", "Quotation"
    CONFIRMED = "confirmed", "Confirmed"
    IN_PRODUCTION = "in_production", "In production"
    READY = "ready", "Ready for collection"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"


class DiscountType(models.TextChoices):
    NONE = "none", "No discount"
    PERCENT = "percent", "Percent"
    AMOUNT = "amount", "Fixed amount"


class OrderSource(models.TextChoices):
    COUNTER = "counter", "Entered in ChhapaKhata"
    IMPORT = "import", "Imported work log"


class RateSource(models.TextChoices):
    CARD = "card", "Rate card"
    PREVIOUS = "previous", "Customer's last rate"
    CUSTOM = "custom", "Custom rate"


class Order(BusinessOwned, TimeStampedModel):
    order_no = models.CharField(max_length=30)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.QUOTATION, db_index=True
    )
    order_date = models.DateField(default=local_today, db_index=True)
    deadline = models.DateTimeField(null=True, blank=True)
    is_urgent = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    source = models.CharField(
        max_length=10, choices=OrderSource.choices, default=OrderSource.COUNTER, db_index=True
    )

    discount_type = models.CharField(
        max_length=10, choices=DiscountType.choices, default=DiscountType.NONE
    )
    discount_value = models.DecimalField(**MONEY)

    subtotal = models.DecimalField(**MONEY)
    discount_amount = models.DecimalField(**MONEY)
    taxable_amount = models.DecimalField(**MONEY)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    vat_amount = models.DecimalField(**MONEY)
    round_off = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders_created"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)

    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["business", "order_no"], name="uniq_order_no")
        ]

    def __str__(self) -> str:
        return self.order_no

    @property
    def is_quotation(self) -> bool:
        return self.status == OrderStatus.QUOTATION


class OrderItem(BusinessOwned):
    """One printed item: size, media and quantity, with prices snapshotted at entry."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    line_no = models.PositiveSmallIntegerField()
    media_type = models.ForeignKey(
        "catalog.MediaType", on_delete=models.PROTECT, related_name="order_items"
    )
    media_name = models.CharField(max_length=80)
    description = models.CharField(max_length=200, blank=True)

    pricing_unit = models.CharField(
        max_length=5, choices=PricingUnit.choices, default=PricingUnit.SQFT
    )
    # Zero width and height mean "no size" (allowed for per-piece items only).
    width = models.DecimalField(max_digits=10, decimal_places=2)
    height = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=2, choices=LengthUnit.choices, default=LengthUnit.FOOT)
    quantity = models.PositiveIntegerField(default=1)

    width_ft = models.DecimalField(max_digits=10, decimal_places=4)
    height_ft = models.DecimalField(max_digits=10, decimal_places=4)
    sqft = models.DecimalField("Sq ft per piece", max_digits=10, decimal_places=2)
    billable_sqft = models.DecimalField("Billable sq ft per piece", max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    rate_source = models.CharField(
        max_length=10, choices=RateSource.choices, default=RateSource.CARD
    )
    card_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Rate-card price when the line was entered, for comparison.",
    )
    min_sqft = models.DecimalField(max_digits=8, decimal_places=2)

    base_amount = models.DecimalField(**MONEY)
    addons_amount = models.DecimalField(**MONEY)
    line_total = models.DecimalField(**MONEY)

    finishing = models.CharField(max_length=200, blank=True)
    design_file_ref = models.CharField("Design file", max_length=255, blank=True)
    import_ref = models.CharField(
        max_length=40,
        blank=True,
        default="",
        help_text="Fingerprint of the work-log row this line was imported from.",
    )

    class Meta:
        ordering = ["order", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["order", "line_no"], name="uniq_order_line"),
            models.UniqueConstraint(
                fields=["business", "import_ref"],
                condition=~models.Q(import_ref=""),
                name="uniq_order_item_import_ref",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order.order_no} #{self.line_no} {self.media_name}"

    @property
    def total_sqft(self) -> Decimal:
        return self.sqft * self.quantity

    @property
    def total_billable_sqft(self) -> Decimal:
        return self.billable_sqft * self.quantity

    @property
    def is_per_piece(self) -> bool:
        return self.pricing_unit == PricingUnit.PIECE

    @property
    def has_size(self) -> bool:
        return self.width > 0 and self.height > 0

    @property
    def size_label(self) -> str:
        if not self.has_size:
            return ""
        return f"{fmt_qty(self.width)} × {fmt_qty(self.height)} {self.unit}"

    @property
    def min_applied(self) -> bool:
        return self.billable_sqft > self.sqft


class OrderItemAddOn(BusinessOwned):
    item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="addons")
    addon = models.ForeignKey("catalog.AddOn", on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=80)
    basis = models.CharField(max_length=20, choices=AddOnBasis.choices)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1"))
    amount = models.DecimalField(**MONEY)

    class Meta:
        ordering = ["item", "id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.amount})"
