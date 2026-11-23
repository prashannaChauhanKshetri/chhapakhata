from __future__ import annotations

import datetime as dt
from decimal import Decimal

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.activity import log_activity
from apps.core.dates import bs_string, local_today
from apps.core.documents import pdf_response, render_pdf
from apps.core.params import parse_date
from apps.core.permissions import Perm

from . import services
from .models import SalaryPayment, Staff, StaffAdvance
from .serializers import (
    DayRegisterSerializer,
    MarkAttendanceSerializer,
    PayrollSerializer,
    PaySalarySerializer,
    SalaryPaymentSerializer,
    StaffAdvanceSerializer,
    StaffMonthSerializer,
    StaffSerializer,
    UndoSalarySerializer,
)


class StaffViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Workers on the payroll. Never deleted: set the last working day instead."""

    serializer_class = StaffSerializer
    required_perms = Perm.STAFF_MANAGE
    pagination_class = None

    def get_queryset(self):
        return Staff.objects.all().order_by("-is_active", "name")

    def perform_create(self, serializer):
        staff = serializer.save()
        log_activity(self.request.user, "staff.created", staff, f"Staff {staff.name} added")

    @extend_schema(
        parameters=[OpenApiParameter("month", str, description="BS month YYYY-MM; default: now")],
        responses=StaffMonthSerializer,
    )
    @action(detail=True, methods=["get"])
    def days(self, request, pk=None):
        """The worker's month as a calendar, to correct past days."""
        staff = self.get_object()
        year, month = _month_param(request.query_params.get("month"))
        data = {
            "staff": staff,
            "year": year,
            "month": month,
            "label": services.month_label(year, month),
            **_neighbours(year, month),
            "paid": SalaryPayment.objects.filter(
                staff=staff, bs_year=year, bs_month=month
            ).exists(),
            "days": services.month_days(staff, year, month),
        }
        return Response(StaffMonthSerializer(data).data)

    def perform_update(self, serializer):
        before = serializer.instance.monthly_salary
        staff = serializer.save()
        message = f"Staff {staff.name} updated"
        if staff.monthly_salary != before:
            message += f"; monthly salary {before} → {staff.monthly_salary}"
        log_activity(self.request.user, "staff.updated", staff, message)


class AttendanceView(APIView):
    """The daily register: everyone working that day, present or absent."""

    required_perms = Perm.STAFF_MANAGE

    @extend_schema(
        parameters=[OpenApiParameter("date", dt.date, description="Default: today")],
        responses=DayRegisterSerializer,
    )
    def get(self, request):
        day = parse_date(request.query_params.get("date"), "date") or local_today()
        data = {
            "date": day,
            "date_bs": bs_string(day),
            "is_holiday": services.is_holiday(day),
            "rows": services.day_register(day),
        }
        return Response(DayRegisterSerializer(data).data)

    @extend_schema(request=MarkAttendanceSerializer, responses=MarkAttendanceSerializer)
    def post(self, request):
        serializer = MarkAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        services.set_attendance(
            staff=data["staff"],
            day=data["date"],
            status=data["status"],
            user=request.user,
            request=request,
        )
        return Response(serializer.data)


class StaffAdvanceViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Advances on salary. Taken off the salary of the BS month they are given in."""

    serializer_class = StaffAdvanceSerializer
    required_perms = Perm.STAFF_MANAGE

    def get_queryset(self):
        queryset = StaffAdvance.objects.select_related("staff", "given_by").order_by("-date", "-id")
        staff = self.request.query_params.get("staff")
        if staff and staff.isdigit():
            queryset = queryset.filter(staff_id=int(staff))
        return queryset

    @extend_schema(parameters=[OpenApiParameter("staff", int)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        advance = services.give_advance(
            staff=data["staff"],
            day=data["date"],
            amount=Decimal(data["amount"]),
            note=data.get("note", ""),
            user=request.user,
            request=request,
        )
        return Response(self.get_serializer(advance).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        services.delete_advance(advance=instance, user=self.request.user, request=self.request)


def _month_param(value: str | None) -> tuple[int, int]:
    """``YYYY-MM`` in BS; this BS month when empty."""
    if not value:
        return services.month_of(local_today())
    try:
        year, month = (int(part) for part in value.split("-"))
    except ValueError as exc:
        raise ValidationError({"month": "Use the BS month as YYYY-MM, e.g. 2083-08."}) from exc
    services.month_bounds(year, month)
    return year, month


def _neighbours(year: int, month: int) -> dict:
    """The months either side; no next month once it has not started."""
    py, pm = services.previous_month(year, month)
    ny, nm = services.next_month(year, month)
    upcoming = services.month_bounds(ny, nm)[0] > local_today()
    return {
        "previous": {"year": py, "month": pm, "label": services.month_label(py, pm)},
        "next": None
        if upcoming
        else {"year": ny, "month": nm, "label": services.month_label(ny, nm)},
    }


class SalaryView(APIView):
    """One BS month's salary for everyone who worked in it."""

    required_perms = Perm.STAFF_MANAGE

    @extend_schema(
        parameters=[OpenApiParameter("month", str, description="BS month YYYY-MM; default: now")],
        responses=PayrollSerializer,
    )
    def get(self, request):
        year, month = _month_param(request.query_params.get("month"))
        start, end = services.month_bounds(year, month)
        rows = services.payroll(year, month)
        data = {
            "year": year,
            "month": month,
            "label": services.month_label(year, month),
            "start": start,
            "end": end,
            **_neighbours(year, month),
            "rows": rows,
            "total_net": sum((r.net for r in rows), Decimal("0")),
            "total_paid": sum((r.net for r in rows if r.payment), Decimal("0")),
        }
        return Response(PayrollSerializer(data).data)


class PaySalaryView(APIView):
    required_perms = Perm.STAFF_MANAGE

    @extend_schema(request=PaySalarySerializer, responses={201: SalaryPaymentSerializer})
    def post(self, request):
        serializer = PaySalarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payment = services.pay_salary(
            staff=data["staff"],
            bs_year=data["year"],
            bs_month=data["month"],
            paid_on=data["paid_on"],
            mode=data["mode"],
            note=data["note"],
            user=request.user,
            request=request,
        )
        return Response(SalaryPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class SalaryPaymentViewSet(viewsets.GenericViewSet):
    serializer_class = SalaryPaymentSerializer
    required_perms = Perm.STAFF_MANAGE

    def get_queryset(self):
        return SalaryPayment.objects.select_related("staff", "paid_by")

    @extend_schema(request=UndoSalarySerializer, responses={204: None})
    @action(detail=True, methods=["post"])
    def undo(self, request, pk=None):
        serializer = UndoSalarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.undo_salary(
            payment=self.get_object(),
            user=request.user,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={(200, "application/pdf"): bytes})
    @action(detail=True, methods=["get"])
    def slip(self, request, pk=None):
        """The salary slip (A4), with signature lines."""
        payment = self.get_object()
        sheet = services.month_sheet(payment.staff, payment.bs_year, payment.bs_month)
        context = {"sheet": sheet, "payment": payment, "page_size": "A4"}
        name = f"salary-{payment.staff.name}-{payment.bs_year}-{payment.bs_month:02d}"
        return pdf_response(render_pdf("documents/salary_slip.html", context), name)
