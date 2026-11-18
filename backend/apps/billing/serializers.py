from __future__ import annotations

from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
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
    orders = serializers.SerializerMethodField(help_text="Every order on this bill")
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
            "vat_note",
            "orders",
            "cancel_reason",
            "cancelled_at",
            "cancelled_by",
            "last_printed_at",
            "lines",
            "order_paid",
            "order_balance",
        ]

    @extend_schema_field(OrderRefSerializer(many=True))
    def get_orders(self, obj: Invoice) -> list[dict]:
        links = obj.order_links.select_related("order").order_by("order__order_date", "order_id")
        return [{"id": link.order_id, "order_no": link.order.order_no} for link in links]

    def _paid(self, obj: Invoice) -> Decimal:
        from .selectors import bill_paid_amount

        if not hasattr(obj, "_paid_cache"):
            obj._paid_cache = bill_paid_amount(obj)
        return obj._paid_cache

    def get_order_paid(self, obj: Invoice) -> str:
        return f"{self._paid(obj):.2f}"

    def get_order_balance(self, obj: Invoice) -> str:
        if obj.is_cancelled:
            return "0.00"
        return f"{obj.total - self._paid(obj):.2f}"


class BillInputSerializer(serializers.Serializer):
    """Make a bill: one or more of a customer's orders, with or without VAT."""

    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    orders = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    add_vat = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Empty: the orders' choice, or the customer's setting.",
    )
    vat_note = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
        help_text="Printed on a bill without VAT, e.g. an exemption reference.",
    )
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class InvoiceCreateSerializer(BillInputSerializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False)
    orders = serializers.ListField(child=serializers.IntegerField(), min_length=1, required=False)
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), required=False, help_text="One order (older clients)."
    )

    def validate(self, attrs):
        if attrs.get("order") is not None:
            attrs["customer"] = attrs["order"].customer
            attrs["orders"] = [attrs["order"].pk]
        elif not attrs.get("customer") or not attrs.get("orders"):
            raise serializers.ValidationError({"orders": ["Choose the customer and orders."]})
        return attrs


class BillPreviewSerializer(serializers.Serializer):
    orders = OrderRefSerializer(many=True)
    add_vat = serializers.BooleanField()
    default_add_vat = serializers.BooleanField(help_text="What the bill does if not told")
    subtotal = serializers.DecimalField(**MONEY)
    discount_amount = serializers.DecimalField(**MONEY)
    taxable_amount = serializers.DecimalField(**MONEY)
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    vat_amount = serializers.DecimalField(**MONEY)
    round_off = serializers.DecimalField(**MONEY)
    total = serializers.DecimalField(**MONEY)
    work_on_account = serializers.DecimalField(
        **MONEY, help_text="Work-log charges already on the account that move onto the bill"
    )
    account_change = serializers.DecimalField(
        **MONEY, help_text="How much the customer's balance goes up"
    )


class UnbilledOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_no = serializers.CharField()
    order_date = serializers.DateField()
    order_date_bs = BSDateField(source="order_date")
    source = serializers.CharField()
    status = serializers.CharField()
    items = serializers.SerializerMethodField()
    subtotal = serializers.DecimalField(**MONEY)
    discount_amount = serializers.DecimalField(**MONEY)
    taxable_amount = serializers.DecimalField(**MONEY)
    vat_amount = serializers.DecimalField(**MONEY)
    total = serializers.DecimalField(**MONEY)
    paid_amount = serializers.DecimalField(**MONEY)

    def get_items(self, obj) -> str:
        names = [i.media_name for i in sorted(obj.items.all(), key=lambda i: i.line_no)]
        return ", ".join(dict.fromkeys(names))


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
    allow_repeat = serializers.BooleanField(
        default=False, help_text="Save even if the same payment was saved a moment ago"
    )


class PaymentCorrectSerializer(serializers.Serializer):
    """What to change on a mistaken payment; fields left out keep their value."""

    reason = serializers.CharField(max_length=200)
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False)
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), required=False, allow_null=True
    )
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"), required=False)
    mode = serializers.ChoiceField(choices=PaymentMode.choices, required=False)
    wallet = serializers.ChoiceField(choices=Wallet.choices, required=False, allow_blank=True)
    bank_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    reference_no = serializers.CharField(max_length=60, required=False, allow_blank=True)
    cheque_no = serializers.CharField(max_length=30, required=False, allow_blank=True)
    cheque_date = serializers.DateField(required=False, allow_null=True)
    payment_date = serializers.DateField(required=False)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)


class CustomerNameSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class LedgerEntrySerializer(serializers.Serializer):
    """One line of the shop-wide day book."""

    id = serializers.IntegerField()
    entry_date = serializers.DateField()
    entry_date_bs = BSDateField(source="entry_date")
    entry_type = serializers.CharField()
    entry_type_label = serializers.CharField(source="get_entry_type_display")
    customer = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()
    invoice_id = serializers.IntegerField(allow_null=True)
    payment_id = serializers.IntegerField(allow_null=True)
    order_id = serializers.IntegerField(allow_null=True)
    narration = serializers.CharField()
    debit = serializers.DecimalField(**MONEY)
    credit = serializers.DecimalField(**MONEY)
    created_by = UserRefSerializer(allow_null=True)
    created_at = serializers.DateTimeField()

    @extend_schema_field(CustomerNameSerializer)
    def get_customer(self, obj) -> dict:
        return {"id": obj.customer_id, "name": obj.customer.name}

    def get_reference(self, obj) -> str:
        if obj.invoice_id:
            return obj.invoice.invoice_no
        if obj.payment_id:
            return obj.payment.receipt_no
        if obj.order_id:
            return obj.order.order_no
        return ""


class LedgerSummaryRowSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    customer_name = serializers.CharField()
    phone = serializers.CharField()
    address = serializers.CharField()
    opening_balance = serializers.DecimalField(**MONEY)
    debit = serializers.DecimalField(**MONEY)
    credit = serializers.DecimalField(**MONEY)
    closing_balance = serializers.DecimalField(**MONEY)
    last_entry_date = serializers.DateField(allow_null=True)
    last_payment_date = serializers.DateField(allow_null=True)


class LedgerSummaryTotalsSerializer(serializers.Serializer):
    customers = serializers.IntegerField()
    opening_balance = serializers.DecimalField(**MONEY)
    debit = serializers.DecimalField(**MONEY)
    credit = serializers.DecimalField(**MONEY)
    closing_balance = serializers.DecimalField(**MONEY)
    receivable = serializers.DecimalField(**MONEY, help_text="Sum of closing dues")
    advances = serializers.DecimalField(**MONEY, help_text="Sum of advances held")


class LedgerSummarySerializer(serializers.Serializer):
    date_from = serializers.DateField(allow_null=True)
    date_to = serializers.DateField()
    count = serializers.IntegerField(help_text="Customers in the whole result")
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    ordering = serializers.CharField()
    rows = LedgerSummaryRowSerializer(many=True, help_text="This page of customers")
    totals = LedgerSummaryTotalsSerializer(help_text="Totals over all pages")
