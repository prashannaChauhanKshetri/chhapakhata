from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.billing.models import Invoice, InvoiceStatus, Payment, PaymentStatus
from apps.billing.selectors import outstanding_by_customer
from apps.core.dates import bs_month_range, bs_string, local_today
from apps.core.documents import pdf_response, xlsx_response
from apps.core.money import ZERO, q2
from apps.core.params import output_format, parse_date, parse_range
from apps.core.permissions import AUTHENTICATED, Perm, permissions_for
from apps.inventory.models import StockItem
from apps.orders.models import Order, OrderStatus
from apps.production.models import ACTIVE_STAGES, Job, Stage

from . import selectors
from .exporters import report_to_pdf, report_to_xlsx
from .insights import dues_follow_up, insights
from .serializers import InsightsSerializer
from .tables import report_to_json

REPORTS = {
    "daily-sales": {"title": "Daily sales", "perm": Perm.REPORTS_DAILY_SALES, "range": False},
    "monthly-sales": {"title": "Sales summary", "perm": Perm.REPORTS_ALL, "range": True},
    "pending-dues": {"title": "Pending dues", "perm": Perm.REPORTS_ALL, "range": False},
    "collections": {"title": "Collection report", "perm": Perm.REPORTS_ALL, "range": True},
    "material-vs-sales": {
        "title": "Material consumption vs sales",
        "perm": Perm.REPORTS_ALL,
        "range": True,
    },
    "operator-log": {
        "title": "Operator production log",
        "perm": Perm.REPORTS_OWN_PRODUCTION,
        "range": True,
    },
    "stock": {"title": "Stock report", "perm": Perm.REPORTS_ALL, "range": False},
}


class ReportListView(APIView):
    """Reports this user may open."""

    required_perms = AUTHENTICATED

    @extend_schema(operation_id="reports_list", responses=OpenApiTypes.OBJECT)
    def get(self, request):
        held = permissions_for(request.user)
        return Response(
            [
                {"slug": slug, "title": meta["title"], "date_range": meta["range"]}
                for slug, meta in REPORTS.items()
                if meta["perm"] in held
            ]
        )


