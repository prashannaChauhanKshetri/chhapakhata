"""Attendance, advances and salary: the rules in one place (see models.py)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.core.activity import log_activity
from apps.core.dates import BS_MONTHS, bs_month_range, bs_string, from_bs, local_today, to_bs
from apps.core.money import format_npr, q2

from .models import SATURDAY, Attendance, AttendanceKind, SalaryPayment, Staff, StaffAdvance

ZERO = Decimal("0")

#: What the owner can mark: a working day is present or absent; a Saturday is off or worked.
DAY_STATUSES = ("present", "absent", "off", "worked")
#: As shown on calendars: also days before joining / after leaving, and days settled
#: by the opening balance.
CALENDAR_STATUSES = (*DAY_STATUSES, "not_working", "settled")


# -- Months ---------------------------------------------------------------------------


def month_bounds(bs_year: int, bs_month: int) -> tuple[dt.date, dt.date]:
    """First and last AD dates of a BS month."""
    if not 1 <= bs_month <= 12:
        raise ValidationError({"month": "The month must be 1 to 12."})
    try:
        return bs_month_range(from_bs(bs_year, bs_month, 1))
    except (ValueError, OverflowError) as exc:
        raise ValidationError({"month": "There is no such Nepali month."}) from exc


def month_label(bs_year: int, bs_month: int) -> str:
    return f"{BS_MONTHS[bs_month - 1]} {bs_year}"


def month_of(day: dt.date) -> tuple[int, int]:
    bs = to_bs(day)
    return bs.year, bs.month


def next_month(bs_year: int, bs_month: int) -> tuple[int, int]:
    return (bs_year + 1, 1) if bs_month == 12 else (bs_year, bs_month + 1)


def previous_month(bs_year: int, bs_month: int) -> tuple[int, int]:
    return (bs_year - 1, 12) if bs_month == 1 else (bs_year, bs_month - 1)


def is_holiday(day: dt.date) -> bool:
    return day.weekday() == SATURDAY


def employed_on(staff: Staff, day: dt.date) -> bool:
    return staff.joined_on <= day and (staff.left_on is None or day <= staff.left_on)


def balance_label(staff: Staff) -> str:
    if not (staff.balance_year and staff.balance_month):
        return ""
    return month_label(staff.balance_year, staff.balance_month)


def settled_until(staff: Staff) -> dt.date | None:
    """The last day covered by the worker's opening balance, if one was entered."""
    if not (staff.balance_year and staff.balance_month):
        return None
    return month_bounds(staff.balance_year, staff.balance_month)[1]


def counted_on(staff: Staff, day: dt.date) -> bool:
    """Working here that day, and the day is not already settled by the opening balance."""
    settled = settled_until(staff)
    return employed_on(staff, day) and (settled is None or day > settled)


def opening_month(staff: Staff) -> tuple[int, int] | None:
    """The BS month in which the opening balance is settled: the one after it."""
    if not (staff.balance_year and staff.balance_month):
        return None
    return next_month(staff.balance_year, staff.balance_month)


def recent_months(count: int = 12) -> list[tuple[int, int]]:
    """This BS month and the ones before it, newest first (choices for the balance month)."""
    year, month = month_of(local_today())
    months = []
    for _ in range(count):
        months.append((year, month))
        year, month = previous_month(year, month)
    return months


def check_balance_change(staff: Staff, year: int | None, month: int | None) -> None:
    """A balance cannot move once a month it affects is paid."""
    old = (staff.balance_year, staff.balance_month) if staff.balance_year else None
    new = (year, month) if year else None
    affected = [m for m in (old, new) if m]
    if not affected:
        return
    earliest = min(affected)
    paid = SalaryPayment.objects.filter(staff=staff).filter(
        Q(bs_year__gt=earliest[0]) | Q(bs_year=earliest[0], bs_month__gt=earliest[1])
    )
    if paid.exists():
        raise ValidationError(
            {
                "opening_balance": "A month after the balance is already paid. "
                "Undo that payment first to change the balance."
            }
        )


# -- The month's salary ---------------------------------------------------------------


