from __future__ import annotations

import datetime as dt

import django_filters
from django.db.models import Count, OuterRef, Prefetch, Subquery
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.billing.models import Invoice, InvoiceStatus
from apps.billing.selectors import paid_subquery
from apps.billing.serializers import InvoiceDetailSerializer, PaymentSerializer
from apps.catalog.pricing import discount_percent
from apps.core.dates import local_today
from apps.core.documents import pdf_response, render_pdf
from apps.core.exceptions import BusinessError
from apps.core.permissions import Perm
from apps.core.serializers import ReasonSerializer
from apps.production.models import Job

from . import services
from .models import Order, OrderItem, OrderStatus
from .serializers import (
    DeliverSerializer,
    IssueInvoiceSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderWriteSerializer,
    PricePreviewRequestSerializer,
    PricePreviewSerializer,
)


class OrderFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=OrderStatus.choices)
    date_from = django_filters.DateFilter(field_name="order_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="order_date", lookup_expr="lte")
    has_balance = django_filters.BooleanFilter(method="filter_has_balance")
    open = django_filters.BooleanFilter(method="filter_open", label="Not delivered or cancelled")

    class Meta:
        model = Order
        fields = ["customer", "is_urgent", "created_by"]

    def filter_has_balance(self, queryset, name, value):
        from django.db.models import F

        qs = queryset.exclude(status__in=[OrderStatus.CANCELLED, OrderStatus.QUOTATION])
        return (
            qs.filter(total__gt=F("paid_amount"))
            if value
            else qs.filter(total__lte=F("paid_amount"))
        )

    def filter_open(self, queryset, name, value):
        closed = [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
        return queryset.exclude(status__in=closed) if value else queryset.filter(status__in=closed)


def _order_input(data: dict) -> services.OrderInput:
    return services.OrderInput(
        items=[services.item_input_from_data(i) for i in data["items"]],
        discount_type=data.get("discount_type", "none"),
        discount_value=data.get("discount_value", 0),
    )


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Quotations and orders. Status changes go through explicit actions."""

    filterset_class = OrderFilter
    search_fields = ["order_no", "customer__name", "customer__phone", "items__description"]
    ordering_fields = ["created_at", "order_date", "deadline", "total"]
    ordering = ["-created_at"]
    required_perms = {
        "list": Perm.ORDERS_VIEW,
        "retrieve": Perm.ORDERS_VIEW,
        "create": Perm.ORDERS_MANAGE,
        "update": Perm.ORDERS_MANAGE,
        "price_preview": Perm.ORDERS_VIEW,
        "confirm": Perm.ORDERS_MANAGE,
        "cancel": Perm.ORDERS_MANAGE,
        "deliver": Perm.ORDERS_MANAGE,
        "invoice": Perm.DOCUMENTS_ISSUE,
        "quotation_pdf": Perm.DOCUMENTS_ISSUE,
        "job_tickets_pdf": Perm.PRODUCTION_VIEW,
    }
    http_method_names = ["get", "post", "put", "head", "options"]

    def get_queryset(self):
        active_invoice = Invoice.objects.filter(
            order=OuterRef("pk"), status=InvoiceStatus.ISSUED
        ).values("invoice_no")[:1]
        qs = (
            Order.objects.select_related("customer", "created_by")
            .annotate(
                paid_amount=paid_subquery(),
                items_count=Count("items", distinct=True),
                invoice_no=Subquery(active_invoice),
            )
            .distinct()
        )
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch(
                    "items",
                    queryset=OrderItem.objects.select_related("job").prefetch_related("addons"),
                ),
                "payments",
                "invoices",
            )
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update"):
            return OrderWriteSerializer
        if self.action == "retrieve":
            return OrderDetailSerializer
        return OrderListSerializer

    def _detail(self, order: Order, code: int = status.HTTP_200_OK) -> Response:
        fresh = (
            self.get_queryset()
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=OrderItem.objects.select_related("job").prefetch_related("addons"),
                ),
                "payments",
                "invoices",
            )
            .get(pk=order.pk)
        )
        return Response(
            OrderDetailSerializer(fresh, context=self.get_serializer_context()).data, status=code
        )

    @extend_schema(request=OrderWriteSerializer, responses={201: OrderDetailSerializer})
    def create(self, request, *args, **kwargs):
        serializer = OrderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order = services.create_order(
            user=request.user,
            customer=data["customer"],
            data=_order_input(data),
            deadline=data.get("deadline"),
            is_urgent=data.get("is_urgent", False),
            notes=data.get("notes", ""),
            confirm=data.get("confirm", False),
            request=request,
        )
        return self._detail(order, status.HTTP_201_CREATED)

    @extend_schema(request=OrderWriteSerializer, responses=OrderDetailSerializer)
    def update(self, request, *args, **kwargs):
        order = self.get_object()
        serializer = OrderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["customer"].pk != order.customer_id:
            raise BusinessError({"customer": ["The customer of an order cannot be changed."]})
        order = services.update_order(
            order=order,
            user=request.user,
            data=_order_input(data),
            deadline=data.get("deadline"),
            is_urgent=data.get("is_urgent", False),
            notes=data.get("notes", ""),
            request=request,
        )
        return self._detail(order)

    @extend_schema(request=PricePreviewRequestSerializer, responses=PricePreviewSerializer)
    @action(detail=False, methods=["post"], url_path="price-preview")
    def price_preview(self, request):
        """Live calculator: price items without saving anything."""
        serializer = PricePreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        pricing = services.calculate(_order_input(data), order=data.get("order"))
        limit = request.user.discount_limit()
        payload = {
            "items": [
                {
                    **{
                        f: getattr(r, f)
                        for f in (
                            "width_ft",
                            "height_ft",
                            "sqft",
                            "billable_sqft",
                            "min_applied",
                            "min_sqft",
                            "rate",
                            "quantity",
                            "base_amount",
                            "addons",
                            "addons_amount",
                            "line_total",
                        )
                    },
                    "total_sqft": r.total_sqft,
                    "total_billable_sqft": r.total_billable_sqft,
                }
                for r in pricing.items
            ],
            "totals": pricing.totals,
            "warnings": list(pricing.warnings),
            "discount_percent": discount_percent(
                pricing.totals.subtotal, pricing.totals.discount_amount
            ),
            "discount_limit": limit,
        }
        return Response(PricePreviewSerializer(payload).data)

    @extend_schema(request=None, responses=OrderDetailSerializer)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Confirm a quotation; opens one production job per item."""
        order = services.confirm_order(order=self.get_object(), user=request.user, request=request)
        return self._detail(order)

    @extend_schema(request=ReasonSerializer, responses=OrderDetailSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.cancel_order(
            order=self.get_object(),
            user=request.user,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return self._detail(order)

    @extend_schema(request=IssueInvoiceSerializer, responses={201: InvoiceDetailSerializer})
    @action(detail=True, methods=["post"])
    def invoice(self, request, pk=None):
        """Issue the tax invoice for this order."""
        from apps.billing import services as billing

        serializer = IssueInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = billing.issue_invoice(
            order=self.get_object(),
            user=request.user,
            notes=serializer.validated_data.get("notes", ""),
            request=request,
        )
        return Response(InvoiceDetailSerializer(invoice).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=DeliverSerializer,
        responses=OpenApiResponse(
            response=OrderDetailSerializer, description="Order after delivery"
        ),
    )
    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        """Counter checkout: issue the invoice if needed, take payment, mark delivered."""
        serializer = DeliverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = services.deliver_order(
            order=self.get_object(),
            user=request.user,
            issue_invoice=data.get("issue_invoice", True),
            payment=data.get("payment"),
            note=data.get("note", ""),
            request=request,
        )
        response = self._detail(result["order"])
        if result["payment"] is not None:
            response.data["delivered_payment"] = PaymentSerializer(result["payment"]).data
        return response

    @extend_schema(responses={(200, "application/pdf"): bytes})
    @action(detail=True, methods=["get"], url_path="quotation-pdf")
    def quotation_pdf(self, request, pk=None):
        """Printable quotation / estimate (A4)."""
        order = self.get_object()
        items = order.items.prefetch_related("addons").order_by("line_no")
        valid_until = order.order_date + dt.timedelta(days=_shop_validity_days())
        pdf = render_pdf(
            "documents/quotation.html",
            {"order": order, "items": items, "valid_until": valid_until, "today": local_today()},
        )
        return pdf_response(pdf, f"quotation-{order.order_no}")

    @extend_schema(responses={(200, "application/pdf"): bytes})
    @action(detail=True, methods=["get"], url_path="job-tickets-pdf")
    def job_tickets_pdf(self, request, pk=None):
        """All job tickets for this order (A5, one per page)."""
        order = self.get_object()
        jobs = (
            Job.objects.filter(order=order)
            .select_related("order__customer", "order_item", "operator")
            .prefetch_related("order_item__addons")
            .order_by("order_item__line_no")
        )
        pdf = render_pdf("documents/job_ticket.html", {"jobs": jobs})
        return pdf_response(pdf, f"job-tickets-{order.order_no}")


def _shop_validity_days() -> int:
    from apps.core.models import ShopSettings

    return ShopSettings.load().quotation_validity_days
