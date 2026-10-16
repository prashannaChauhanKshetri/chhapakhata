from __future__ import annotations

from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.billing.models import InvoiceStatus, PaymentMode, Wallet
from apps.catalog.models import AddOn, LengthUnit, MediaType
from apps.core.permissions import Perm
from apps.core.serializers import BSDateField, UserRefSerializer
from apps.customers.models import Customer
from apps.customers.serializers import CustomerRefSerializer

from .models import DiscountType, Order, OrderItem, OrderItemAddOn, OrderStatus
from .services import EDITABLE_STATUSES

MONEY = {"max_digits": 12, "decimal_places": 2}


# ---------- read ----------


class OrderItemAddOnSerializer(serializers.ModelSerializer):
    basis_label = serializers.CharField(source="get_basis_display", read_only=True)

    class Meta:
        model = OrderItemAddOn
        fields = ["id", "addon", "name", "basis", "basis_label", "rate", "quantity", "amount"]


class JobRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    job_no = serializers.CharField()
    stage = serializers.IntegerField()
    stage_label = serializers.CharField(source="get_stage_display")
    material_recorded = serializers.BooleanField()


class OrderItemSerializer(serializers.ModelSerializer):
    addons = OrderItemAddOnSerializer(many=True, read_only=True)
    rate_source_label = serializers.CharField(source="get_rate_source_display", read_only=True)
    has_size = serializers.BooleanField(read_only=True)
    total_sqft = serializers.DecimalField(read_only=True, **MONEY)
    total_billable_sqft = serializers.DecimalField(read_only=True, **MONEY)
    min_applied = serializers.BooleanField(read_only=True)
    size_label = serializers.CharField(read_only=True)
    job = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "line_no",
            "media_type",
            "media_name",
            "description",
            "pricing_unit",
            "width",
            "height",
            "unit",
            "has_size",
            "size_label",
            "quantity",
            "width_ft",
            "height_ft",
            "sqft",
            "billable_sqft",
            "total_sqft",
            "total_billable_sqft",
            "min_applied",
            "rate",
            "rate_source",
            "rate_source_label",
            "card_rate",
            "min_sqft",
            "base_amount",
            "addons_amount",
            "line_total",
            "finishing",
            "design_file_ref",
            "addons",
            "job",
        ]

    @extend_schema_field(JobRefSerializer(allow_null=True))
    def get_job(self, obj: OrderItem) -> dict | None:
        job = getattr(obj, "job", None)
        return JobRefSerializer(job).data if job is not None else None


class OrderListSerializer(serializers.ModelSerializer):
    customer = CustomerRefSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    order_date_bs = BSDateField(source="order_date")
    paid_amount = serializers.DecimalField(read_only=True, **MONEY)
    balance_due = serializers.SerializerMethodField()
    items_count = serializers.IntegerField(read_only=True)
    invoice_no = serializers.CharField(read_only=True, allow_null=True)
    created_by = UserRefSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_no",
            "customer",
            "status",
            "status_label",
            "source",
            "source_label",
            "order_date",
            "order_date_bs",
            "deadline",
            "is_urgent",
            "total",
            "paid_amount",
            "balance_due",
            "items_count",
            "invoice_no",
            "created_by",
            "created_at",
        ]

    def get_balance_due(self, obj: Order) -> str:
        if obj.status in (OrderStatus.CANCELLED,):
            return "0.00"
        paid = getattr(obj, "paid_amount", Decimal("0"))
        return f"{obj.total - paid:.2f}"


class OrderPaymentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    receipt_no = serializers.CharField()
    amount = serializers.DecimalField(**MONEY)
    mode = serializers.CharField()
    mode_label = serializers.CharField()
    payment_date = serializers.DateField()
    is_advance = serializers.BooleanField()
    status = serializers.CharField()


class OrderInvoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    invoice_no = serializers.CharField()
    invoice_date = serializers.DateField()
    invoice_date_bs = serializers.CharField()
    total = serializers.DecimalField(**MONEY)
    status = serializers.CharField()