@dataclass
class MonthSheet:
    """One worker's salary for one BS month: live figures, or the paid record's."""

    staff: Staff
    bs_year: int
    bs_month: int
    start: dt.date
    end: dt.date
    days_in_month: int
    days_employed: int
    monthly_salary: Decimal
    day_rate: Decimal
    absent_dates: list[dt.date]
    worked_dates: list[dt.date]
    base_pay: Decimal
    absent_deduction: Decimal
    holiday_pay: Decimal
    #: Paid for each Saturday worked: one day's pay, or the worker's own Saturday pay.
    holiday_rate: Decimal
    earned: Decimal
    advances: list[StaffAdvance]
    advances_total: Decimal
    net: Decimal
    carry_forward: Decimal
    payment: SalaryPayment | None = None
    #: Brought in from before the app (+ the shop owed it, − the worker owed it).
    opening_balance: Decimal = ZERO
    #: The month the opening balance covers, e.g. "Kartik 2083".
    opening_label: str = ""
    #: Days of the month still to come (their attendance is not known yet).
    days_ahead: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return month_label(self.bs_year, self.bs_month)


def month_sheet(staff: Staff, bs_year: int, bs_month: int) -> MonthSheet:
    start, end = month_bounds(bs_year, bs_month)
    days = (end - start).days + 1
    settled = settled_until(staff)
    first = max(start, staff.joined_on, settled + dt.timedelta(days=1) if settled else start)
    last = min(end, staff.left_on) if staff.left_on else end

    exceptions = list(
        Attendance.objects.filter(staff=staff, date__range=(first, last)).values_list(
            "date", "kind"
        )
    )
    absent = sorted(d for d, k in exceptions if k == AttendanceKind.ABSENT and not is_holiday(d))
    worked = sorted(
        d for d, k in exceptions if k == AttendanceKind.WORKED_HOLIDAY and is_holiday(d)
    )
    advances = list(StaffAdvance.objects.filter(staff=staff, date__range=(start, end)))
    advances_total = sum((a.amount for a in advances), ZERO)
    payment = SalaryPayment.objects.filter(staff=staff, bs_year=bs_year, bs_month=bs_month).first()
    today = local_today()
    days_ahead = max((last - max(today, first - dt.timedelta(days=1))).days, 0)

    if payment is not None:
        # Paid: show exactly what was paid, whatever changed since.
        return MonthSheet(
            staff=staff,
            bs_year=bs_year,
            bs_month=bs_month,
            start=start,
            end=end,
            days_in_month=payment.days_in_month,
            days_employed=payment.days_employed,
            monthly_salary=payment.monthly_salary,
            day_rate=payment.day_rate,
            absent_dates=absent,
            worked_dates=worked,
            base_pay=payment.base_pay,
            absent_deduction=payment.absent_deduction,
            holiday_pay=payment.holiday_pay,
            holiday_rate=payment.holiday_rate,
            earned=payment.earned,
            advances=advances,
            advances_total=payment.advances,
            net=payment.net_paid,
            carry_forward=payment.carried_forward,
            payment=payment,
            opening_balance=payment.opening_balance,
            opening_label=balance_label(staff) if payment.opening_balance else "",
        )

    salary = staff.monthly_salary
    # Earned to date: a month still running counts the days up to today only, so
    # the pay grows day by day. Whole month: exactly the monthly salary.
    so_far = max((min(last, today) - first).days + 1, 0)
    base = salary if so_far == days else q2(salary * so_far / days)
    deduction = q2(salary * len(absent) / days)
    day_rate = q2(salary / days)
    if staff.saturday_pay is not None:
        holiday_rate = staff.saturday_pay
        extra = q2(holiday_rate * len(worked))
    else:
        holiday_rate = day_rate
        extra = q2(salary * len(worked) / days)
    earned = base - deduction + extra
    opening = staff.opening_balance if opening_month(staff) == (bs_year, bs_month) else ZERO
    net = earned - advances_total + opening
    carry = ZERO
    if net < 0:
        carry, net = -net, ZERO
    sheet = MonthSheet(
        staff=staff,
        bs_year=bs_year,
        bs_month=bs_month,
        start=start,
        end=end,
        days_in_month=days,
        days_employed=so_far,
        monthly_salary=salary,
        day_rate=day_rate,
        absent_dates=absent,
        worked_dates=worked,
        base_pay=base,
        absent_deduction=deduction,
        holiday_pay=extra,
        holiday_rate=holiday_rate,
        earned=earned,
        advances=advances,
        advances_total=advances_total,
        net=net,
        carry_forward=carry,
        days_ahead=days_ahead,
        opening_balance=opening,
        opening_label=balance_label(staff) if opening else "",
    )
    if carry and days_ahead:
        # Mid-month the pay is still growing; only at the month's end is anything left over.
        sheet.notes.append(
            f"Advances are {format_npr(carry)} more than the pay so far; "
            "the days still to come make up for it."
        )
    elif carry:
        sheet.notes.append(
            f"Advances are {format_npr(carry)} more than this month's pay; "
            "the rest moves to next month's advances when paid."
        )
    return sheet


