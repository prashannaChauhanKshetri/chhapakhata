from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .dates import bs_string
from .models import ActivityLog, ShopSettings


@extend_schema_field(OpenApiTypes.STR)
class BSDateField(serializers.Field):
    """Read-only BS (Bikram Sambat) rendering of a date or datetime attribute."""

    def __init__(self, **kwargs):
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def to_representation(self, value):
        return bs_string(value)


class UserRefSerializer(serializers.Serializer):
    """Compact user reference embedded in other resources."""

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)


IMAGE_FIELDS = ("logo", "stamp_image", "signature_image")


class ShopSettingsSerializer(serializers.ModelSerializer):
    remove_logo = serializers.BooleanField(write_only=True, required=False)
    remove_stamp_image = serializers.BooleanField(write_only=True, required=False)
    remove_signature_image = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = ShopSettings
        fields = [
            "name",
            "tagline",
            "address",
            "phone",
            "email",
            "pan_vat_number",
            "is_vat_registered",
            "vat_rate",
            "default_min_sqft",
            "round_total_to_rupee",
            "front_desk_max_discount_percent",
            "logo",
            "stamp_image",
            "signature_image",
            "remove_logo",
            "remove_stamp_image",
            "remove_signature_image",
            "invoice_footer_note",
            "quotation_validity_days",
            "quotation_terms",
            "order_number_pattern",
            "job_number_pattern",
            "invoice_number_pattern",
            "receipt_number_pattern",
            "purchase_number_pattern",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def to_representation(self, instance):
        # Images are private files: point at the signed-in-only endpoint, with a
        # version so a replaced image is not shown from the browser cache.
        data = super().to_representation(instance)
        version = int(instance.updated_at.timestamp()) if instance.updated_at else 0
        for field in IMAGE_FIELDS:
            data[field] = (
                f"/api/v1/settings/shop/images/{field}/?v={version}"
                if getattr(instance, field)
                else None
            )
        return data

    def update(self, instance, validated_data):
        for field in IMAGE_FIELDS:
            if validated_data.pop(f"remove_{field}", False):
                getattr(instance, field).delete(save=False)
                setattr(instance, field, "")
        return super().update(instance, validated_data)


class ActivityLogSerializer(serializers.ModelSerializer):
    actor = UserRefSerializer(read_only=True, allow_null=True)
    created_at_bs = BSDateField(source="created_at")

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "actor",
            "action",
            "target_type",
            "target_id",
            "target_label",
            "message",
            "metadata",
            "ip_address",
            "created_at",
            "created_at_bs",
        ]


class DateConversionSerializer(serializers.Serializer):
    ad = serializers.DateField()
    bs = serializers.CharField()
    bs_long = serializers.CharField()
    fiscal_year = serializers.CharField()
    bs_month_start = serializers.DateField()
    bs_month_end = serializers.DateField()


class ReasonSerializer(serializers.Serializer):
    """A short reason, required for cancellations, voids and adjustments."""

    reason = serializers.CharField(max_length=255)
