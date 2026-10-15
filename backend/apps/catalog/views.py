from __future__ import annotations

from django.db.models import ProtectedError
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.activity import log_activity
from apps.core.exceptions import BusinessError
from apps.core.permissions import Perm

from .models import AddOn, MediaType
from .serializers import AddOnSerializer, MediaTypeSerializer, RateHistorySerializer

CATALOG_PERMS = {
    "list": Perm.CATALOG_VIEW,
    "retrieve": Perm.CATALOG_VIEW,
    "create": Perm.CATALOG_MANAGE,
    "update": Perm.CATALOG_MANAGE,
    "partial_update": Perm.CATALOG_MANAGE,
    "destroy": Perm.CATALOG_MANAGE,
    "history": Perm.CATALOG_MANAGE,
}


class _CatalogViewSet(viewsets.ModelViewSet):
    filterset_fields = ["is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["sort_order", "name"]
    required_perms = CATALOG_PERMS
    pagination_class = None  # the rate card is small and always shown whole
    entity = "catalog"

    def perform_create(self, serializer):
        obj = serializer.save()
        log_activity(self.request.user, f"{self.entity}.created", obj, request=self.request)

    def perform_update(self, serializer):
        obj = serializer.save()
        log_activity(
            self.request.user,
            f"{self.entity}.updated",
            obj,
            metadata={k: str(v) for k, v in serializer.validated_data.items()},
            request=self.request,
        )

    def perform_destroy(self, instance):
        try:
            label = str(instance)
            instance.delete()
        except ProtectedError as exc:
            raise BusinessError(
                f"'{instance}' is used on orders, so it cannot be deleted. "
                "Mark it inactive instead."
            ) from exc
        log_activity(
            self.request.user, f"{self.entity}.deleted", None, message=label, request=self.request
        )

    def _history(self, rate_field: str, min_field: str | None):
        obj = self.get_object()
        rows = []
        for record in obj.history.select_related("history_user").order_by("-history_date")[:100]:
            rows.append(
                {
                    "history_id": record.history_id,
                    "history_date": record.history_date,
                    "history_type": record.get_history_type_display(),
                    "changed_by": str(record.history_user) if record.history_user else None,
                    "rate": getattr(record, rate_field),
                    "min_sqft": getattr(record, min_field) if min_field else None,
                    "is_active": record.is_active,
                }
            )
        return Response(RateHistorySerializer(rows, many=True).data)


class MediaTypeViewSet(_CatalogViewSet):
    """Printable media on the rate card, priced per sq ft."""

    queryset = MediaType.objects.select_related("material")
    serializer_class = MediaTypeSerializer
    entity = "media_type"

    @extend_schema(responses=RateHistorySerializer(many=True))
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """Rate changes over time (who changed what, and when)."""
        return self._history("rate_per_sqft", "min_sqft")


class AddOnViewSet(_CatalogViewSet):
    """Extra charges: design, eyelets, framing, lamination, pockets, urgent."""

    queryset = AddOn.objects.all()
    serializer_class = AddOnSerializer
    entity = "addon"

    @extend_schema(responses=RateHistorySerializer(many=True))
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        return self._history("rate", None)
