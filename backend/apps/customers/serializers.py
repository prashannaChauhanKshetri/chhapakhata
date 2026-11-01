from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.billing.selectors import customer_balance
from apps.core.serializers import BSDateField

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    customer_type_label = serializers.CharField(source="get_customer_type_display", read_only=True)
    balance = serializers.SerializerMethodField()
    opening_balance = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        write_only=True,
        required=False,
        help_text="Existing due (positive) or advance (negative) when the customer is added.",
    )
    opening_date = serializers.DateField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Date of that balance (default: last day of the previous fiscal year)",
    )
    created_at_bs = BSDateField(source="created_at")

    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "phone",
            "alt_phone",
            "address",
            "pan_no",
            "customer_type",
            "customer_type_label",
            "notes",
            "is_active",
            "balance",
            "opening_balance",
            "opening_date",
            "created_at",
            "created_at_bs",
        ]
        read_only_fields = ["created_at"]

    def get_balance(self, obj: Customer) -> str:
        value = getattr(obj, "ledger_balance", None)
        if value is None:
            value = customer_balance(obj)
        return f"{Decimal(value):.2f}"

    def validate_name(self, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError("Enter the customer's name.")
        return value

    def update(self, instance, validated_data):
        validated_data.pop("opening_balance", None)
        validated_data.pop("opening_date", None)
        return super().update(instance, validated_data)


class CustomerRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "address", "pan_no"]


class LedgerAdjustmentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Positive increases what the customer owes; negative reduces it.",
    )
    narration = serializers.CharField(max_length=255)


class OpeningBalanceInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Due carried in (positive) or advance (negative); 0 clears it.",
    )
    as_of = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Only when first set (default: last day of the previous fiscal year)",
    )
    reason = serializers.CharField(
        max_length=200, required=False, allow_blank=True, help_text="Required for a correction"
    )


class OpeningEntrySerializer(serializers.Serializer):
    date = serializers.DateField(source="entry_date")
    date_bs = BSDateField(source="entry_date")
    debit = serializers.DecimalField(max_digits=12, decimal_places=2)
    credit = serializers.DecimalField(max_digits=12, decimal_places=2)
    narration = serializers.CharField()
    created_by = serializers.CharField(source="created_by.get_full_name", default="")
    created_at = serializers.DateTimeField()


class OpeningBalanceSerializer(serializers.Serializer):
    """The balance a customer carried in from the previous year, and its history."""

    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    date = serializers.DateField(allow_null=True)
    date_bs = serializers.CharField(allow_null=True)
    default_date = serializers.DateField(help_text="Last day of the previous fiscal year")
    default_date_bs = serializers.CharField()
    has_other_entries = serializers.BooleanField(
        help_text="The customer has invoices, payments or imported work too"
    )
    entries = OpeningEntrySerializer(many=True)


class StatementEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    date = serializers.DateField()
    date_bs = serializers.CharField()
    entry_type = serializers.CharField()
    entry_type_label = serializers.CharField()
    reference = serializers.CharField()
    invoice_id = serializers.IntegerField(allow_null=True)
    payment_id = serializers.IntegerField(allow_null=True)
    order_id = serializers.IntegerField(allow_null=True)
    narration = serializers.CharField()
    debit = serializers.DecimalField(max_digits=14, decimal_places=2)
    credit = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)


class StatementTypeTotalSerializer(serializers.Serializer):
    entry_type = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    debit = serializers.DecimalField(max_digits=14, decimal_places=2)
    credit = serializers.DecimalField(max_digits=14, decimal_places=2)


class AgingBucketSerializer(serializers.Serializer):
    label = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class StatementAgingSerializer(serializers.Serializer):
    oldest_due_date = serializers.DateField(allow_null=True)
    buckets = AgingBucketSerializer(many=True)


class StatementSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    customer_name = serializers.CharField()
    date_from = serializers.DateField(allow_null=True)
    date_to = serializers.DateField()
    opening_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    entries = StatementEntrySerializer(many=True)
    total_debit = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_credit = serializers.DecimalField(max_digits=14, decimal_places=2)
    closing_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    by_type = StatementTypeTotalSerializer(many=True)
    aging = StatementAgingSerializer(
        allow_null=True, help_text="How old the closing due is (oldest invoices paid first)."
    )
