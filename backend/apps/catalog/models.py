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


class PricingUnit(models.TextChoices):
    SQFT = "sqft", "Per sq ft"
    PIECE = "piece", "Per piece"


class MediaType(TimeStampedModel):
    """An item on the rate card.

    Most media are priced by area (Star Flex at Rs 35 per sq ft). Some work is
    priced per piece instead (a photo print, 3D letters, a name plate); for
    those the size is optional and the minimum sq ft rule does not apply.
    """

    name = models.CharField(max_length=80, unique=True)
    pricing_unit = models.CharField(
        max_length=5, choices=PricingUnit.choices, default=PricingUnit.SQFT
    )
    rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Rate per sq ft, or per piece for per-piece items.",
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

    @property
    def is_per_piece(self) -> bool:
        return self.pricing_unit == PricingUnit.PIECE


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
