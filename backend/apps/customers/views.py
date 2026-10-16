from __future__ import annotations

import django_filters
from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.billing import services as billing_services
from apps.billing.selectors import balance_subquery, customer_statement
from apps.catalog.models import MediaType
from apps.core.activity import log_activity
from apps.core.dates import local_today
from apps.core.documents import pdf_response, render_pdf, xlsx_response
from apps.core.params import output_format, parse_range
from apps.core.permissions import Perm
from apps.orders.selectors import last_rates_for
from apps.orders.serializers import CustomerRateSerializer
from apps.reports.exporters import report_to_xlsx
from apps.reports.tables import Column, Metric, Report, Table, period_label

from .models import Customer
from .serializers import (
    CustomerSerializer,
    LedgerAdjustmentSerializer,
    StatementSerializer,
)


class CustomerFilter(django_filters.FilterSet):
    has_due = django_filters.BooleanFilter(method="filter_has_due")

    class Meta:
        model = Customer
        fields = ["is_active", "customer_type"]

    def filter_has_due(self, queryset, name, value):
        return (
            queryset.filter(ledger_balance__gt=0)
            if value
            else queryset.filter(ledger_balance__lte=0)
        )


class CustomerViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Customers with their running balance. Customers are deactivated, never deleted."""

    serializer_class = CustomerSerializer
    filterset_class = CustomerFilter
    search_fields = ["name", "phone", "alt_phone", "pan_no", "address"]
    ordering_fields = ["name", "ledger_balance", "created_at"]
    ordering = ["name"]
    required_perms = {
        "list": Perm.CUSTOMERS_VIEW,
        "retrieve": Perm.CUSTOMERS_VIEW,
        "create": Perm.CUSTOMERS_MANAGE,
        "update": Perm.CUSTOMERS_MANAGE,
        "partial_update": Perm.CUSTOMERS_MANAGE,
        "statement": Perm.LEDGER_VIEW,
        "adjust_balance": Perm.LEDGER_MANAGE,
        "rates": Perm.ORDERS_VIEW,
    }

    def get_queryset(self):
        return Customer.objects.annotate(ledger_balance=balance_subquery())

    @transaction.atomic
    def perform_create(self, serializer):
        opening = serializer.validated_data.pop("opening_balance", None)
        customer = serializer.save(created_by=self.request.user)
        if opening:
            billing_services.post_opening_balance(
                customer=customer, amount=opening, user=self.request.user
            )
        log_activity(self.request.user, "customer.created", customer, request=self.request)

    def perform_update(self, serializer):
        customer = serializer.save()
        log_activity(
            self.request.user,
            "customer.updated",
            customer,
            metadata={"fields": sorted(serializer.validated_data)},
            request=self.request,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="Start date (AD, YYYY-MM-DD)"),
            OpenApiParameter("to", str, description="End date (AD, YYYY-MM-DD)"),
            OpenApiParameter("export", str, enum=["json", "pdf", "xlsx"]),
        ],
        responses=StatementSerializer,
    )
    @action(detail=True, methods=["get"])
    def statement(self, request, pk=None):
        """Ledger statement with running balance; printable as PDF or Excel."""
        customer = self.get_object()
        date_from, date_to = parse_range(request.query_params, None, local_today())
        data = customer_statement(customer, date_from, date_to)
        fmt = output_format(request.query_params)
        if fmt == "pdf":
            pdf = render_pdf(
                "documents/statement.html",
                {
                    "customer": customer,
                    "statement": data,
                    "period": period_label(date_from, date_to),
                },
            )
            return pdf_response(pdf, f"statement-{customer.name}")
        if fmt == "xlsx":
            report = Report(
                slug="statement",
                title=f"Statement: {customer.name}",
                period=period_label(date_from, date_to),
                summary=[
                    Metric("Opening balance", data["opening_balance"]),
                    Metric("Closing balance", data["closing_balance"]),
                ],
                tables=[
                    Table(
                        title="Entries",
                        columns=[
                            Column("date", "Date (AD)", "date"),
                            Column("date_bs", "Date (BS)"),
                            Column("entry_type_label", "Type"),
                            Column("reference", "Reference"),
                            Column("narration", "Details"),
                            Column("debit", "Debit", "money"),
                            Column("credit", "Credit", "money"),
                            Column("balance", "Balance", "money"),
                        ],
                        rows=data["entries"],
                        totals={
                            "narration": "Total",
                            "debit": data["total_debit"],
                            "credit": data["total_credit"],
                            "balance": data["closing_balance"],
                        },
                    )
                ],
            )
            return xlsx_response(report_to_xlsx(report), f"statement-{customer.name}")
        return Response(StatementSerializer(data).data)

    @extend_schema(responses=CustomerRateSerializer(many=True))
    @action(detail=True, methods=["get"])
    def rates(self, request, pk=None):
        """The last rate this customer was charged for each item, beside today's rate card."""
        customer = self.get_object()
        last = last_rates_for(customer)
        card = dict(MediaType.objects.filter(pk__in=last).values_list("pk", "rate"))
        rows = sorted(last.values(), key=lambda r: r.order_date, reverse=True)
        data = [{**r.__dict__, "card_rate": card.get(r.media_type_id)} for r in rows]
        return Response(CustomerRateSerializer(data, many=True).data)

    @extend_schema(request=LedgerAdjustmentSerializer, responses=CustomerSerializer)
    @action(detail=True, methods=["post"], url_path="adjust-balance")
    def adjust_balance(self, request, pk=None):
        """Owner-only correction to a customer's balance, with a reason."""
        customer = self.get_object()
        serializer = LedgerAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        billing_services.post_adjustment(
            customer=customer, user=request.user, request=request, **serializer.validated_data
        )
        customer = self.get_queryset().get(pk=customer.pk)
        return Response(CustomerSerializer(customer).data)
