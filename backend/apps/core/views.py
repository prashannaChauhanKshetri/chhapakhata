from __future__ import annotations

import datetime as dt
import mimetypes

import django_filters
from django.db import connection
from django.http import FileResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .activity import log_activity
from .dates import (
    bs_long,
    bs_month_range,
    bs_string,
    fiscal_year_for,
    from_bs,
    local_today,
    named_periods,
)
from .models import ActivityLog, ShopSettings
from .permissions import AUTHENTICATED, Perm
from .serializers import (
    IMAGE_FIELDS,
    ActivityLogSerializer,
    DateConversionSerializer,
    ShopSettingsSerializer,
)


class ShopSettingsView(APIView):
    """Shop identity, tax, pricing defaults and numbering. Everyone can read; owner edits."""

    required_perms = {"get": AUTHENTICATED, "patch": Perm.SETTINGS_MANAGE}
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(responses=ShopSettingsSerializer)
    def get(self, request):
        return Response(
            ShopSettingsSerializer(ShopSettings.load(), context={"request": request}).data
        )

    @extend_schema(request=ShopSettingsSerializer, responses=ShopSettingsSerializer)
    def patch(self, request):
        instance = ShopSettings.load()
        serializer = ShopSettingsSerializer(
            instance, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        log_activity(
            request.user,
            "settings.updated",
            instance,
            message="Shop settings updated",
            metadata={"fields": sorted(k for k in request.data if not k.startswith("remove_"))},
            request=request,
        )
        return Response(serializer.data)


class ShopImageView(APIView):
    """The shop's logo, stamp and signature, for signed-in users only.

    Any signed-in user may see the logo; the stamp and signature (which make a
    bill look genuine) are for the owner, who manages them in Settings.
    """

    required_perms = AUTHENTICATED

    @extend_schema(responses={(200, "image/*"): bytes})
    def get(self, request, field: str):
        if field not in IMAGE_FIELDS:
            raise NotFound()
        if field != "logo" and not request.user.can(Perm.SETTINGS_MANAGE):
            raise PermissionDenied()
        image = getattr(ShopSettings.load(), field)
        if not image:
            raise NotFound()
        try:
            handle = image.open("rb")
        except FileNotFoundError as exc:
            raise NotFound() from exc
        response = FileResponse(handle, content_type=mimetypes.guess_type(image.name)[0])
        response["Cache-Control"] = "private, max-age=86400"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class ActivityLogFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    action = django_filters.CharFilter(lookup_expr="startswith")

    class Meta:
        model = ActivityLog
        fields = ["actor", "action", "target_type", "target_id"]


class ActivityLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Audit trail of important actions (owner only)."""

    queryset = ActivityLog.objects.select_related("actor")
    serializer_class = ActivityLogSerializer
    filterset_class = ActivityLogFilter
    search_fields = ["target_label", "message", "action"]
    ordering_fields = ["created_at"]
    required_perms = Perm.AUDIT_VIEW


class DateConversionView(APIView):
    """Convert between AD and BS dates and report the fiscal year."""

    required_perms = AUTHENTICATED

    @extend_schema(
        parameters=[
            OpenApiParameter("ad", str, description="AD date, YYYY-MM-DD"),
            OpenApiParameter("bs", str, description="BS date, YYYY-MM-DD"),
        ],
        responses=DateConversionSerializer,
    )
    def get(self, request):
        ad_param, bs_param = request.query_params.get("ad"), request.query_params.get("bs")
        try:
            if bs_param:
                year, month, day = (int(part) for part in bs_param.split("-"))
                day_ad = from_bs(year, month, day)
            elif ad_param:
                day_ad = dt.date.fromisoformat(ad_param)
            else:
                day_ad = local_today()
        except (ValueError, OverflowError) as exc:
            raise ValidationError({"detail": "Enter a valid date as YYYY-MM-DD."}) from exc
        month_start, month_end = bs_month_range(day_ad)
        return Response(
            {
                "ad": day_ad.isoformat(),
                "bs": bs_string(day_ad),
                "bs_long": bs_long(day_ad),
                "fiscal_year": fiscal_year_for(day_ad),
                "bs_month_start": month_start.isoformat(),
                "bs_month_end": month_end.isoformat(),
            }
        )


class PeriodSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    date_from = serializers.DateField(source="from")
    date_to = serializers.DateField(source="to")


class PeriodsView(APIView):
    """Named periods for date pickers: this BS month, last month, this and last fiscal year."""

    required_perms = AUTHENTICATED

    @extend_schema(responses=PeriodSerializer(many=True))
    def get(self, request):
        return Response(PeriodSerializer(named_periods(), many=True).data)


class HealthView(APIView):
    """Liveness check used by Docker and the install script."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        responses=inline_serializer(
            "Health", {"status": serializers.CharField(), "database": serializers.CharField()}
        )
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_status = "ok"
        except Exception:
            db_status = "unavailable"
        status_code = 200 if db_status == "ok" else 503
        return Response(
            {"status": "ok" if db_status == "ok" else "degraded", "database": db_status},
            status=status_code,
        )


def _api_error(request, status_code: int, code: str, detail: str, fallback):
    """JSON errors for /api/ in the standard shape; normal Django pages elsewhere."""
    from django.http import JsonResponse

    if request.path.startswith("/api/"):
        error_type = "client_error" if status_code < 500 else "server_error"
        return JsonResponse(
            {"type": error_type, "errors": [{"code": code, "detail": detail, "attr": None}]},
            status=status_code,
        )
    return fallback()


def not_found(request, exception=None):
    from django.views.defaults import page_not_found

    return _api_error(
        request,
        404,
        "not_found",
        "This address does not exist.",
        lambda: page_not_found(request, exception),
    )


def server_error(request):
    from django.views.defaults import server_error as default_server_error

    return _api_error(
        request,
        500,
        "error",
        "The server had a problem. Try again; if it repeats, tell the owner.",
        lambda: default_server_error(request),
    )
