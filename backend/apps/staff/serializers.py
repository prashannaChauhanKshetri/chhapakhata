from __future__ import annotations

from rest_framework import serializers

from apps.billing.models import PaymentMode
from apps.core.dates import bs_string

from .models import SalaryPayment, Staff, StaffAdvance
from .services import DAY_STATUSES


class StaffSerializer(serializers.ModelSerializer):
    joined_on_bs = serializers.SerializerMethodField()
    left_on_bs = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            "id",
            "name",
            "phone",
            "job_title",
            "monthly_salary",
            "joined_on",
            "joined_on_bs",
            "left_on",
            "left_on_bs",
            "is_active",
            "notes",
        ]

    def get_joined_on_bs(self, obj: Staff) -> str | None:
        return bs_string(obj.joined_on)

    def get_left_on_bs(self, obj: Staff) -> str | None:
        return bs_string(obj.left_on)

    def validate(self, attrs):
        joined = attrs.get("joined_on", getattr(self.instance, "joined_on", None))
        left = attrs.get("left_on", getattr(self.instance, "left_on", None))
        active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        if joined and left and left < joined:
            raise serializers.ValidationError({"left_on": "The last day cannot be before joining."})
        if not active and not left:
            # Without it, a worker switched off would still be counted in every month.
            raise serializers.ValidationError(
                {"left_on": "Enter the last working day of someone who has left."}
            )
        return attrs


class StaffRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ["id", "name", "job_title"]


class DayRowSerializer(serializers.Serializer):
    staff = StaffRefSerializer()
    status = serializers.ChoiceField(choices=DAY_STATUSES)
    locked = serializers.BooleanField(help_text="The month is paid, so the day cannot change.")


class DayRegisterSerializer(serializers.Serializer):
    date = serializers.DateField()
    date_bs = serializers.CharField()
    is_holiday = serializers.BooleanField()
    rows = DayRowSerializer(many=True)


class MarkAttendanceSerializer(serializers.Serializer):
    staff = serializers.PrimaryKeyRelatedField(queryset=Staff.objects.all())
    date = serializers.DateField()
    status = serializers.ChoiceField(choices=DAY_STATUSES)


class StaffAdvanceSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.name", read_only=True)
    date_bs = serializers.SerializerMethodField()
    carried = serializers.SerializerMethodField()
    given_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffAdvance
        fields = [
            "id",
            "staff",
            "staff_name",
            "date",
            "date_bs",
            "amount",
            "note",
            "carried",
            "given_by_name",
        ]

    def get_date_bs(self, obj: StaffAdvance) -> str | None:
        return bs_string(obj.date)

    def get_carried(self, obj: StaffAdvance) -> bool:
        return obj.carried_from_id is not None

    def get_given_by_name(self, obj: StaffAdvance) -> str:
        user = obj.given_by
        return (user.get_full_name() or user.username) if user else ""


class DayRefSerializer(serializers.Serializer):
    ad = serializers.DateField()
    bs = serializers.CharField()


class SalaryPaymentSerializer(serializers.ModelSerializer):
    paid_on_bs = serializers.SerializerMethodField()
    mode_label = serializers.CharField(source="get_mode_display", read_only=True)
    paid_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SalaryPayment
        fields = [
            "id",
            "paid_on",
            "paid_on_bs",
            "mode",
            "mode_label",
            "note",
            "net_paid",
            "paid_by_name",
        ]

    def get_paid_on_bs(self, obj: SalaryPayment) -> str | None:
        return bs_string(obj.paid_on)

    def get_paid_by_name(self, obj: SalaryPayment) -> str:
        user = obj.paid_by
        return (user.get_full_name() or user.username) if user else ""


class MonthSheetSerializer(serializers.Serializer):
    staff = StaffRefSerializer()
    days_in_month = serializers.IntegerField()
    days_employed = serializers.IntegerField()
    days_ahead = serializers.IntegerField()
    monthly_salary = serializers.DecimalField(max_digits=10, decimal_places=2)
    day_rate = serializers.DecimalField(max_digits=10, decimal_places=2)
    absent_dates = serializers.SerializerMethodField()
    worked_dates = serializers.SerializerMethodField()
    base_pay = serializers.DecimalField(max_digits=10, decimal_places=2)
    absent_deduction = serializers.DecimalField(max_digits=10, decimal_places=2)
    holiday_pay = serializers.DecimalField(max_digits=10, decimal_places=2)
    earned = serializers.DecimalField(max_digits=10, decimal_places=2)
    advances = StaffAdvanceSerializer(many=True)
    advances_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    net = serializers.DecimalField(max_digits=10, decimal_places=2)
    carry_forward = serializers.DecimalField(max_digits=10, decimal_places=2)
    notes = serializers.ListField(child=serializers.CharField())
    payment = SalaryPaymentSerializer(allow_null=True)

    @staticmethod
    def _days(days) -> list[dict]:
        return [{"ad": d, "bs": bs_string(d)} for d in days]

    def get_absent_dates(self, obj) -> list[dict]:
        return DayRefSerializer(self._days(obj.absent_dates), many=True).data

    def get_worked_dates(self, obj) -> list[dict]:
        return DayRefSerializer(self._days(obj.worked_dates), many=True).data


class MonthRefSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    label = serializers.CharField()


class PayrollSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    label = serializers.CharField()
    start = serializers.DateField()
    end = serializers.DateField()
    previous = MonthRefSerializer()
    next = MonthRefSerializer(allow_null=True)
    rows = MonthSheetSerializer(many=True)
    total_net = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2)


class PaySalarySerializer(serializers.Serializer):
    staff = serializers.PrimaryKeyRelatedField(queryset=Staff.objects.all())
    year = serializers.IntegerField(min_value=2000, max_value=2200)
    month = serializers.IntegerField(min_value=1, max_value=12)
    paid_on = serializers.DateField()
    mode = serializers.ChoiceField(choices=PaymentMode.choices, default=PaymentMode.CASH)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class UndoSalarySerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)