class ReportView(APIView):
    """Run one report. ``export=xlsx`` or ``export=pdf`` downloads it."""

    required_perms = AUTHENTICATED

    @extend_schema(
        parameters=[
            OpenApiParameter("date", str, description="Single day (AD) for daily reports"),
            OpenApiParameter("from", str, description="Start date (AD)"),
            OpenApiParameter("to", str, description="End date (AD)"),
            OpenApiParameter("operator", int),
            OpenApiParameter("export", str, enum=["json", "pdf", "xlsx"]),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request, slug: str):
        meta = REPORTS.get(slug)
        if meta is None:
            raise NotFound("Unknown report.")
        held = permissions_for(request.user)
        if meta["perm"] not in held:
            raise PermissionDenied("You do not have access to this report.")

        params = request.query_params
        today = local_today()
        month_start, _ = bs_month_range(today)
        day = parse_date(params.get("date"), "date") or today
        date_from, date_to = parse_range(params, month_start, today)

        operator = None
        if slug == "operator-log":
            if Perm.REPORTS_ALL in held:
                operator_id = params.get("operator")
                operator = User.objects.filter(pk=operator_id).first() if operator_id else None
            else:
                operator = request.user  # staff only ever see their own log

        builder = {
            "daily-sales": lambda: selectors.daily_sales(day),
            "monthly-sales": lambda: selectors.sales_summary(date_from, date_to),
            "pending-dues": lambda: selectors.pending_dues(day),
            "collections": lambda: selectors.collections(date_from, date_to),
            "material-vs-sales": lambda: selectors.material_vs_sales(date_from, date_to),
            "operator-log": lambda: selectors.operator_log(date_from, date_to, operator=operator),
            "stock": lambda: selectors.stock_report(),
        }[slug]
        report = builder()
        fmt = output_format(params)
        if fmt == "xlsx":
            return xlsx_response(report_to_xlsx(report), f"{slug}-{report.period[:24]}")
        if fmt == "pdf":
            return pdf_response(report_to_pdf(report), f"{slug}-{today.isoformat()}")
        return Response(report_to_json(report))


def _money(value) -> str:
    return f"{q2(value or 0):.2f}"


class DashboardView(APIView):
    """Role-aware home screen data. Sections a user may not see are omitted."""

    required_perms = AUTHENTICATED

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        user = request.user
        held = permissions_for(user)
        today = local_today()
        now = timezone.now()
        data: dict = {"date": today.isoformat(), "date_bs": bs_string(today)}

        if Perm.DASHBOARD_SALES in held:
            invoices = Invoice.objects.filter(invoice_date=today, status=InvoiceStatus.ISSUED)
            payments = Payment.objects.filter(payment_date=today, status=PaymentStatus.VALID)
            orders = Order.objects.filter(order_date=today).exclude(status=OrderStatus.CANCELLED)
            data["today"] = {
                "sales": _money(invoices.aggregate(s=Sum("total"))["s"]),
                "invoices": invoices.count(),
                "collections": _money(payments.aggregate(s=Sum("amount"))["s"]),
                "payments": payments.count(),
                "orders": orders.exclude(status=OrderStatus.QUOTATION).count(),
                "quotations": orders.filter(status=OrderStatus.QUOTATION).count(),
            }
            data["ready_orders"] = [
                {
                    "id": o.pk,
                    "order_no": o.order_no,
                    "customer": o.customer.name,
                    "phone": o.customer.phone,
                    "total": _money(o.total),
                }
                for o in Order.objects.filter(status=OrderStatus.READY)
                .select_related("customer")
                .order_by("deadline")[:8]
            ]

        if Perm.REPORTS_ALL in held:
            outstanding = outstanding_by_customer(today)
            data["dues"] = {
                "total": _money(sum((o.balance for o in outstanding.values()), ZERO)),
                "customers": len(outstanding),
                "over_90_days": _money(sum((o.buckets["90+"] for o in outstanding.values()), ZERO)),
            }
            start = today - dt.timedelta(days=29)
            per_day = {
                row["invoice_date"]: row["total"]
                for row in Invoice.objects.filter(
                    status=InvoiceStatus.ISSUED, invoice_date__gte=start, invoice_date__lte=today
                )
                .values("invoice_date")
                .annotate(total=Sum("total"))
            }
            data["sales_trend"] = [
                {
                    "date": (start + dt.timedelta(days=i)).isoformat(),
                    "date_bs": bs_string(start + dt.timedelta(days=i)),
                    "total": float(per_day.get(start + dt.timedelta(days=i), Decimal("0"))),
                }
                for i in range(30)
            ]
            from apps.system.selectors import backup_status

            data["backup"] = backup_status()

        if Perm.PRODUCTION_VIEW in held:
            jobs = Job.objects.filter(stage__in=ACTIVE_STAGES)
            working = jobs.exclude(stage=Stage.READY)
            end_of_day = timezone.make_aware(
                dt.datetime.combine(today, dt.time.max), timezone.get_current_timezone()
            )
            counts = dict(jobs.values_list("stage").annotate(n=Count("id")))
            data["jobs"] = {
                "open": jobs.count(),
                "overdue": working.filter(deadline__lt=now).count(),
                "due_today": working.filter(deadline__gte=now, deadline__lte=end_of_day).count(),
                "by_stage": [
                    {"stage": int(s), "label": s.label, "count": counts.get(int(s), 0)}
                    for s in ACTIVE_STAGES
                ],
            }
            data["overdue_jobs"] = [
                {
                    "id": j.pk,
                    "job_no": j.job_no,
                    "customer": j.order.customer.name,
                    "media": j.order_item.media_name,
                    "stage_label": j.get_stage_display(),
                    "deadline": j.deadline.isoformat() if j.deadline else None,
                }
                for j in working.filter(deadline__lt=end_of_day)
                .select_related("order__customer", "order_item")
                .order_by("deadline")[:8]
            ]

        if Perm.INVENTORY_VIEW in held:
            low = StockItem.objects.filter(
                Q(is_active=True), Q(low_stock_level__gt=0), Q(on_hand__lt=F("low_stock_level"))
            ).order_by("name")
            data["low_stock"] = [
                {
                    "id": i.pk,
                    "name": i.name,
                    "on_hand": f"{i.on_hand:.2f}",
                    "low_stock_level": f"{i.low_stock_level:.2f}",
                    "unit": i.get_unit_display(),
                }
                for i in low
            ]

        if Perm.PAYMENTS_VIEW in held:
            data["recent_payments"] = [
                {
                    "id": p.pk,
                    "receipt_no": p.receipt_no,
                    "customer": p.customer.name,
                    "amount": _money(p.amount),
                    "mode": p.mode_label,
                    "payment_date": p.payment_date.isoformat(),
                }
                for p in Payment.objects.filter(status=PaymentStatus.VALID)
                .select_related("customer")
                .order_by("-created_at")[:6]
            ]

        if Perm.LEDGER_VIEW in held:
            data["dues_follow_up"] = dues_follow_up()

        if Perm.REPORTS_OWN_PRODUCTION in held and Perm.REPORTS_ALL not in held:
            month_start, _ = bs_month_range(today)
            mine = selectors.operator_log(month_start, today, operator=user)
            data["my_production"] = {
                "jobs": mine.summary[0].value,
                "sqft": f"{mine.summary[1].value:.2f}",
                "period_start": month_start.isoformat(),
            }
        return Response(data)


class InsightsView(APIView):
    """Owner insights for a period: sales, collections, customers, dues, production."""

    required_perms = Perm.REPORTS_ALL

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "from", str, description="Start date (AD). Default: start of this BS month"
            ),
            OpenApiParameter("to", str, description="End date (AD). Default: today"),
        ],
        responses=InsightsSerializer,
    )
    def get(self, request):
        today = local_today()
        date_from, date_to = parse_range(request.query_params, bs_month_range(today)[0], today)
        return Response(InsightsSerializer(insights(date_from, date_to)).data)
