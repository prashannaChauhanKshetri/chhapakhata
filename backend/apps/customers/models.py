from __future__ import annotations

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Upper
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel
from apps.tenancy.models import BusinessOwned

pan_validator = RegexValidator(r"^\d{9}$", "PAN / VAT numbers in Nepal have 9 digits.")
phone_validator = RegexValidator(
    r"^[0-9+\-\s]{6,20}$", "Enter a valid phone number (digits, spaces, + or -)."
)


class CustomerType(models.TextChoices):
    INDIVIDUAL = "individual", "Individual"
    BUSINESS = "business", "Business / Organisation"


class Customer(BusinessOwned, TimeStampedModel):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    alt_phone = models.CharField(
        "Alternate phone", max_length=20, blank=True, validators=[phone_validator]
    )
    address = models.CharField(max_length=255, blank=True)
    pan_no = models.CharField("PAN / VAT no.", max_length=9, blank=True, validators=[pan_validator])
    customer_type = models.CharField(
        max_length=20, choices=CustomerType.choices, default=CustomerType.INDIVIDUAL
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ["name"]
        indexes = [
            GinIndex(OpClass(Upper("name"), name="gin_trgm_ops"), name="customer_name_trgm"),
            models.Index(fields=["phone"], name="customer_phone_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.phone})" if self.phone else self.name

    def save(self, *args, **kwargs):
        self.name = " ".join(self.name.split())
        self.phone = self.phone.strip()
        super().save(*args, **kwargs)
