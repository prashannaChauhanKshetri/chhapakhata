"""Typed shapes for the insights page (so the frontend gets checked types)."""

from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import BSDateField

MONEY = {"max_digits": 14, "decimal_places": 2}


class InsightSummarySerializer(serializers.Serializer):
    work_done = serializers.DecimalField(**MONEY, help_text="Confirmed and delivered orders")
    orders = serializers.IntegerField()
    average_order = serializers.DecimalField(**MONEY)
    invoiced = serializers.DecimalField(**MONEY)
    collected = serializers.DecimalField(**MONEY)
    discounts = serializers.DecimalField(**MONEY)
    new_customers = serializers.IntegerField()
    quotations_open = serializers.IntegerField()


class TrendPointSerializer(serializers.Serializer):
    label = serializers.CharField()
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    work_done = serializers.FloatField()
    collected = serializers.FloatField()


class TopItemSerializer(serializers.Serializer):
    name = serializers.CharField()
    amount = serializers.DecimalField(**MONEY)
    pieces = serializers.IntegerField()
    sqft = serializers.DecimalField(**MONEY)
    orders = serializers.IntegerField()


class TopCustomerSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    name = serializers.CharField()
    amount = serializers.DecimalField(**MONEY)
    orders = serializers.IntegerField()


class PaymentModeTotalSerializer(serializers.Serializer):
    mode = serializers.CharField()
    amount = serializers.DecimalField(**MONEY)
    count = serializers.IntegerField()


class AgingTotalSerializer(serializers.Serializer):
    label = serializers.CharField()
    amount = serializers.DecimalField(**MONEY)


class TopDueSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    name = serializers.CharField()
    balance = serializers.DecimalField(**MONEY)
    oldest_due_date = serializers.DateField(allow_null=True)
    oldest_due_date_bs = serializers.CharField(allow_null=True)


class ProductionInsightSerializer(serializers.Serializer):
    jobs_finished = serializers.IntegerField()
    on_time_percent = serializers.FloatField(allow_null=True)
    average_turnaround_hours = serializers.FloatField(allow_null=True)
    material_used = serializers.DecimalField(**MONEY)
    material_wasted = serializers.DecimalField(**MONEY)
    wastage_percent = serializers.FloatField(allow_null=True)
    open_jobs = serializers.IntegerField()
    average_job_value = serializers.DecimalField(**MONEY)


class InsightsSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_from_bs = BSDateField(source="date_from")
    date_to = serializers.DateField()
    date_to_bs = BSDateField(source="date_to")
    granularity = serializers.ChoiceField(choices=["day", "month"])
    summary = InsightSummarySerializer()
    trend = TrendPointSerializer(many=True)
    top_items = TopItemSerializer(many=True)
    top_customers = TopCustomerSerializer(many=True)
    payment_modes = PaymentModeTotalSerializer(many=True)
    aging = AgingTotalSerializer(many=True)
    top_dues = TopDueSerializer(many=True)
    dues_total = serializers.DecimalField(**MONEY)
    production = ProductionInsightSerializer()
