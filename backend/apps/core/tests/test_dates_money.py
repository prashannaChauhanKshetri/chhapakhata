import datetime as dt
from decimal import Decimal as D

import pytest

from apps.core.dates import (
    bs_long,
    bs_month_range,
    bs_string,
    fiscal_year_for,
    fiscal_year_range,
    from_bs,
)
from apps.core.money import amount_in_words, fmt_qty, format_npr, q2


@pytest.mark.parametrize(
    ("ad", "fy"),
    [
        (dt.date(2026, 7, 16), "2082/83"),  # last day of Asar 2083
        (dt.date(2026, 7, 17), "2083/84"),  # 1 Shrawan 2083
        (dt.date(2026, 10, 15), "2083/84"),
        (dt.date(2027, 4, 14), "2083/84"),  # Baisakh 2084 is still FY 2083/84
    ],
)
def test_fiscal_year_boundaries(ad, fy):
    assert fiscal_year_for(ad) == fy


def test_fiscal_year_range_round_trip():
    start, end = fiscal_year_range("2083/84")
    assert start == dt.date(2026, 7, 17)
    assert fiscal_year_for(start) == "2083/84"
    assert fiscal_year_for(end) == "2083/84"
    assert fiscal_year_for(end + dt.timedelta(days=1)) == "2084/85"


def test_bs_formatting():
    day = dt.date(2026, 10, 15)
    assert bs_string(day) == "2083-06-29"
    assert bs_long(day) == "29 Asoj 2083"
    assert from_bs(2083, 6, 29) == day
    start, end = bs_month_range(day)
    assert bs_string(start) == "2083-06-01"
    assert bs_string(end + dt.timedelta(days=1)) == "2083-07-01"


@pytest.mark.parametrize(
    ("amount", "words"),
    [
        ("0", "Rupees Zero Only"),
        ("15", "Rupees Fifteen Only"),
        ("12430", "Rupees Twelve Thousand Four Hundred Thirty Only"),
        ("125000.50", "Rupees One Lakh Twenty-Five Thousand and Fifty Paisa Only"),
        ("12500000", "Rupees One Crore Twenty-Five Lakh Only"),
        ("101", "Rupees One Hundred One Only"),
    ],
)
def test_amount_in_words(amount, words):
    assert amount_in_words(D(amount)) == words


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        ("0", "Rs. 0.00"),
        ("999", "Rs. 999.00"),
        ("1000", "Rs. 1,000.00"),
        ("125000", "Rs. 1,25,000.00"),
        ("12500000.5", "Rs. 1,25,00,000.50"),
        ("-4500", "-Rs. 4,500.00"),
    ],
)
def test_format_npr_uses_lakh_grouping(amount, text):
    assert format_npr(D(amount)) == text


def test_q2_and_fmt_qty():
    assert q2("2.345") == D("2.35")
    assert q2(None) == D("0.00")
    assert fmt_qty(D("10.00")) == "10"
    assert fmt_qty(D("2.50")) == "2.5"
    assert fmt_qty(D("100")) == "100"
