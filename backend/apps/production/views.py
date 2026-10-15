from __future__ import annotations

import datetime as dt

import django_filters
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.documents import pdf_response, render_pdf
from apps.core.permissions import Perm
from apps.inventory.models import Roll, RollStatus

from . import services
from .models import ACTIVE_STAGES, Job, Stage
from .serializers import (
    BoardSerializer,
    JobDetailSerializer,
    JobSerializer,
    JobUpdateSerializer,
    MaterialInputSerializer,
    MaterialOptionsSerializer,
    MoveJobSerializer,
    MoveResultSerializer,
)


class JobFilter(django_filters.FilterSet):
    stage = django_filters.MultipleChoiceFilter(choices=Stage.choices)
    media_type = django_filters.NumberFilter(field_name="order_item__media_type")
    due = django_filters.ChoiceFilter(
        choices=[("today", "Due today"), ("overdue", "Overdue")], method="filter_due"
    )
    open = django_filters.BooleanFilter(method="filter_open")

    class Meta:
        model = Job
        fields = ["operator", "order", "priority"]

    def filter_due(self, queryset, name, value):
        now = timezone.now()
        open_jobs = queryset.filter(
            stage__in=[Stage.DESIGN, Stage.READY_FOR_PRINT, Stage.PRINTING, Stage.FINISHING]
        )
        if value == "overdue":
            return open_jobs.filter(deadline__lt=now)
        end_of_day = timezone.make_aware(
            dt.datetime.combine(timezone.localdate(), dt.time.max), timezone.get_current_timezone()
        )
        return open_jobs.filter(deadline__gte=now, deadline__lte=end_of_day)

    def filter_open(self, queryset, name, value):
        return (
            queryset.filter(stage__in=ACTIVE_STAGES)
            if value
            else queryset.exclude(stage__in=ACTIVE_STAGES)
        )


class JobViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Production jobs: one per order item, moved through six stages."""

    filterset_class = JobFilter
    search_fields = [
        "job_no",
        "order__order_no",
        "order__customer__name",
        "order_item__media_name",
        "order_item__description",
    ]
    ordering_fields = ["deadline", "created_at", "stage", "priority"]
    ordering = ["deadline", "id"]
    http_method_names = ["get", "post", "patch", "head", "options"]
    required_perms = {
        "list": Perm.PRODUCTION_VIEW,
        "retrieve": Perm.PRODUCTION_VIEW,
        "board": Perm.PRODUCTION_VIEW,
        "partial_update": Perm.PRODUCTION_MOVE,
        "move": Perm.PRODUCTION_MOVE,
        "record_material": Perm.INVENTORY_RECORD_USAGE,
        "material_options": Perm.PRODUCTION_VIEW,
        "ticket": Perm.PRODUCTION_VIEW,
    }

    def get_queryset(self):
        qs = Job.objects.select_related(
            "order__customer", "order_item__media_type", "operator"
        ).prefetch_related("order_item__addons")
        if self.action == "retrieve":
            qs = qs.prefetch_related("events__created_by")
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return JobDetailSerializer
        if self.action == "partial_update":
            return JobUpdateSerializer
        return JobSerializer

    @extend_schema(request=JobUpdateSerializer, responses=JobSerializer)
    def partial_update(self, request, *args, **kwargs):
        job = self.get_object()
        serializer = JobUpdateSerializer(job, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        job = services.update_job_details(
            job=job, user=request.user, request=request, **serializer.validated_data
        )
        return Response(JobSerializer(job, context=self.get_serializer_context()).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("search", str),
            OpenApiParameter("media_type", int),
            OpenApiParameter("operator", int),
            OpenApiParameter("due", str, enum=["today", "overdue"]),
            OpenApiParameter("mine", bool, description="Only jobs assigned to me"),
        ],
        responses=BoardSerializer,
    )
    @action(detail=False, methods=["get"], pagination_class=None)
    def board(self, request):
        """All open jobs grouped by stage; delivered shows only today's deliveries."""
        today_start = timezone.make_aware(
            dt.datetime.combine(timezone.localdate(), dt.time.min), timezone.get_current_timezone()
        )
        qs = self.filter_queryset(self.get_queryset()).filter(
            Q(stage__in=ACTIVE_STAGES) | Q(stage=Stage.DELIVERED, stage_changed_at__gte=today_start)
        )
        if request.query_params.get("mine") in ("1", "true"):
            qs = qs.filter(operator=request.user)
        jobs = list(qs.order_by("-priority", "deadline", "id"))
        context = self.get_serializer_context()
        columns = []
        for stage in [*ACTIVE_STAGES, Stage.DELIVERED]:
            stage_jobs = [j for j in jobs if j.stage == stage]
            columns.append(
                {
                    "stage": int(stage),
                    "label": stage.label,
                    "count": len(stage_jobs),
                    "jobs": stage_jobs,
                }
            )
        data = BoardSerializer(
            {
                "columns": columns,
                "total_open": sum(1 for j in jobs if j.stage in ACTIVE_STAGES),
                "overdue": 0,
                "due_today": 0,
            },
            context=context,
        ).data
        cards = [card for column in data["columns"] for card in column["jobs"]]
        data["overdue"] = sum(1 for c in cards if c["is_overdue"])
        data["due_today"] = sum(1 for c in cards if c["is_due_today"])
        return Response(data)

    @extend_schema(request=MoveJobSerializer, responses=MoveResultSerializer)
    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        """Move to another stage. Passing Printing requires the material used."""
        serializer = MoveJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = services.move_job(
            job=self.get_object(),
            user=request.user,
            to_stage=data["to_stage"],
            note=data.get("note", ""),
            material=data.get("material"),
            skip_material=data.get("skip_material", False),
            request=request,
        )
        job = self.get_queryset().get(pk=result["job"].pk)
        return Response(
            MoveResultSerializer(
                {"job": job, "warnings": result["warnings"]}, context=self.get_serializer_context()
            ).data
        )

    @extend_schema(request=MaterialInputSerializer, responses=MoveResultSerializer)
    @action(detail=True, methods=["post"], url_path="record-material")
    def record_material(self, request, pk=None):
        """Record roll usage without changing the stage (e.g. a reprint)."""
        from apps.inventory.services import record_job_consumption

        serializer = MaterialInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = self.get_object()
        result = record_job_consumption(
            user=request.user, job=job, request=request, **serializer.validated_data
        )
        job = self.get_queryset().get(pk=job.pk)
        return Response(
            MoveResultSerializer(
                {"job": job, "warnings": result["warnings"]}, context=self.get_serializer_context()
            ).data
        )

    @extend_schema(responses=MaterialOptionsSerializer)
    @action(detail=True, methods=["get"], url_path="material-options")
    def material_options(self, request, pk=None):
        """Rolls that can be used for this job, with a pre-filled sq ft value."""
        job = self.get_object()
        material = job.order_item.media_type.material
        rolls = []
        if material is not None:
            short_side = min(job.order_item.width_ft, job.order_item.height_ft)
            for roll in Roll.objects.filter(stock_item=material, status=RollStatus.ACTIVE).order_by(
                "width_ft", "remaining_sqft"
            ):
                rolls.append(
                    {
                        "id": roll.pk,
                        "code": roll.code,
                        "width_ft": roll.width_ft,
                        "remaining_sqft": roll.remaining_sqft,
                        "fits": roll.width_ft >= short_side,
                    }
                )
        return Response(
            MaterialOptionsSerializer(
                {
                    "stock_item_id": material.pk if material else None,
                    "stock_item_name": material.name if material else None,
                    "default_used_sqft": services.default_used_sqft(job),
                    "material_recorded": job.material_recorded,
                    "rolls": rolls,
                }
            ).data
        )

    @extend_schema(responses={(200, "application/pdf"): bytes})
    @action(detail=True, methods=["get"])
    def ticket(self, request, pk=None):
        """Printable job ticket (A5)."""
        job = self.get_object()
        return pdf_response(
            render_pdf("documents/job_ticket.html", {"jobs": [job]}), f"ticket-{job.job_no}"
        )