def staff_for_month(bs_year: int, bs_month: int) -> list[Staff]:
    """Workers employed on any day of the month, already paid for it, or with an advance
    in it (e.g. one carried over after they left, which they still owe)."""
    start, end = month_bounds(bs_year, bs_month)
    paid = SalaryPayment.objects.filter(bs_year=bs_year, bs_month=bs_month).values("staff")
    owing = StaffAdvance.objects.filter(date__range=(start, end)).values("staff")
    working = Q(joined_on__lte=end) & (Q(left_on__isnull=True) | Q(left_on__gte=start))
    paid_ids = set(paid.values_list("staff", flat=True))
    return [
        staff
        for staff in Staff.objects.filter(working | Q(pk__in=paid) | Q(pk__in=owing)).order_by(
            "name"
        )
        # A month wholly covered by the opening balance has nothing to pay.
        if staff.pk in paid_ids or not ((settled := settled_until(staff)) and settled >= end)
    ]


def payroll(bs_year: int, bs_month: int) -> list[MonthSheet]:
    return [month_sheet(s, bs_year, bs_month) for s in staff_for_month(bs_year, bs_month)]


# -- Guards ---------------------------------------------------------------------------


def _paid_month(staff: Staff, day: dt.date) -> SalaryPayment | None:
    year, month = month_of(day)
    return SalaryPayment.objects.filter(staff=staff, bs_year=year, bs_month=month).first()


def _ensure_open(staff: Staff, day: dt.date) -> None:
    payment = _paid_month(staff, day)
    if payment is not None:
        raise ValidationError(
            {
                "date": f"{staff.name}'s salary for "
                f"{month_label(payment.bs_year, payment.bs_month)} is already paid. "
                "Undo the payment first to change it."
            }
        )


def _not_working(staff: Staff, day: dt.date) -> str:
    return f"{staff.name} was not working here on {bs_string(day)} BS."


def _ensure_counted(staff: Staff, day: dt.date) -> None:
    if not employed_on(staff, day):
        raise ValidationError({"date": _not_working(staff, day)})
    if not counted_on(staff, day):
        raise ValidationError(
            {
                "date": f"{bs_string(day)} BS is settled by {staff.name}'s balance up to "
                f"{balance_label(staff)}. Change the balance instead."
            }
        )


def _ensure_working(staff: Staff, day: dt.date) -> None:
    if day > local_today():
        raise ValidationError({"date": "Attendance cannot be marked for a day still to come."})
    _ensure_counted(staff, day)


# -- Removing a worker ----------------------------------------------------------------


def has_money_records(staff: Staff) -> bool:
    """Salary paid or an advance given: such a worker is kept (marked as left), not deleted."""
    return (
        SalaryPayment.objects.filter(staff=staff).exists()
        or StaffAdvance.objects.filter(staff=staff).exists()
    )


@transaction.atomic
def delete_staff(*, staff: Staff, user: Any, request: Any = None) -> None:
    """Remove a worker entered by mistake, with their attendance marks."""
    if has_money_records(staff):
        raise ValidationError(
            {
                "detail": f"{staff.name} has salary paid or advances given, so the record "
                'is kept. If they have left, switch off "Still working here" and enter '
                "the last working day."
            }
        )
    log_activity(user, "staff.deleted", staff, f"Staff {staff.name} deleted", request=request)
    Attendance.objects.filter(staff=staff).delete()
    staff.delete()


# -- Attendance -----------------------------------------------------------------------


def day_status(day: dt.date, kind: str | None) -> str:
    if is_holiday(day):
        return "worked" if kind == AttendanceKind.WORKED_HOLIDAY else "off"
    return "absent" if kind == AttendanceKind.ABSENT else "present"


@transaction.atomic
def set_attendance(
    *, staff: Staff, day: dt.date, status: str, user: Any, request: Any = None
) -> str:
    """Mark one day. Present and off are the normal state, so they clear any mark."""
    if status not in DAY_STATUSES:
        raise ValidationError({"status": "Choose present, absent, off or worked."})
    holiday = is_holiday(day)
    if holiday and status in ("present", "absent"):
        raise ValidationError({"status": "Saturday is the weekly holiday: mark it off or worked."})
    if not holiday and status in ("off", "worked"):
        raise ValidationError({"status": "A working day is present or absent."})
    _ensure_working(staff, day)
    _ensure_open(staff, day)

    current = Attendance.objects.filter(staff=staff, date=day).first()
    kind = {"absent": AttendanceKind.ABSENT, "worked": AttendanceKind.WORKED_HOLIDAY}.get(status)
    before = day_status(day, current.kind if current else None)
    if kind is None:
        if current is not None:
            current.delete()
    elif current is None:
        Attendance.objects.create(staff=staff, date=day, kind=kind, marked_by=user)
    elif current.kind != kind:
        current.kind, current.marked_by = kind, user
        current.save(update_fields=["kind", "marked_by", "updated_at"])
    if before != status:
        log_activity(
            user,
            "staff.attendance",
            staff,
            f"{staff.name}: {bs_string(day)} BS marked {status} (was {before})",
            request=request,
        )
    return status