class OrderActionsSerializer(serializers.Serializer):
    can_edit = serializers.BooleanField()
    can_confirm = serializers.BooleanField()
    can_cancel = serializers.BooleanField()
    can_invoice = serializers.BooleanField()
    can_deliver = serializers.BooleanField()
    can_receive_payment = serializers.BooleanField()


class OrderDetailSerializer(OrderListSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payments = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    discount_type_label = serializers.CharField(source="get_discount_type_display", read_only=True)
    actions = serializers.SerializerMethodField()

    class Meta(OrderListSerializer.Meta):
        fields = [
            *OrderListSerializer.Meta.fields,
            "notes",
            "discount_type",
            "discount_type_label",
            "discount_value",
            "subtotal",
            "discount_amount",
            "taxable_amount",
            "vat_rate",
            "vat_amount",
            "round_off",
            "confirmed_at",
            "delivered_at",
            "cancelled_at",
            "cancel_reason",
            "items",
            "payments",
            "invoices",
            "actions",
        ]

    @extend_schema_field(OrderPaymentSerializer(many=True))
    def get_payments(self, obj: Order) -> list[dict]:
        rows = [
            {
                "id": p.pk,
                "receipt_no": p.receipt_no,
                "amount": p.amount,
                "mode": p.mode,
                "mode_label": p.mode_label,
                "payment_date": p.payment_date,
                "is_advance": p.is_advance,
                "status": p.status,
            }
            for p in obj.payments.order_by("payment_date", "id")
        ]
        return OrderPaymentSerializer(rows, many=True).data

    @extend_schema_field(OrderInvoiceSerializer(many=True))
    def get_invoices(self, obj: Order) -> list[dict]:
        return OrderInvoiceSerializer(obj.invoices.order_by("-created_at"), many=True).data

    @extend_schema_field(OrderActionsSerializer)
    def get_actions(self, obj: Order) -> dict:
        user = self.context["request"].user
        invoiced = any(i.status == InvoiceStatus.ISSUED for i in obj.invoices.all())
        live = obj.status not in (OrderStatus.CANCELLED, OrderStatus.QUOTATION)
        paid = getattr(obj, "paid_amount", Decimal("0"))
        return {
            "can_edit": user.can(Perm.ORDERS_MANAGE)
            and obj.status in EDITABLE_STATUSES
            and not invoiced,
            "can_confirm": user.can(Perm.ORDERS_MANAGE) and obj.status == OrderStatus.QUOTATION,
            "can_cancel": user.can(Perm.ORDERS_MANAGE)
            and obj.status not in (OrderStatus.CANCELLED, OrderStatus.DELIVERED)
            and not invoiced,
            "can_invoice": user.can(Perm.DOCUMENTS_ISSUE) and live and not invoiced,
            "can_deliver": user.can(Perm.ORDERS_MANAGE) and obj.status == OrderStatus.READY,
            "can_receive_payment": user.can(Perm.PAYMENTS_RECEIVE)
            and live
            and obj.total - paid > 0,
        }


# ---------- write ----------


class OrderItemAddOnWriteSerializer(serializers.Serializer):
    addon = serializers.PrimaryKeyRelatedField(queryset=AddOn.objects.all())
    quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), default=Decimal("1")
    )


class OrderItemWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    media_type = serializers.PrimaryKeyRelatedField(queryset=MediaType.objects.all())
    description = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
    width = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0"),
        default=Decimal("0"),
        help_text="Leave 0 for per-piece items without a size.",
    )
    height = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), default=Decimal("0")
    )
    unit = serializers.ChoiceField(choices=LengthUnit.choices, default=LengthUnit.FOOT)
    quantity = serializers.IntegerField(min_value=1, max_value=100000, default=1)
    rate = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        allow_null=True,
        default=None,
        help_text="Charge this rate instead of the rate card (e.g. the customer's last rate). "
        "Leave empty to use the rate card, or the rate the order was quoted at.",
    )
    finishing = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    design_file_ref = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    addons = OrderItemAddOnWriteSerializer(many=True, required=False, default=list)

    def validate_addons(self, value):
        ids = [a["addon"].pk for a in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Each add-on can be added once per item.")
        return value


class PricingInputSerializer(serializers.Serializer):
    discount_type = serializers.ChoiceField(choices=DiscountType.choices, default=DiscountType.NONE)
    discount_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), default=Decimal("0")
    )
    items = OrderItemWriteSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Add at least one item.")
        return value


