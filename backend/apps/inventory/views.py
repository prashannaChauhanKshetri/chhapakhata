from __future__ import annotations

import django_filters
from django.db.models import Count, F, ProtectedError, Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.activity import log_activity
from apps.core.exceptions import BusinessError
from apps.core.permissions import Perm

from . import services
from .models import Purchase, Roll, RollStatus, StockItem, StockMovement, Supplier
from .serializers import (
    AdjustStockSerializer,
    FinishRollSerializer,
    OpeningStockSerializer,
    PurchaseInputSerializer,
    PurchaseSerializer,
    QuantityReasonSerializer,
    RollSerializer,
    StockItemSerializer,
    StockMovementSerializer,
    SupplierSerializer,
)


class StockItemFilter(django_filters.FilterSet):
    low = django_filters.BooleanFilter(method="filter_low", label="Below low-stock level")

    class Meta:
        model = StockItem
        fields = ["kind", "is_active"]

    def filter_low(self, queryset, name, value):
        low = Q(low_stock_level__gt=0, on_hand__lt=F("low_stock_level"))
        return queryset.filter(low) if value else queryset.exclude(low)


class StockItemViewSet(viewsets.ModelViewSet):
    """Stock items. Quantities change only through purchases, usage and adjustments."""

    serializer_class = StockItemSerializer
    filterset_class = StockItemFilter
    search_fields = ["name", "notes"]
    ordering_fields = ["name", "kind", "on_hand"]
    ordering = ["kind", "name"]
    pagination_class = None
    required_perms = {
        "list": Perm.INVENTORY_VIEW,
        "retrieve": Perm.INVENTORY_VIEW,
        "create": Perm.INVENTORY_MANAGE,
        "update": Perm.INVENTORY_MANAGE,
        "partial_update": Perm.INVENTORY_MANAGE,
        "destroy": Perm.INVENTORY_MANAGE,
        "opening": Perm.INVENTORY_MANAGE,
        "adjust": Perm.INVENTORY_MANAGE,
        "wastage": Perm.INVENTORY_RECORD_USAGE,
        "usage": Perm.INVENTORY_RECORD_USAGE,
    }

    def get_queryset(self):
        return StockItem.objects.annotate(
            active_rolls=Count("rolls", filter=Q(rolls__status=RollStatus.ACTIVE))
        )

    def perform_create(self, serializer):
        item = serializer.save()
        log_activity(self.request.user, "stock_item.created", item, request=self.request)

    def perform_update(self, serializer):
        item = serializer.save()
        log_activity(
            self.request.user,
            "stock_item.updated",
            item,
            metadata={k: str(v) for k, v in serializer.validated_data.items()},
            request=self.request,
        )

    def perform_destroy(self, instance):
        if instance.movements.exists():
            raise BusinessError("This item has stock history. Mark it inactive instead.")
        try:
            instance.delete()
        except ProtectedError as exc:
            raise BusinessError("This item is in use. Mark it inactive instead.") from exc

    def _item_response(self, item: StockItem) -> Response:
        return Response(StockItemSerializer(self.get_queryset().get(pk=item.pk)).data)

    @extend_schema(request=OpeningStockSerializer, responses=StockItemSerializer)
    @action(detail=True, methods=["post"])
    def opening(self, request, pk=None):
        """Bring existing stock (or part-used rolls) into the system at go-live."""
        serializer = OpeningStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        item = self.get_object()
        services.add_opening_stock(
            user=request.user,
            stock_item=item,
            quantity=data.get("quantity"),
            rolls=[services.RollSpec(**r) for r in data.get("rolls", [])],
            reason=data.get("reason") or "Opening stock",
        )
        return self._item_response(item)

    @extend_schema(request=AdjustStockSerializer, responses=StockItemSerializer)
    @action(detail=True, methods=["post"])
    def adjust(self, request, pk=None):
        """Correct stock after a physical count (owner only, reason required)."""
        serializer = AdjustStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = self.get_object()
        services.adjust_stock(
            user=request.user, stock_item=item, request=request, **serializer.validated_data
        )
        return self._item_response(item)

    @extend_schema(request=QuantityReasonSerializer, responses=StockItemSerializer)
    @action(detail=True, methods=["post"])
    def wastage(self, request, pk=None):
        """Record misprints, test prints or trimming."""
        serializer = QuantityReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = self.get_object()
        services.record_wastage(
            user=request.user, stock_item=item, request=request, **serializer.validated_data
        )
        return self._item_response(item)

    @extend_schema(request=QuantityReasonSerializer, responses=StockItemSerializer)
    @action(detail=True, methods=["post"])
    def usage(self, request, pk=None):
        """Record general usage, e.g. ink, eyelets or frame material."""
        serializer = QuantityReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = self.get_object()
        services.record_usage(
            user=request.user, stock_item=item, request=request, **serializer.validated_data
        )
        return self._item_response(item)


class RollViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Roll.objects.select_related("stock_item")
    serializer_class = RollSerializer
    filterset_fields = ["stock_item", "status"]
    search_fields = ["code", "stock_item__name"]
    ordering_fields = ["code", "remaining_sqft", "width_ft", "created_at"]
    ordering = ["status", "stock_item__name", "code"]
    required_perms = {
        "list": Perm.INVENTORY_VIEW,
        "retrieve": Perm.INVENTORY_VIEW,
        "finish": Perm.INVENTORY_MANAGE,
    }

    @extend_schema(request=FinishRollSerializer, responses=RollSerializer)
    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        """Mark a roll finished; any leftover is written off as wastage."""
        serializer = FinishRollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        roll = services.finish_roll(
            user=request.user, roll=self.get_object(), request=request, **serializer.validated_data
        )
        return Response(RollSerializer(roll).data)


class SupplierViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name", "phone"]
    pagination_class = None
    required_perms = Perm.INVENTORY_MANAGE


class PurchaseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Stock received from suppliers."""

    queryset = Purchase.objects.select_related("supplier", "created_by").prefetch_related(
        "lines__stock_item"
    )
    serializer_class = PurchaseSerializer
    filterset_fields = ["supplier"]
    search_fields = ["purchase_no", "bill_no", "supplier__name"]
    ordering_fields = ["purchase_date", "total_amount"]
    ordering = ["-purchase_date", "-id"]
    required_perms = Perm.INVENTORY_MANAGE

    @extend_schema(request=PurchaseInputSerializer, responses={201: PurchaseSerializer})
    def create(self, request, *args, **kwargs):
        serializer = PurchaseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        purchase = services.receive_purchase(
            user=request.user,
            supplier=data["supplier"],
            purchase_date=data["purchase_date"],
            bill_no=data.get("bill_no", ""),
            notes=data.get("notes", ""),
            lines=[dict(line) for line in data["lines"]],
            request=request,
        )
        return Response(
            PurchaseSerializer(self.get_queryset().get(pk=purchase.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class StockMovementFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = StockMovement
        fields = ["stock_item", "roll", "movement_type", "job", "created_by"]


class StockMovementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read-only stock ledger."""

    queryset = StockMovement.objects.select_related("stock_item", "roll", "job", "created_by")
    serializer_class = StockMovementSerializer
    filterset_class = StockMovementFilter
    search_fields = ["reason", "stock_item__name", "roll__code", "job__job_no"]
    ordering = ["-created_at", "-id"]
    required_perms = Perm.INVENTORY_VIEW
