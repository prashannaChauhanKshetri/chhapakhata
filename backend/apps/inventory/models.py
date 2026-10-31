"""Stock: items, roll-wise media tracking, purchases and an append-only movement ledger."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.money import fmt_qty
from apps.tenancy.models import BusinessOwned

QTY = {"max_digits": 12, "decimal_places": 2}


class StockKind(models.TextChoices):
    ROLL_MEDIA = "roll_media", "Roll media (flex, vinyl)"
    INK = "ink", "Ink"
    EYELETS = "eyelets", "Eyelets / rings"
    FRAME = "frame", "Frame material"
    STANDEE = "standee", "Standees"
    OTHER = "other", "Other"


class StockUnit(models.TextChoices):
    SQFT = "sqft", "sq ft"
    LITRE = "litre", "litre"
    BOX = "box", "box"
    RUNNING_FT = "rft", "running ft"
    PIECE = "pcs", "piece"


DEFAULT_UNIT = {
    StockKind.ROLL_MEDIA: StockUnit.SQFT,
    StockKind.INK: StockUnit.LITRE,
    StockKind.EYELETS: StockUnit.BOX,
    StockKind.FRAME: StockUnit.RUNNING_FT,
    StockKind.STANDEE: StockUnit.PIECE,
    StockKind.OTHER: StockUnit.PIECE,
}


class StockItem(BusinessOwned, TimeStampedModel):
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=StockKind.choices)
    unit = models.CharField(max_length=10, choices=StockUnit.choices)
    low_stock_level = models.DecimalField(
        **QTY, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )
    #: Cached balance, maintained only by inventory services under a row lock.
    on_hand = models.DecimalField(**QTY, default=Decimal("0"))
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(fields=["business", "name"], name="uniq_stock_item_name")
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_roll_media(self) -> bool:
        return self.kind == StockKind.ROLL_MEDIA

    @property
    def is_low(self) -> bool:
        return self.low_stock_level > 0 and self.on_hand < self.low_stock_level


class RollStatus(models.TextChoices):
    ACTIVE = "active", "Available"
    FINISHED = "finished", "Finished"


class Roll(BusinessOwned, TimeStampedModel):
    """One physical roll, e.g. a 10 ft × 100 ft Star Flex roll = 1,000 sq ft."""

    code = models.CharField(max_length=20)
    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name="rolls")
    width_ft = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    length_ft = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    total_sqft = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_sqft = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10, choices=RollStatus.choices, default=RollStatus.ACTIVE, db_index=True
    )
    purchase_line = models.ForeignKey(
        "PurchaseLine", null=True, blank=True, on_delete=models.SET_NULL, related_name="rolls"
    )
    finished_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["stock_item", "status", "code"]
        constraints = [models.UniqueConstraint(fields=["business", "code"], name="uniq_roll_code")]

    def __str__(self) -> str:
        return f"{self.code} · {self.stock_item.name} {fmt_qty(self.width_ft)} ft"


class Supplier(BusinessOwned, TimeStampedModel):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    pan_no = models.CharField("PAN / VAT no.", max_length=9, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["business", "name"], name="uniq_supplier_name")
        ]

    def __str__(self) -> str:
        return self.name


class Purchase(BusinessOwned, TimeStampedModel):
    purchase_no = models.CharField(max_length=30)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    purchase_date = models.DateField(db_index=True)
    bill_no = models.CharField("Supplier bill no.", max_length=40, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    total_amount = models.DecimalField(**QTY, default=Decimal("0"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-purchase_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["business", "purchase_no"], name="uniq_purchase_no")
        ]

    def __str__(self) -> str:
        return self.purchase_no


class PurchaseLine(BusinessOwned):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="lines")
    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(**QTY)
    amount = models.DecimalField(**QTY)
    rate = models.DecimalField(max_digits=12, decimal_places=4)
    roll_count = models.PositiveSmallIntegerField(null=True, blank=True)
    roll_width_ft = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roll_length_ft = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["purchase", "id"]

    def __str__(self) -> str:
        return f"{self.purchase.purchase_no}: {self.stock_item.name} × {self.quantity}"


class MovementType(models.TextChoices):
    OPENING = "opening", "Opening stock"
    PURCHASE = "purchase", "Purchase"
    CONSUMPTION = "consumption", "Used in job"
    WASTAGE = "wastage", "Wastage"
    ADJUSTMENT = "adjustment", "Adjustment"


class AppendOnlyError(RuntimeError):
    pass


class StockMovement(BusinessOwned):
    """Append-only stock ledger. Corrections are new adjustment rows, never edits."""

    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name="movements")
    roll = models.ForeignKey(
        Roll, null=True, blank=True, on_delete=models.PROTECT, related_name="movements"
    )
    movement_type = models.CharField(max_length=20, choices=MovementType.choices, db_index=True)
    quantity = models.DecimalField(**QTY, help_text="Positive adds stock, negative removes it.")
    balance_after = models.DecimalField(**QTY)
    roll_balance_after = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    job = models.ForeignKey(
        "production.Job",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    purchase_line = models.ForeignKey(
        PurchaseLine, null=True, blank=True, on_delete=models.PROTECT, related_name="movements"
    )
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["stock_item", "created_at"], name="movement_item_time")]

    def __str__(self) -> str:
        return f"{self.get_movement_type_display()} {self.quantity} {self.stock_item.name}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise AppendOnlyError("Stock movements cannot be edited. Record an adjustment instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError("Stock movements cannot be deleted. Record an adjustment instead.")