def month_days(staff: Staff, bs_year: int, bs_month: int) -> list[dict[str, Any]]:
    """Every day of a BS month for one worker, for the attendance calendar.

    ``editable`` is false for days still to come, days the worker was not here,
    and every day of a paid month.
    """
    start, end = month_bounds(bs_year, bs_month)
    marks = dict(
        Attendance.objects.filter(staff=staff, date__range=(start, end)).values_list("date", "kind")
    )
    paid = SalaryPayment.objects.filter(staff=staff, bs_year=bs_year, bs_month=bs_month).exists()
    today = local_today()
    days = []
    day = start
    while day <= end:
        working = employed_on(staff, day)
        counted = counted_on(staff, day)
        days.append(
            {
                "date": day,
                "bs_day": to_bs(day).day,
                # Nepali calendars start the week on Sunday.
                "weekday": (day.weekday() + 1) % 7,
                "is_holiday": is_holiday(day),
                "status": (
                    day_status(day, marks.get(day))
                    if counted
                    else ("settled" if working else "not_working")
                ),
                "editable": counted and day <= today and not paid,
            }
        )
        day += dt.timedelta(days=1)
    return days


def month_register(bs_year: int, bs_month: int) -> dict[str, Any]:
    """The whole month for everyone, like the paper attendance register."""
    start, end = month_bounds(bs_year, bs_month)
    rows = []
    for staff in staff_for_month(bs_year, bs_month):
        days = month_days(staff, bs_year, bs_month)
        rows.append(
            {
                "staff": staff,
                "paid": SalaryPayment.objects.filter(
                    staff=staff, bs_year=bs_year, bs_month=bs_month
                ).exists(),
                "cells": [{"status": d["status"], "editable": d["editable"]} for d in days],
                "absent": sum(d["status"] == "absent" for d in days),
                "worked": sum(d["status"] == "worked" for d in days),
            }
        )
    days = []
    day = start
    while day <= end:
        days.append(
            {
                "date": day,
                "bs_day": to_bs(day).day,
                "weekday": (day.weekday() + 1) % 7,
                "is_holiday": is_holiday(day),
            }
        )
        day += dt.timedelta(days=1)
    return {"days": days, "rows": rows}


def day_register(day: dt.date) -> list[dict[str, Any]]:
    """Everyone working on ``day`` with their mark, for the daily attendance screen."""
    staff = [
        s
        # By working dates, not "still working here": a past day still shows who left later.
        for s in Staff.objects.filter(joined_on__lte=day).order_by("name")
        if employed_on(s, day)
    ]
    marks = dict(
        Attendance.objects.filter(date=day, staff__in=staff).values_list("staff_id", "kind")
    )
    year, month = month_of(day)
    paid = set(
        SalaryPayment.objects.filter(bs_year=year, bs_month=month, staff__in=staff).values_list(
            "staff_id", flat=True
        )
    )
    return [
        {
            "staff": s,
            "status": day_status(day, marks.get(s.pk)),
            "locked": s.pk in paid or not counted_on(s, day),
        }
        for s in staff
    ]


# -- Advances -------------------------------------------------------------------------


@transaction.atomic
def give_advance(
    *, staff: Staff, day: dt.date, amount: Decimal, note: str, user: Any, request: Any = None
) -> StaffAdvance:
    if amount <= 0:
        raise ValidationError({"amount": "The advance must be more than zero."})
    if day > local_today():
        raise ValidationError({"date": "An advance cannot be dated in the future."})
    _ensure_counted(staff, day)
    _ensure_open(staff, day)
    advance = StaffAdvance.objects.create(
        staff=staff, date=day, amount=q2(amount), note=note.strip(), given_by=user
    )
    log_activity(
        user,
        "staff.advance_given",
        staff,
        f"Advance {format_npr(advance.amount)} to {staff.name} on {bs_string(day)} BS",
        request=request,
    )
    return advance


