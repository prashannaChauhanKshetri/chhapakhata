"""Rate card: media types (priced per sq ft) and add-on charges."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel


class LengthUnit(models.TextChoices):
    INCH = "in", "Inches"
    FOOT = "ft", "Feet"
    CM = "cm", "Centimetres"


class MediaType(TimeStampedModel):
    """A printable material on the rate card, e.g. Star Flex at Rs 35 per sq ft."""

    name = models.CharField(max_length=80, unique=True)
    rate_per_sqft = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    min_sqft = models.DecimalField(
        "Minimum sq ft",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Leave empty to use the shop default.",
    )
    material = models.ForeignKey(
        "inventory.StockItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_types",
        help_text="Stock item consumed when this media is printed.",
    )
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class AddOnBasis(models.TextChoices):
    FIXED = "fixed", "Fixed amount per item line"
    PER_PIECE = "per_piece", "Per unit on each piece"
    PER_SQFT = "per_sqft", "Per sq ft (actual size)"
    PER_RUNNING_FT = "per_running_ft", "Per running ft (perimeter)"
    PERCENT = "percent", "Percent of print amount"


class AddOn(TimeStampedModel):
    """Extra charge on an item: design, eyelets, framing, lamination, pockets, urgent."""

    name = models.CharField(max_length=80, unique=True)
    basis = models.CharField(max_length=20, choices=AddOnBasis.choices)
    rate = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    default_quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Pre-filled quantity, e.g. 8 eyelets per banner.",
    )
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "add-on"

    def __str__(self) -> str:
        return self.name

    @property
    def uses_quantity(self) -> bool:
        return self.basis in {AddOnBasis.FIXED, AddOnBasis.PER_PIECE}
