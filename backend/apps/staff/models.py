"""Staff, daily attendance, salary advances and monthly salary payments.

Salary is counted per Nepali (BS) month:

* one day's pay = monthly salary ÷ days in that BS month;
* a working day marked **absent** takes off one day's pay;
* **Saturday** is the paid weekly holiday; working it adds one day's pay, or
  the worker's own Saturday pay when the owner has set one;
* advances given during the month are taken off that month's salary.

Only the exceptions are stored (absent days, Saturdays worked): every other
working day counts as present.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.billing.models import PaymentMode
from apps.core.models import TimeStampedModel
from apps.customers.models import phone_validator
from apps.tenancy.models import BusinessOwned

#: Python's weekday() for Saturday, the weekly holiday in Nepal.
SATURDAY = 5


class Staff(BusinessOwned, TimeStampedModel):
    """A worker on the payroll. Not the same as a login: helpers need no account."""

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    job_title = models.CharField(max_length=80, blank=True, help_text="e.g. Designer, Fitter")
    monthly_salary = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    saturday_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Extra pay for each Saturday worked. Empty: one day's pay (double).",
    )
    joined_on = models.DateField(help_text="No pay is counted before this day.")
    left_on = models.DateField(null=True, blank=True, help_text="No pay is counted after this day.")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "staff"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = " ".join(self.name.split())
        super().save(*args, **kwargs)


class AttendanceKind(models.TextChoices):
    ABSENT = "absent", "Absent"
    WORKED_HOLIDAY = "worked", "Worked on Saturday"


class Attendance(BusinessOwned, TimeStampedModel):
    """One exception to the normal week: an absent working day or a Saturday worked."""

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField()
    kind = models.CharField(max_length=10, choices=AttendanceKind.choices)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "staff", "date"], name="uniq_staff_attendance_day"
            ),
        ]


class StaffAdvance(BusinessOwned, TimeStampedModel):
    """Money given to a worker before payday; taken off that BS month's salary."""

    staff = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name="advances")
    date = models.DateField()
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    note = models.CharField(max_length=200, blank=True)
    given_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    carried_from = models.ForeignKey(
        "SalaryPayment",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="carried_advances",
        help_text="Set when last month's advances were more than its pay.",
    )

    class Meta:
        ordering = ["date", "id"]


class SalaryPayment(BusinessOwned, TimeStampedModel):
    """A month's salary, paid. Holds the figures as they were, for the salary slip.

    Once a month is paid its attendance and advances are locked; undoing the
    payment unlocks them.
    """

    staff = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name="salary_payments")
    bs_year = models.PositiveSmallIntegerField()
    bs_month = models.PositiveSmallIntegerField()
    monthly_salary = models.DecimalField(max_digits=10, decimal_places=2)
    days_in_month = models.PositiveSmallIntegerField()
    days_employed = models.PositiveSmallIntegerField()
    day_rate = models.DecimalField(max_digits=10, decimal_places=2)
    absent_days = models.PositiveSmallIntegerField()
    holidays_worked = models.PositiveSmallIntegerField()
    holiday_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, help_text="Paid for each Saturday worked."
    )
    base_pay = models.DecimalField(max_digits=10, decimal_places=2)
    absent_deduction = models.DecimalField(max_digits=10, decimal_places=2)
    holiday_pay = models.DecimalField(max_digits=10, decimal_places=2)
    earned = models.DecimalField(max_digits=10, decimal_places=2)
    advances = models.DecimalField(max_digits=10, decimal_places=2)
    net_paid = models.DecimalField(max_digits=10, decimal_places=2)
    carried_forward = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Advance more than the month's pay, moved to next month's advances.",
    )
    paid_on = models.DateField()
    mode = models.CharField(max_length=10, choices=PaymentMode.choices, default=PaymentMode.CASH)
    note = models.CharField(max_length=200, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-bs_year", "-bs_month", "staff__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "staff", "bs_year", "bs_month"],
                name="uniq_salary_per_staff_month",
            ),
        ]
