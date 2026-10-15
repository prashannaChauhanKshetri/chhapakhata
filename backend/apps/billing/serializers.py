from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.core.serializers import BSDateField, UserRefSerializer
from apps.customers.models import Customer
from apps.orders.models import Order

from .models import Invoice, InvoiceLine, Payment, PaymentMode, Wallet

MONEY = {"max_digits": 12, "decimal_places": 2}


class OrderRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_no = serializers.CharField()


class CustomerMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    phone = serializers.CharField()


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["line_no", "description", "details", "quantity", "unit", "rate", "amount"]


class InvoiceListSerializer(serializers.ModelSerializer):
    order = OrderRefSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    issued_by = UserRefSerializer(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_no",
            "fiscal_year",
            "invoice_date",
            "invoice_date_bs",
            "customer",
            "customer_name",
            "customer_phone",
            "order",
            "is_vat_invoice",
            "total",
            "status",
            "status_label",
            "print_count",
            "issued_by",
            "created_at",
        ]


class InvoiceDetailSerializer(InvoiceListSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    cancelled_by = UserRefSerializer(read_only=True, allow_null=True)
    order_paid = serializers.SerializerMethodField()
    order_balance = serializers.SerializerMethodField()

    class Meta(InvoiceListSerializer.Meta):
        fields = [
            *InvoiceListSerializer.Meta.fields,
            "customer_address",
            "customer_pan",
            "subtotal",
            "discount_amount",
            "taxable_amount",
            "vat_rate",
            "vat_amount",
            "round_off",
            "amount_in_words",
            "notes",
            "cancel_reason",
            "cancelled_at",
            "cancelled_by",
            "last_printed_at",
            "lines",
            "order_paid",
            "order_balance",
        ]

    def _paid(self, obj: Invoice) -> Decimal:
        from .selectors import order_paid_amount

        if not hasattr(obj, "_paid_cache"):
            obj._paid_cache = order_paid_amount(obj.order)
        return obj._paid_cache

    def get_order_paid(self, obj: Invoice) -> str:
        return f"{self._paid(obj):.2f}"

    def get_order_balance(self, obj: Invoice) -> str:
        if obj.is_cancelled:
            return "0.00"
        return f"{obj.total - self._paid(obj):.2f}"


class InvoiceCreateSerializer(serializers.Serializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class PaymentSerializer(serializers.ModelSerializer):
    customer = CustomerMiniSerializer(read_only=True)
    order = OrderRefSerializer(read_only=True, allow_null=True)
    mode_label = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    payment_date_bs = BSDateField(source="payment_date")
    received_by = UserRefSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "receipt_no",
            "fiscal_year",
            "customer",
            "order",
            "amount",
            "mode",
            "mode_label",
            "wallet",
            "bank_name",
            "reference_no",
            "cheque_no",
            "cheque_date",
            "payment_date",
            "payment_date_bs",
            "is_advance",
            "notes",
            "status",
            "status_label",
            "void_reason",
            "voided_at",
            "received_by",
            "created_at",
        ]


class PaymentCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), required=False, allow_null=True
    )
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))
    mode = serializers.ChoiceField(choices=PaymentMode.choices)
    wallet = serializers.ChoiceField(choices=Wallet.choices, required=False, allow_blank=True)
    bank_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    reference_no = serializers.CharField(max_length=60, required=False, allow_blank=True)
    cheque_no = serializers.CharField(max_length=30, required=False, allow_blank=True)
    cheque_date = serializers.DateField(required=False, allow_null=True)
    payment_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)
