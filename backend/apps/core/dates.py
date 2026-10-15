"""Bikram Sambat (BS) dates and Nepal fiscal years.

Nepal's fiscal year starts on 1 Shrawan (BS month 4) and ends on the last day
of Asar (BS month 3) of the next BS year. Fiscal year labels look like
``"2083/84"``.
"""

from __future__ import annotations

import datetime as dt

import nepali_datetime
from django.utils import timezone

BS_MONTHS = (
    "Baisakh",
    "Jestha",
    "Asar",
    "Shrawan",
    "Bhadra",
    "Asoj",
    "Kartik",
    "Mangsir",
    "Poush",
    "Magh",
    "Falgun",
    "Chaitra",
)
FISCAL_YEAR_START_MONTH = 4  # Shrawan


def local_today() -> dt.date:
    """Today's date in the shop's time zone."""
    return timezone.localdate()


def as_date(value: dt.date | dt.datetime) -> dt.date:
    """Convert a datetime to the shop-local date. Dates pass through unchanged."""
    if isinstance(value, dt.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    return value


def to_bs(value: dt.date | dt.datetime) -> nepali_datetime.date:
    return nepali_datetime.date.from_datetime_date(as_date(value))


def from_bs(year: int, month: int, day: int) -> dt.date:
    return nepali_datetime.date(year, month, day).to_datetime_date()


def bs_string(value: dt.date | dt.datetime | None) -> str | None:
    """Format as ``YYYY-MM-DD`` in BS, e.g. ``2083-06-29``."""
    if value is None:
        return None
    bs = to_bs(value)
    return f"{bs.year:04d}-{bs.month:02d}-{bs.day:02d}"


def bs_long(value: dt.date | dt.datetime | None) -> str | None:
    """Format as ``29 Asoj 2083``."""
    if value is None:
        return None
    bs = to_bs(value)
    return f"{bs.day} {BS_MONTHS[bs.month - 1]} {bs.year}"


def fiscal_year_for(value: dt.date | dt.datetime) -> str:
    """Return the Nepal fiscal year label for a date, e.g. ``"2083/84"``."""
    bs = to_bs(value)
    start_year = bs.year if bs.month >= FISCAL_YEAR_START_MONTH else bs.year - 1
    return f"{start_year}/{(start_year + 1) % 100:02d}"


def fiscal_year_range(label: str) -> tuple[dt.date, dt.date]:
    """Return the first and last AD dates of a fiscal year label."""
    start_year = int(label.split("/")[0])
    start = from_bs(start_year, FISCAL_YEAR_START_MONTH, 1)
    next_start = from_bs(start_year + 1, FISCAL_YEAR_START_MONTH, 1)
    return start, next_start - dt.timedelta(days=1)


def bs_month_range(value: dt.date | dt.datetime) -> tuple[dt.date, dt.date]:
    """Return the first and last AD dates of the BS month containing ``value``."""
    bs = to_bs(value)
    start = from_bs(bs.year, bs.month, 1)
    next_year, next_month = (bs.year + 1, 1) if bs.month == 12 else (bs.year, bs.month + 1)
    next_start = from_bs(next_year, next_month, 1)
    return start, next_start - dt.timedelta(days=1)


def bs_payload(value: dt.date | dt.datetime | None) -> dict[str, str | None]:
    """Both calendars in one dict, for API responses."""
    if value is None:
        return {"ad": None, "bs": None, "bs_long": None}
    day = as_date(value)
    return {"ad": day.isoformat(), "bs": bs_string(day), "bs_long": bs_long(day)}
