from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.core.serializers import BSDateField, UserRefSerializer
from apps.tenancy.validators import unique_in_business

from .models import (
    DEFAULT_UNIT,
    Purchase,
    PurchaseLine,
    Roll,
    StockItem,
    StockMovement,
    Supplier,
)

QTY = {"max_digits": 12, "decimal_places": 2}


class StockItemSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    unit_label = serializers.CharField(source="get_unit_display", read_only=True)
    is_low = serializers.BooleanField(read_only=True)
    is_roll_media = serializers.BooleanField(read_only=True)
    active_rolls = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = StockItem
        fields = [
            "id",
            "name",
            "kind",
            "kind_label",
            "unit",
            "unit_label",
            "low_stock_level",
            "on_hand",
            "is_low",
            "is_roll_media",
            "active_rolls",
            "is_active",
            "notes",
            "updated_at",
        ]
        read_only_fields = ["on_hand", "updated_at"]
        extra_kwargs = {"unit": {"required": False}, "name": unique_in_business(StockItem)}

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        kind_changed = self.instance is not None and attrs.get("kind", kind) != self.instance.kind
        if kind_changed and self.instance.movements.exists():
            raise serializers.ValidationError(
                {"kind": "The kind cannot change once stock has been recorded."}
            )
        if not attrs.get("unit") and self.instance is None:
            attrs["unit"] = DEFAULT_UNIT[kind]
        if kind == "roll_media":
            attrs["unit"] = "sqft"
        return attrs


class RollSerializer(serializers.ModelSerializer):
    stock_item_name = serializers.CharField(source="stock_item.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    used_percent = serializers.SerializerMethodField()

    class Meta:
        model = Roll
        fields = [
            "id",
            "code",
            "stock_item",
            "stock_item_name",
            "width_ft",
            "length_ft",
            "total_sqft",
            "remaining_sqft",
            "used_percent",
            "status",
            "status_label",
            "finished_at",
            "notes",
            "created_at",
        ]

    def get_used_percent(self, obj: Roll) -> str:
        if not obj.total_sqft:
            return "0"
        return f"{(obj.total_sqft - obj.remaining_sqft) / obj.total_sqft * 100:.0f}"


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "phone", "address", "pan_no", "is_active"]
        extra_kwargs = {"name": unique_in_business(Supplier)}


class PurchaseLineSerializer(serializers.ModelSerializer):
    stock_item_name = serializers.CharField(source="stock_item.name", read_only=True)
    unit = serializers.CharField(source="stock_item.get_unit_display", read_only=True)

    class Meta:
        model = PurchaseLine
        fields = [
            "id",
            "stock_item",
            "stock_item_name",
            "unit",
            "quantity",
            "amount",
            "rate",
            "roll_count",
            "roll_width_ft",
            "roll_length_ft",
        ]


class PurchaseSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    purchase_date_bs = BSDateField(source="purchase_date")
    created_by = UserRefSerializer(read_only=True)
    lines = PurchaseLineSerializer(many=True, read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id",
            "purchase_no",
            "supplier",
            "supplier_name",
            "purchase_date",
            "purchase_date_bs",
            "bill_no",
            "notes",
            "total_amount",
            "created_by",
            "created_at",
            "lines",
        ]


class PurchaseLineInputSerializer(serializers.Serializer):
    stock_item = serializers.PrimaryKeyRelatedField(
        queryset=StockItem.objects.filter(is_active=True)
    )
    amount = serializers.DecimalField(**QTY, min_value=Decimal("0"))
    quantity = serializers.DecimalField(**QTY, required=False, allow_null=True)
    roll_count = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=500
    )
    roll_width_ft = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True
    )
    roll_length_ft = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True
    )


class PurchaseInputSerializer(serializers.Serializer):
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())
    purchase_date = serializers.DateField()
    bill_no = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    lines = PurchaseLineInputSerializer(many=True)


class StockMovementSerializer(serializers.ModelSerializer):
    stock_item_name = serializers.CharField(source="stock_item.name", read_only=True)
    unit = serializers.CharField(source="stock_item.get_unit_display", read_only=True)
    movement_type_label = serializers.CharField(source="get_movement_type_display", read_only=True)
    roll_code = serializers.CharField(source="roll.code", read_only=True, default=None)
    job_no = serializers.CharField(source="job.job_no", read_only=True, default=None)
    created_by = UserRefSerializer(read_only=True)
    created_at_bs = BSDateField(source="created_at")

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "stock_item",
            "stock_item_name",
            "unit",
            "roll",
            "roll_code",
            "movement_type",
            "movement_type_label",
            "quantity",
            "balance_after",
            "roll_balance_after",
            "job",
            "job_no",
            "reason",
            "created_by",
            "created_at",
            "created_at_bs",
        ]


class RollSpecSerializer(serializers.Serializer):
    width_ft = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0.01"))
    length_ft = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0.01"))
    remaining_sqft = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )


class OpeningStockSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(**QTY, required=False, allow_null=True)
    rolls = RollSpecSerializer(many=True, required=False)
    reason = serializers.CharField(max_length=255, required=False, default="Opening stock")


class QuantityReasonSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(**QTY, min_value=Decimal("0.01"))
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    roll = serializers.PrimaryKeyRelatedField(
        queryset=Roll.objects.all(), required=False, allow_null=True
    )


class AdjustStockSerializer(serializers.Serializer):
    counted_quantity = serializers.DecimalField(**QTY, min_value=Decimal("0"))
    reason = serializers.CharField(max_length=255)
    roll = serializers.PrimaryKeyRelatedField(
        queryset=Roll.objects.all(), required=False, allow_null=True
    )


class FinishRollSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
