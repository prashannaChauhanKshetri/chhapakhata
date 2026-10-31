from __future__ import annotations

from rest_framework import serializers

from apps.core.models import ShopSettings
from apps.inventory.models import StockItem, StockKind
from apps.tenancy.validators import unique_in_business

from .models import AddOn, MediaType


class MediaTypeSerializer(serializers.ModelSerializer):
    effective_min_sqft = serializers.SerializerMethodField()
    material_name = serializers.CharField(source="material.name", read_only=True, default=None)
    pricing_unit_label = serializers.CharField(source="get_pricing_unit_display", read_only=True)
    material = serializers.PrimaryKeyRelatedField(
        queryset=StockItem.objects.filter(kind=StockKind.ROLL_MEDIA),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = MediaType
        fields = [
            "id",
            "name",
            "pricing_unit",
            "pricing_unit_label",
            "rate",
            "min_sqft",
            "effective_min_sqft",
            "material",
            "material_name",
            "description",
            "is_active",
            "sort_order",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]
        extra_kwargs = {"name": unique_in_business(MediaType)}

    def get_effective_min_sqft(self, obj: MediaType) -> str:
        if obj.min_sqft is not None:
            return f"{obj.min_sqft:.2f}"
        shop = self.context.get("shop") or ShopSettings.load()
        self.context["shop"] = shop
        return f"{shop.default_min_sqft:.2f}"


class AddOnSerializer(serializers.ModelSerializer):
    basis_label = serializers.CharField(source="get_basis_display", read_only=True)
    uses_quantity = serializers.BooleanField(read_only=True)

    class Meta:
        model = AddOn
        fields = [
            "id",
            "name",
            "basis",
            "basis_label",
            "rate",
            "default_quantity",
            "uses_quantity",
            "description",
            "is_active",
            "sort_order",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]
        extra_kwargs = {"name": unique_in_business(AddOn)}


class RateHistorySerializer(serializers.Serializer):
    history_id = serializers.IntegerField()
    history_date = serializers.DateTimeField()
    history_type = serializers.CharField()
    changed_by = serializers.CharField(allow_null=True)
    rate = serializers.DecimalField(max_digits=10, decimal_places=2)
    min_sqft = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)
    is_active = serializers.BooleanField()
