from __future__ import annotations

import django_filters
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.documents import PAGE_SIZES, pdf_response, render_pdf
from apps.core.permissions import Perm
from apps.core.serializers import ReasonSerializer

from . import services
from .models import Invoice, InvoiceStatus, Payment, PaymentMode, PaymentStatus
from .selectors import order_paid_amount
from .serializers import (
    InvoiceCreateSerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
)


def _size(request, allowed=("a4", "a5", "80mm"), default="a4") -> str:
    size = (request.query_params.get("size") or default).lower()
    if size not in allowed:
        raise ValidationError({"size": [f"Choose one of: {', '.join(allowed)}."]})
    return size


class InvoiceFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="invoice_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="invoice_date", lookup_expr="lte")

    class Meta:
        model = Invoice
        fields = ["status", "customer", "order", "fiscal_year"]


class InvoiceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Tax invoices. Never deleted: cancel with a reason instead."""

    filterset_class = InvoiceFilter
    search_fields = ["invoice_no", "customer_name", "customer_phone", "order__order_no"]
    ordering_fields = ["invoice_date", "sequence", "total"]
    ordering = ["-invoice_date", "-sequence"]
    required_perms = {
        "list": Perm.INVOICES_VIEW,
        "retrieve": Perm.INVOICES_VIEW,
        "create": Perm.DOCUMENTS_ISSUE,
        "cancel": Perm.INVOICES_CANCEL,
        "print": Perm.DOCUMENTS_ISSUE,
    }

    def get_queryset(self):
        qs = Invoice.objects.select_related("order", "issued_by", "cancelled_by")
        if self.action in ("retrieve", "print"):
            qs = qs.prefetch_related("lines")
        return qs

    def get_serializer_class(self):
        return InvoiceDetailSerializer if self.action != "list" else InvoiceListSerializer

    @extend_schema(request=InvoiceCreateSerializer, responses={201: InvoiceDetailSerializer})
    def create(self, request, *args, **kwargs):
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = services.issue_invoice(
            order=serializer.validated_data["order"],
            user=request.user,
            notes=serializer.validated_data.get("notes", ""),
            request=request,
        )
        return Response(InvoiceDetailSerializer(invoice).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ReasonSerializer, responses=InvoiceDetailSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel with a reason (owner only). The number is kept and the ledger reversed."""
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = services.cancel_invoice(
            invoice=self.get_object(),
            user=request.user,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(InvoiceDetailSerializer(invoice).data)

    @extend_schema(
        request=None,
        parameters=[OpenApiParameter("size", str, enum=list(PAGE_SIZES))],
        responses={(200, "application/pdf"): bytes},
    )
    @action(detail=True, methods=["post"])
    def print(self, request, pk=None):
        """Render the invoice for printing. Prints after the first are marked as copies."""
        size = _size(request)
        invoice = self.get_object()
        count = services.record_invoice_print(
            invoice=invoice, user=request.user, size=size, request=request
        )
        paid = order_paid_amount(invoice.order)
        context = {
            "invoice": invoice,
            "lines": invoice.lines.all(),
            "size": size,
            "page_size": PAGE_SIZES[size],
            "copy_number": count - 1 if count > 1 else 0,
            "paid": paid,
            "balance": invoice.total - paid if invoice.status == InvoiceStatus.ISSUED else 0,
        }
        template = "documents/invoice_thermal.html" if size == "80mm" else "documents/invoice.html"
        return pdf_response(
            render_pdf(template, context, thermal=size == "80mm"), f"invoice-{invoice.invoice_no}"
        )


class PaymentFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")
    mode = django_filters.ChoiceFilter(choices=PaymentMode.choices)
    status = django_filters.ChoiceFilter(choices=PaymentStatus.choices)

    class Meta:
        model = Payment
        fields = ["customer", "order", "received_by", "is_advance"]


class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Money received: advances, settlements and payments on account."""

    serializer_class = PaymentSerializer
    filterset_class = PaymentFilter
    search_fields = ["receipt_no", "customer__name", "customer__phone", "reference_no", "cheque_no"]
    ordering_fields = ["payment_date", "amount", "created_at"]
    ordering = ["-payment_date", "-id"]
    required_perms = {
        "list": Perm.PAYMENTS_VIEW,
        "retrieve": Perm.PAYMENTS_VIEW,
        "create": Perm.PAYMENTS_RECEIVE,
        "void": Perm.PAYMENTS_VOID,
        "receipt": Perm.PAYMENTS_VIEW,
    }

    def get_queryset(self):
        return Payment.objects.select_related("customer", "order", "received_by")

    @extend_schema(request=PaymentCreateSerializer, responses={201: PaymentSerializer})
    def create(self, request, *args, **kwargs):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        payment = services.receive_payment(
            user=request.user,
            request=request,
            customer=data.pop("customer"),
            order=data.pop("order", None),
            **{k: v for k, v in data.items() if v is not None},
        )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ReasonSerializer, responses=PaymentSerializer)
    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        """Void a mistaken payment or bounced cheque (owner only)."""
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = services.void_payment(
            payment=self.get_object(),
            user=request.user,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(PaymentSerializer(payment).data)

    @extend_schema(
        parameters=[OpenApiParameter("size", str, enum=["a5", "80mm"])],
        responses={(200, "application/pdf"): bytes},
    )
    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        """Payment receipt (A5 or 3-inch thermal)."""
        size = _size(request, allowed=("a5", "80mm"), default="a5")
        payment = self.get_object()
        from .selectors import customer_balance

        context = {
            "payment": payment,
            "size": size,
            "page_size": PAGE_SIZES[size],
            "customer_balance": customer_balance(payment.customer),
        }
        return pdf_response(
            render_pdf("documents/receipt.html", context, thermal=size == "80mm"),
            f"receipt-{payment.receipt_no}",
        )