class OrderWriteSerializer(PricingInputSerializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    is_urgent = serializers.BooleanField(default=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    confirm = serializers.BooleanField(
        default=False,
        write_only=True,
        help_text="Create as a confirmed order instead of a quotation.",
    )


class PricePreviewRequestSerializer(PricingInputSerializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        required=False,
        allow_null=True,
        help_text="Lets the calculator recognise the customer's last rates.",
    )
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        required=False,
        allow_null=True,
        help_text="When editing, keeps the rates the order was quoted at.",
    )


class AddOnResultSerializer(serializers.Serializer):
    addon = serializers.IntegerField(source="key")
    name = serializers.CharField()
    basis = serializers.CharField()
    rate = serializers.DecimalField(**MONEY)
    quantity = serializers.DecimalField(**MONEY)
    amount = serializers.DecimalField(**MONEY)


class ItemResultSerializer(serializers.Serializer):
    width_ft = serializers.DecimalField(max_digits=10, decimal_places=4)
    height_ft = serializers.DecimalField(max_digits=10, decimal_places=4)
    sqft = serializers.DecimalField(**MONEY)
    billable_sqft = serializers.DecimalField(**MONEY)
    total_sqft = serializers.DecimalField(**MONEY)
    total_billable_sqft = serializers.DecimalField(**MONEY)
    min_applied = serializers.BooleanField()
    min_sqft = serializers.DecimalField(**MONEY)
    rate = serializers.DecimalField(**MONEY)
    rate_source = serializers.CharField()
    card_rate = serializers.DecimalField(**MONEY)
    pricing_unit = serializers.CharField()
    quantity = serializers.IntegerField()
    base_amount = serializers.DecimalField(**MONEY)
    addons = AddOnResultSerializer(many=True)
    addons_amount = serializers.DecimalField(**MONEY)
    line_total = serializers.DecimalField(**MONEY)


class TotalsSerializer(serializers.Serializer):
    subtotal = serializers.DecimalField(**MONEY)
    discount_amount = serializers.DecimalField(**MONEY)
    taxable_amount = serializers.DecimalField(**MONEY)
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    vat_amount = serializers.DecimalField(**MONEY)
    round_off = serializers.DecimalField(**MONEY)
    total = serializers.DecimalField(**MONEY)


class CustomerRateSerializer(serializers.Serializer):
    media_type = serializers.IntegerField(source="media_type_id")
    media_name = serializers.CharField()
    pricing_unit = serializers.CharField()
    last_rate = serializers.DecimalField(source="rate", **MONEY)
    card_rate = serializers.DecimalField(**MONEY, allow_null=True)
    order = serializers.IntegerField(source="order_id")
    order_no = serializers.CharField()
    order_date = serializers.DateField()
    order_date_bs = BSDateField(source="order_date")
    times = serializers.IntegerField(help_text="Number of orders with this item")


class PricePreviewSerializer(serializers.Serializer):
    items = ItemResultSerializer(many=True)
    totals = TotalsSerializer()
    warnings = serializers.ListField(child=serializers.CharField())
    discount_percent = serializers.DecimalField(max_digits=6, decimal_places=2)
    discount_limit = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)


class PaymentInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))
    mode = serializers.ChoiceField(choices=PaymentMode.choices)
    wallet = serializers.ChoiceField(choices=Wallet.choices, required=False, allow_blank=True)
    bank_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    reference_no = serializers.CharField(max_length=60, required=False, allow_blank=True)
    cheque_no = serializers.CharField(max_length=30, required=False, allow_blank=True)
    cheque_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)


class DeliverSerializer(serializers.Serializer):
    issue_invoice = serializers.BooleanField(default=True)
    payment = PaymentInputSerializer(required=False, allow_null=True)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class IssueInvoiceSerializer(serializers.Serializer):
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
