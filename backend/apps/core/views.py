from __future__ import annotations

import datetime as dt

import django_filters
from django.db import connection
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .activity import log_activity
from .dates import bs_long, bs_month_range, bs_string, fiscal_year_for, from_bs, local_today
from .models import ActivityLog, ShopSettings
from .permissions import AUTHENTICATED, Perm
from .serializers import ActivityLogSerializer, DateConversionSerializer, ShopSettingsSerializer


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
