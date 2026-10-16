from __future__ import annotations

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.activity import log_activity
from apps.core.dates import local_today
from apps.core.documents import xlsx_response
from apps.core.params import parse_range
from apps.core.permissions import Perm
from apps.core.serializers import UserRefSerializer

from . import services, work_log
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


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class WorkLogUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="The work log as .xlsx or .csv")
    dry_run = serializers.BooleanField(
        default=True, help_text="Check the file and show what would be imported, without saving."
    )
    skip_errors = serializers.BooleanField(
        default=False, help_text="Import the valid rows and leave out rows with errors."
    )

    def validate_file(self, value):
        if value.size > MAX_UPLOAD_BYTES:
            raise serializers.ValidationError("The file is larger than 10 MB.")
        if not value.name.lower().endswith((".xlsx", ".xlsm", ".csv")):
            raise serializers.ValidationError("Upload an Excel (.xlsx) or CSV file.")
        return value


class RowMessageSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    message = serializers.CharField()


class NewItemSerializer(serializers.Serializer):
    name = serializers.CharField()
    pricing_unit = serializers.CharField()
    rate = serializers.DecimalField(max_digits=10, decimal_places=2)


class WorkLogTotalsSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    discount = serializers.DecimalField(max_digits=14, decimal_places=2)
    vat = serializers.DecimalField(max_digits=14, decimal_places=2)
    paid = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)


class WorkLogImportResultSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField(help_text="True when nothing was saved")
    file_name = serializers.CharField()
    header_row = serializers.IntegerField()
    columns = serializers.DictField(child=serializers.CharField())
    rows_read = serializers.IntegerField()
    rows_imported = serializers.IntegerField()
    rows_skipped_duplicate = serializers.IntegerField()
    rows_skipped_error = serializers.IntegerField()
    rows_already_in_system = serializers.IntegerField()
    orders = serializers.IntegerField()
    payments = serializers.IntegerField()
    new_customers = serializers.ListField(child=serializers.CharField())
    matched_customers = serializers.IntegerField()
    new_items = NewItemSerializer(many=True)
    totals = WorkLogTotalsSerializer()
    date_from = serializers.DateField(allow_null=True)
    date_to = serializers.DateField(allow_null=True)
    errors = RowMessageSerializer(many=True)
    warnings = RowMessageSerializer(many=True)


class WorkLogImportView(APIView):
    """Upload the shop's Excel work log: check it first (dry run), then import."""

    required_perms = Perm.SETTINGS_MANAGE
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={"multipart/form-data": WorkLogUploadSerializer},
        responses=WorkLogImportResultSerializer,
    )
    def post(self, request):
        serializer = WorkLogUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        upload = data["file"]
        try:
            result = work_log.import_work_log(
                upload,
                name=upload.name,
                user=request.user,
                dry_run=data["dry_run"],
                skip_errors=data["skip_errors"],
                request=request,
            )
        except ValueError as exc:
            raise ValidationError({"file": [str(exc)]}) from exc
        return Response(WorkLogImportResultSerializer(result).data)


class WorkLogExportView(APIView):
    """Download orders as a work-log sheet (same columns as the shop's Excel file)."""

    required_perms = Perm.REPORTS_ALL

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="Start date (AD, YYYY-MM-DD)"),
            OpenApiParameter("to", str, description="End date (AD, YYYY-MM-DD)"),
        ],
        responses={(200, XLSX): bytes},
    )
    def get(self, request):
        date_from, date_to = parse_range(request.query_params, None, local_today())
        content = work_log.export_work_log(date_from, date_to)
        log_activity(request.user, "work_log.exported", None, request=request)
        return xlsx_response(content, f"work-log-{date_to.isoformat()}")


class WorkLogTemplateView(APIView):
    """An empty work-log sheet with the expected column headers."""

    required_perms = Perm.SETTINGS_MANAGE

    @extend_schema(responses={(200, XLSX): bytes})
    def get(self, request):
        return xlsx_response(work_log.work_log_template(), "work-log-template")
