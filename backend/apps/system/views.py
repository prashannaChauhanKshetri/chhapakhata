from __future__ import annotations

import json

from django.http import Http404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_field
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

from . import go_live, services, sheets, work_log
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


class ImportUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="The sheet as .xlsx, .xls or .csv")
    dry_run = serializers.BooleanField(
        default=True, help_text="Check the file and show what would be imported, without saving."
    )
    skip_errors = serializers.BooleanField(
        default=False, help_text="Import the valid rows and leave out rows with errors."
    )
    columns = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='JSON {"header text": "field"} correcting the column guesses; "" leaves a '
        "column out.",
    )

    def validate_file(self, value):
        if value.size > MAX_UPLOAD_BYTES:
            raise serializers.ValidationError("The file is larger than 10 MB.")
        if not value.name.lower().endswith(sheets.FILE_TYPES):
            raise serializers.ValidationError("Upload an Excel (.xlsx, .xls) or CSV file.")
        return value

    def validate_columns(self, value):
        if not value:
            return None
        try:
            raw = json.loads(value)
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError("Columns must be JSON.") from exc
        if not isinstance(raw, dict) or not all(isinstance(v, str) for v in raw.values()):
            raise serializers.ValidationError('Columns must look like {"Header": "field"}.')
        allowed = set(self.context.get("fields", ())) | {""}
        unknown = sorted(set(raw.values()) - allowed)
        if unknown:
            raise serializers.ValidationError(f"Unknown field(s): {', '.join(unknown)}.")
        return {sheets.header_key(k): v for k, v in raw.items() if sheets.header_key(k)}


class GoLiveUploadSerializer(ImportUploadSerializer):
    as_of = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Date of the opening balances (customers only; default today)",
    )


class RowMessageSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    message = serializers.CharField()
    sheet = serializers.CharField(help_text="Sheet name when the file has several")


class ImportFieldSerializer(serializers.Serializer):
    field = serializers.CharField()
    label = serializers.CharField()


class SheetFieldsMixin(serializers.Serializer):
    """What the reader understood, so the person importing can correct it."""

    sheets = serializers.ListField(child=serializers.CharField())
    header_row = serializers.IntegerField()
    columns = serializers.DictField(child=serializers.CharField(), help_text="field -> header")
    headers = serializers.ListField(child=serializers.CharField())
    needs_columns = serializers.BooleanField(
        help_text="No header was recognised: choose the columns and check again"
    )
    problem = serializers.CharField()
    field_choices = serializers.SerializerMethodField(
        help_text="Every field this import understands, for correcting columns"
    )

    @extend_schema_field(ImportFieldSerializer(many=True))
    def get_field_choices(self, obj) -> list[dict[str, str]]:
        labels = self.context["columns"].labels()
        return [{"field": f, "label": label} for f, label in labels.items()]


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


class WorkLogImportResultSerializer(SheetFieldsMixin):
    dry_run = serializers.BooleanField(help_text="True when nothing was saved")
    file_name = serializers.CharField()
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


class TableImportResultSerializer(SheetFieldsMixin):
    kind = serializers.CharField()
    dry_run = serializers.BooleanField(help_text="True when nothing was saved")
    file_name = serializers.CharField()
    rows_read = serializers.IntegerField()
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    skipped = serializers.IntegerField()
    rows_skipped_error = serializers.IntegerField()
    summary = serializers.DictField(child=serializers.CharField())
    errors = RowMessageSerializer(many=True)
    warnings = RowMessageSerializer(many=True)


def _field_names(columns: sheets.Columns) -> list[str]:
    return [c.field for c in columns.fields]


class WorkLogImportView(APIView):
    """Upload the shop's Excel work log: check it first (dry run), then import."""

    required_perms = Perm.SETTINGS_MANAGE
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={"multipart/form-data": ImportUploadSerializer},
        responses=WorkLogImportResultSerializer,
    )
    def post(self, request):
        columns = work_log.COLUMNS
        serializer = ImportUploadSerializer(
            data=request.data, context={"fields": _field_names(columns)}
        )
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
                columns=data.get("columns"),
                request=request,
            )
        except ValueError as exc:
            raise ValidationError({"file": [str(exc)]}) from exc
        return Response(WorkLogImportResultSerializer(result, context={"columns": columns}).data)


def _kind(kind: str) -> go_live.Kind:
    if kind not in go_live.KINDS:
        raise Http404
    return go_live.KINDS[kind]


class GoLiveImportView(APIView):
    """Upload customers with opening balances, the rate card or opening stock.

    The same check-first flow as the work log: a dry run shows what would be
    added, updated or skipped, and the columns can be corrected.
    """

    required_perms = Perm.SETTINGS_MANAGE
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        parameters=[
            OpenApiParameter("kind", str, OpenApiParameter.PATH, enum=sorted(go_live.KINDS))
        ],
        request={"multipart/form-data": GoLiveUploadSerializer},
        responses=TableImportResultSerializer,
    )
    def post(self, request, kind: str):
        spec = _kind(kind)
        serializer = GoLiveUploadSerializer(
            data=request.data, context={"fields": _field_names(spec.columns)}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        upload = data["file"]
        try:
            result = go_live.run_import(
                kind,
                upload.read(),
                name=upload.name,
                user=request.user,
                dry_run=data["dry_run"],
                skip_errors=data["skip_errors"],
                columns=data.get("columns"),
                as_of=data.get("as_of"),
                request=request,
            )
        except ValueError as exc:
            raise ValidationError({"file": [str(exc)]}) from exc
        return Response(TableImportResultSerializer(result, context={"columns": spec.columns}).data)


class GoLiveTemplateView(APIView):
    """A sample sheet for a go-live import, with the usual columns."""

    required_perms = Perm.SETTINGS_MANAGE

    @extend_schema(
        parameters=[
            OpenApiParameter("kind", str, OpenApiParameter.PATH, enum=sorted(go_live.KINDS))
        ],
        responses={(200, XLSX): bytes},
    )
    def get(self, request, kind: str):
        _kind(kind)
        return xlsx_response(go_live.template(kind), f"{kind}-template")


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
