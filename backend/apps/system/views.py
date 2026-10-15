from __future__ import annotations

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.activity import log_activity
from apps.core.documents import xlsx_response
from apps.core.permissions import Perm
from apps.core.serializers import UserRefSerializer

from . import services
from .models import BackupRun, BackupTrigger
from .selectors import backup_status


class BackupRunSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    offsite_status_label = serializers.CharField(
        source="get_offsite_status_display", read_only=True
    )
    trigger_label = serializers.CharField(source="get_trigger_display", read_only=True)
    created_by = UserRefSerializer(read_only=True, allow_null=True)

    class Meta:
        model = BackupRun
        fields = [
            "id",
            "started_at",
            "finished_at",
            "status",
            "status_label",
            "trigger",
            "trigger_label",
            "size_bytes",
            "sha256",
            "offsite_status",
            "offsite_status_label",
            "offsite_message",
            "message",
            "created_by",
        ]


class BackupRunViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Backup history; the owner can start a backup at any time."""

    queryset = BackupRun.objects.select_related("created_by")
    serializer_class = BackupRunSerializer
    required_perms = Perm.SYSTEM_BACKUP

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=["get"])
    def status(self, request):
        return Response(backup_status())

    @extend_schema(request=None, responses={201: BackupRunSerializer})
    @action(detail=False, methods=["post"])
    def run(self, request):
        backup = services.run_backup(BackupTrigger.MANUAL, user=request.user)
        return Response(BackupRunSerializer(backup).data, status=status.HTTP_201_CREATED)


class DataExportView(APIView):
    """Download all business data as an Excel workbook."""

    required_perms = Perm.SETTINGS_MANAGE

    @extend_schema(
        responses={
            (200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): bytes
        }
    )
    def get(self, request):
        content = services.export_all_data()
        log_activity(request.user, "data.exported", None, request=request)
        return xlsx_response(content, f"chhapakhata-export-{timezone.localdate().isoformat()}")