@transaction.atomic
def delete_advance(*, advance: StaffAdvance, user: Any, request: Any = None) -> None:
    if advance.carried_from_id:
        raise ValidationError(
            {
                "detail": "This advance was carried from last month's salary; "
                "undo that payment instead."
            }
        )
    _ensure_open(advance.staff, advance.date)
    log_activity(
        user,
        "staff.advance_removed",
        advance.staff,
        f"Advance {format_npr(advance.amount)} of {bs_string(advance.date)} BS removed "
        f"for {advance.staff.name}",
        request=request,
    )
    advance.delete()


# -- Paying the month -----------------------------------------------------------------


@transaction.atomic
def pay_salary(
    *,
    staff: Staff,
    bs_year: int,
    bs_month: int,
    paid_on: dt.date,
    mode: str,
    note: str = "",
    user: Any,
    request: Any = None,
) -> SalaryPayment:
    staff = Staff.objects.select_for_update().get(pk=staff.pk)
    start, end = month_bounds(bs_year, bs_month)
    if start > local_today():
        raise ValidationError({"month": "This month has not started yet."})
    if paid_on > local_today():
        raise ValidationError({"paid_on": "The payment date cannot be in the future."})
    if SalaryPayment.objects.filter(staff=staff, bs_year=bs_year, bs_month=bs_month).exists():
        raise ValidationError(
            {
                "month": f"{staff.name}'s salary for {month_label(bs_year, bs_month)} "
                "is already paid."
            }
        )
    sheet = month_sheet(staff, bs_year, bs_month)
    if sheet.days_ahead:
        # Paying now would lock the month and lose the days still to come.
        raise ValidationError(
            {
                "month": f"{month_label(bs_year, bs_month)} is not over yet: it ends on "
                f"{bs_string(end)} BS. Pay then; for money given now, use Give advance."
            }
        )
    if sheet.days_employed == 0 and not sheet.opening_balance:
        raise ValidationError(
            {"month": f"{staff.name} did not work here in {month_label(bs_year, bs_month)}."}
        )
    if sheet.carry_forward:
        ny, nm = next_month(bs_year, bs_month)
        if SalaryPayment.objects.filter(staff=staff, bs_year=ny, bs_month=nm).exists():
            raise ValidationError(
                {
                    "month": "The advances are more than this month's pay, and next month is "
                    "already paid, so the rest has nowhere to go. Undo next month first."
                }
            )

    payment = SalaryPayment.objects.create(
        staff=staff,
        bs_year=bs_year,
        bs_month=bs_month,
        monthly_salary=sheet.monthly_salary,
        days_in_month=sheet.days_in_month,
        days_employed=sheet.days_employed,
        day_rate=sheet.day_rate,
        absent_days=len(sheet.absent_dates),
        holidays_worked=len(sheet.worked_dates),
        base_pay=sheet.base_pay,
        absent_deduction=sheet.absent_deduction,
        holiday_pay=sheet.holiday_pay,
        holiday_rate=sheet.holiday_rate,
        earned=sheet.earned,
        advances=sheet.advances_total,
        opening_balance=sheet.opening_balance,
        net_paid=sheet.net,
        carried_forward=sheet.carry_forward,
        paid_on=paid_on,
        mode=mode,
        note=note.strip(),
        paid_by=user,
    )
    if sheet.carry_forward:
        StaffAdvance.objects.create(
            staff=staff,
            date=end + dt.timedelta(days=1),
            amount=sheet.carry_forward,
            note=f"Carried from {month_label(bs_year, bs_month)}",
            given_by=user,
            carried_from=payment,
        )
    log_activity(
        user,
        "staff.salary_paid",
        staff,
        f"Salary {format_npr(payment.net_paid)} paid to {staff.name} for "
        f"{month_label(bs_year, bs_month)}",
        request=request,
    )
    return payment


@transaction.atomic
def undo_salary(*, payment: SalaryPayment, user: Any, reason: str, request: Any = None) -> None:
    """Remove a salary payment (e.g. entered by mistake), unlocking the month."""
    if not reason.strip():
        raise ValidationError({"reason": "Write why the payment is being undone."})
    ny, nm = next_month(payment.bs_year, payment.bs_month)
    if (
        payment.carried_forward
        and SalaryPayment.objects.filter(staff=payment.staff, bs_year=ny, bs_month=nm).exists()
    ):
        raise ValidationError(
            {
                "detail": "Part of this month's advances was carried into next month, which is "
                "already paid. Undo next month first."
            }
        )
    log_activity(
        user,
        "staff.salary_undone",
        payment.staff,
        f"Salary for {month_label(payment.bs_year, payment.bs_month)} of {payment.staff.name} "
        f"undone ({format_npr(payment.net_paid)}): {reason.strip()}",
        request=request,
    )
    payment.delete()
