from __future__ import annotations

import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.tenancy.context import business_default, require_business_id
from apps.tenancy.models import Business, BusinessOwned

from .storage import private_storage


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# Allowed placeholders: {n}, {n:05d}, {fy}. Nothing else, so owner-entered
# patterns can never reach attributes through str.format.
_PATTERN_TOKEN = re.compile(r"\{([^}]*)\}")
_ALLOWED_TOKENS = re.compile(r"^(n(:0?\d{1,2}d)?|fy)$")


def validate_number_pattern(value: str) -> None:
    tokens = _PATTERN_TOKEN.findall(value)
    if not any(t.startswith("n") for t in tokens):
        raise ValidationError("The pattern must contain {n}, for example JOB-{n} or INV-{n:04d}.")
    for token in tokens:
        if not _ALLOWED_TOKENS.match(token):
            raise ValidationError(
                f"Unsupported placeholder {{{token}}}. Use {{n}}, {{n:04d}} or {{fy}}."
            )


def branding_path(instance: ShopSettings, filename: str) -> str:
    return f"branding/{instance.business_id}/{filename}"


class ShopSettings(models.Model):
    """Each business's settings: identity, tax, pricing defaults and numbering."""

    business = models.OneToOneField(
        Business, on_delete=models.PROTECT, default=business_default, related_name="settings"
    )

    # Identity (printed on every document)
    name = models.CharField(max_length=150, default="OM Traders and Suppliers")
    tagline = models.CharField(max_length=200, blank=True, default="Flex printing and signage")
    address = models.CharField(max_length=255, blank=True, default="Nepalgunj-12, Banke, Nepal")
    phone = models.CharField(max_length=60, blank=True)
    email = models.EmailField(blank=True)
    pan_vat_number = models.CharField("PAN / VAT number", max_length=20, blank=True)

    # Tax
    is_vat_registered = models.BooleanField(
        default=False, help_text="When on, VAT is added to quotations and invoices."
    )
    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("13.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # Pricing defaults
    default_min_sqft = models.DecimalField(
        "Default minimum sq ft",
        max_digits=8,
        decimal_places=2,
        default=Decimal("5.00"),
        validators=[MinValueValidator(0)],
        help_text="Any item smaller than this is charged as this many sq ft.",
    )
    round_total_to_rupee = models.BooleanField(
        default=False, help_text="Round grand totals to the nearest rupee with a round-off line."
    )
    front_desk_max_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Default discount limit for front desk staff (can be overridden per user).",
    )

    # Documents
    # Private: served only to signed-in users (see apps/core/storage.py).
    logo = models.ImageField(upload_to=branding_path, storage=private_storage, blank=True)
    stamp_image = models.ImageField(upload_to=branding_path, storage=private_storage, blank=True)
    signature_image = models.ImageField(
        upload_to=branding_path, storage=private_storage, blank=True
    )
    invoice_footer_note = models.CharField(
        max_length=255, blank=True, default="Thank you for your business."
    )
    quotation_validity_days = models.PositiveSmallIntegerField(default=7)
    quotation_terms = models.TextField(
        blank=True,
        default="Prices are valid for the period shown. Work starts after design approval.",
    )

    # Numbering patterns
    order_number_pattern = models.CharField(
        max_length=40, default="ORD-{n:05d}", validators=[validate_number_pattern]
    )
    job_number_pattern = models.CharField(
        max_length=40, default="JOB-{n}", validators=[validate_number_pattern]
    )
    invoice_number_pattern = models.CharField(
        max_length=40, default="INV-{fy}-{n:04d}", validators=[validate_number_pattern]
    )
    receipt_number_pattern = models.CharField(
        max_length=40, default="RCT-{fy}-{n:04d}", validators=[validate_number_pattern]
    )
    purchase_number_pattern = models.CharField(
        max_length=40, default="PUR-{n:05d}", validators=[validate_number_pattern]
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "shop settings"
        verbose_name_plural = "shop settings"

    def __str__(self) -> str:
        return self.name

    @classmethod
    def load(cls) -> ShopSettings:
        """The current business's settings, created with its name on first use."""
        business_id = require_business_id()
        obj, _ = cls.objects.get_or_create(
            business_id=business_id,
            defaults={
                "name": lambda: Business.objects.get(pk=business_id).name,
                "tagline": "",
                "address": "",
            },
        )
        return obj


class DocumentSequence(BusinessOwned):
    """Gap-free counters for document numbers, optionally reset per fiscal year."""

    doc_type = models.CharField(max_length=20)
    fiscal_year = models.CharField(max_length=7, blank=True, default="")
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "doc_type", "fiscal_year"], name="uniq_sequence_scope"
            )
        ]

    def __str__(self) -> str:
        scope = f" {self.fiscal_year}" if self.fiscal_year else ""
        return f"{self.doc_type}{scope}: {self.last_number}"


class ActivityLog(BusinessOwned):
    """Who did what, and when, for important business actions."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity",
    )
    action = models.CharField(max_length=60, db_index=True)
    target_type = models.CharField(max_length=60, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    target_label = models.CharField(max_length=120, blank=True)
    message = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.target_label}"
