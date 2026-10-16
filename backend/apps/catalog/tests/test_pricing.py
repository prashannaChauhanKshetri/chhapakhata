"""Pricing engine: every rule from the proposal's price formula."""

from decimal import Decimal as D

import pytest

from apps.catalog.models import AddOnBasis
from apps.catalog.pricing import (
    AddOnLine,
    ItemLine,
    PricingError,
    area_sqft,
    discount_percent,
    perimeter_ft,
    price_item,
    price_order,
    to_feet,
)


def item(w="10", h="4", unit="ft", qty=1, rate="35", min_sqft="5", addons=()):
    return ItemLine(
        width=D(w),
        height=D(h),
        unit=unit,
        quantity=qty,
        rate=D(rate),
        min_sqft=D(min_sqft),
        addons=addons,
    )


@pytest.mark.parametrize(
    ("w", "h", "unit", "expected"),
    [
        ("10", "4", "ft", "40.00"),
        ("24", "36", "in", "6.00"),
        ("30", "40", "in", "8.33"),  # 8.333… rounds half up to 2 dp
        ("100", "50", "cm", "5.38"),  # 5000 / 929.0304 = 5.382
        ("2.5", "3.5", "ft", "8.75"),
    ],
)
def test_area_conversions(w, h, unit, expected):
    assert area_sqft(D(w), D(h), unit) == D(expected)


def test_to_feet_and_perimeter():
    assert to_feet(D("18"), "in") == D("1.5000")
    assert to_feet(D("30.48"), "cm") == D("1.0000")
    assert perimeter_ft(D("10"), D("4"), "ft") == D("28.00")
    assert perimeter_ft(D("24"), D("36"), "in") == D("10.00")


def test_basic_item_price():
    result = price_item(item())
    assert result.sqft == D("40.00")
    assert result.billable_sqft == D("40.00")
    assert result.base_amount == D("1400.00")  # 40 × 35
    assert result.min_applied is False


def test_minimum_sqft_applies_per_piece():
    # 2 × 2 ft = 4 sq ft, charged as 5 sq ft each, 3 pieces
    result = price_item(item(w="2", h="2", qty=3))
    assert result.sqft == D("4.00")
    assert result.billable_sqft == D("5.00")
    assert result.min_applied is True
    assert result.base_amount == D("525.00")  # 5 × 35 × 3
    assert result.total_sqft == D("12.00")
    assert result.total_billable_sqft == D("15.00")


def test_zero_minimum_charges_actual_size():
    result = price_item(item(w="1", h="1", min_sqft="0"))
    assert result.base_amount == D("35.00")


@pytest.mark.parametrize(
    ("basis", "rate", "qty", "expected"),
    [
        (AddOnBasis.FIXED, "500", "1", "500.00"),  # design charge, once per line
        (AddOnBasis.PER_PIECE, "5", "8", "240.00"),  # 8 eyelets × Rs 5 × 6 pieces
        (AddOnBasis.PER_SQFT, "15", "1", "3600.00"),  # 40 sq ft × 6 × Rs 15
        (AddOnBasis.PER_RUNNING_FT, "60", "1", "10080.00"),  # 28 ft × 6 × Rs 60
        (AddOnBasis.PERCENT, "20", "1", "1680.00"),  # 20% of 8,400
    ],
)
def test_addon_bases(basis, rate, qty, expected):
    addon = AddOnLine(name="x", basis=basis, rate=D(rate), quantity=D(qty))
    result = price_item(item(qty=6, addons=(addon,)))
    assert result.base_amount == D("8400.00")
    assert result.addons[0].amount == D(expected)
    assert result.line_total == D("8400.00") + D(expected)


def test_order_totals_with_percent_discount_and_vat():
    pricing = price_order(
        [
            item(
                w="2",
                h="2",
                qty=3,
                addons=(AddOnLine("Eyelets", AddOnBasis.PER_PIECE, D("5"), D("4")),),
            )
        ],
        discount_type="percent",
        discount_value=D("5"),
        vat_rate=D("13"),
    )
    t = pricing.totals
    assert t.subtotal == D("585.00")
    assert t.discount_amount == D("29.25")
    assert t.taxable_amount == D("555.75")
    assert t.vat_amount == D("72.25")  # 72.2475 rounds half up
    assert t.total == D("628.00")
    assert len(pricing.warnings) == 1


def test_fixed_discount_and_no_vat():
    t = price_order([item()], discount_type="amount", discount_value=D("100")).totals
    assert t.discount_amount == D("100.00")
    assert t.vat_amount == D("0.00")
    assert t.total == D("1300.00")


def test_round_to_rupee():
    # 30 × 40 in = 8.33 sq ft × Rs 37 = 308.21; VAT 13% = 40.07 → 348.28 → 348
    t = price_order(
        [item(w="30", h="40", unit="in", rate="37")], vat_rate=D("13"), round_to_rupee=True
    ).totals
    assert t.subtotal == D("308.21")
    assert t.total == D("348.00")
    assert t.round_off == D("-0.28")


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"w": "0"}, "width"),
        ({"h": "-1"}, "height"),
        ({"qty": 0}, "quantity"),
        ({"rate": "-5"}, "rate"),
        ({"unit": "yd"}, "unit"),
    ],
)
def test_invalid_items(kwargs, field):
    with pytest.raises(PricingError) as exc:
        price_item(item(**kwargs))
    assert exc.value.field == field


def test_discount_validation():
    with pytest.raises(PricingError):
        price_order([item()], discount_type="amount", discount_value=D("5000"))
    with pytest.raises(PricingError):
        price_order([item()], discount_type="percent", discount_value=D("101"))


def test_discount_percent_helper():
    assert discount_percent(D("1000"), D("125")) == D("12.50")
    assert discount_percent(D("0"), D("0")) == D("0")


# --- per-piece items ---


def test_per_piece_item_ignores_size_and_minimum():
    result = price_item(
        ItemLine(
            width=D("0"),
            height=D("0"),
            unit="ft",
            quantity=4,
            rate=D("160"),
            min_sqft=D("5"),
            per_piece=True,
        )
    )
    assert result.base_amount == D("640.00")
    assert result.sqft == D("0")
    assert result.min_applied is False


def test_per_piece_item_may_carry_a_size_for_reference():
    result = price_item(
        ItemLine(
            width=D("2"),
            height=D("1"),
            unit="ft",
            quantity=3,
            rate=D("400"),
            min_sqft=D("5"),
            per_piece=True,
        )
    )
    assert result.sqft == D("2.00")
    assert result.base_amount == D("1200.00")


def test_area_item_still_needs_a_size():
    with pytest.raises(PricingError) as exc:
        price_item(
            ItemLine(
                width=D("0"), height=D("0"), unit="ft", quantity=1, rate=D("35"), min_sqft=D("5")
            )
        )
    assert exc.value.field == "width"
