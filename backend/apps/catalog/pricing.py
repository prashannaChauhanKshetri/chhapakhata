"""Pricing engine: the only place prices are calculated.

Pure functions over ``Decimal`` values with no database access, so every rule
is easy to test. The proposal's formula, per item::

    total = [MAX(sq ft, minimum sq ft) × rate × quantity] + add-ons − discount

Per-piece items (photos, 3D letters, name plates) are priced ``rate × quantity``;
their size is optional and the minimum sq ft rule does not apply.

Order level::

    subtotal = Σ line totals
    discount = percent of subtotal, or a fixed amount (never above subtotal)
    taxable  = subtotal − discount
    VAT      = taxable × VAT rate            (only when the shop is VAT-registered)
    total    = taxable + VAT (+ round-off to the nearest rupee, if enabled)

Rounding: square feet per piece and every money amount are rounded to two
decimals, half up, at the step where they are produced.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from apps.core.money import ZERO, q2, to_decimal

from .models import AddOnBasis, LengthUnit

HUNDRED = Decimal("100")
FOUR_PLACES = Decimal("0.0001")

# Divisor converting (width × height) in a unit into square feet.
_SQ_DIVISOR = {
    LengthUnit.FOOT: Decimal("1"),
    LengthUnit.INCH: Decimal("144"),
    LengthUnit.CM: Decimal("929.0304"),  # 30.48²
}
# Divisor converting a length in a unit into feet.
_LEN_DIVISOR = {
    LengthUnit.FOOT: Decimal("1"),
    LengthUnit.INCH: Decimal("12"),
    LengthUnit.CM: Decimal("30.48"),
}


class PricingError(ValueError):
    """Invalid pricing input. ``field`` names the offending input for form errors."""

    def __init__(self, message: str, field: str = "non_field_errors"):
        super().__init__(message)
        self.message = message
        self.field = field


def _unit(unit: str) -> LengthUnit:
    try:
        return LengthUnit(unit)
    except ValueError as exc:
        raise PricingError(f"Unknown unit '{unit}'. Use in, ft or cm.", "unit") from exc


def to_feet(value: Decimal | int | str, unit: str) -> Decimal:
    return (to_decimal(value) / _LEN_DIVISOR[_unit(unit)]).quantize(
        FOUR_PLACES, rounding=ROUND_HALF_UP
    )


def area_sqft(width: Decimal | int | str, height: Decimal | int | str, unit: str) -> Decimal:
    """Area of one piece in sq ft, rounded to 2 decimals."""
    raw = to_decimal(width) * to_decimal(height) / _SQ_DIVISOR[_unit(unit)]
    return q2(raw)


def perimeter_ft(width: Decimal | int | str, height: Decimal | int | str, unit: str) -> Decimal:
    """Perimeter of one piece in running feet (for framing), rounded to 2 decimals."""
    raw = 2 * (to_decimal(width) + to_decimal(height)) / _LEN_DIVISOR[_unit(unit)]
    return q2(raw)


@dataclass(frozen=True)
class AddOnLine:
    name: str
    basis: str
    rate: Decimal
    quantity: Decimal = Decimal("1")
    key: Hashable = None


@dataclass(frozen=True)
class AddOnResult:
    name: str
    basis: str
    rate: Decimal
    quantity: Decimal
    amount: Decimal
    key: Hashable = None


@dataclass(frozen=True)
class ItemLine:
    width: Decimal
    height: Decimal
    unit: str
    quantity: int
    rate: Decimal
    min_sqft: Decimal
    addons: Sequence[AddOnLine] = ()
    key: Hashable = None
    per_piece: bool = False


@dataclass(frozen=True)
class ItemResult:
    width_ft: Decimal
    height_ft: Decimal
    sqft: Decimal
    billable_sqft: Decimal
    min_applied: bool
    quantity: int
    rate: Decimal
    min_sqft: Decimal
    base_amount: Decimal
    addons: tuple[AddOnResult, ...]
    addons_amount: Decimal
    line_total: Decimal
    key: Hashable = None

    @property
    def total_sqft(self) -> Decimal:
        return self.sqft * self.quantity

    @property
    def total_billable_sqft(self) -> Decimal:
        return self.billable_sqft * self.quantity


@dataclass(frozen=True)
class Totals:
    subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    round_off: Decimal
    total: Decimal


@dataclass(frozen=True)
class OrderPricing:
    items: tuple[ItemResult, ...]
    totals: Totals
    warnings: tuple[str, ...] = field(default_factory=tuple)


def addon_amount(
    addon: AddOnLine,
    *,
    item_quantity: int,
    sqft_per_piece: Decimal,
    perimeter_per_piece: Decimal,
    base_amount: Decimal,
) -> Decimal:
    rate = to_decimal(addon.rate)
    qty = to_decimal(addon.quantity)
    if rate < 0:
        raise PricingError(f"{addon.name}: rate cannot be negative.", "addons")
    if qty < 0:
        raise PricingError(f"{addon.name}: quantity cannot be negative.", "addons")
    match AddOnBasis(addon.basis):
        case AddOnBasis.FIXED:
            amount = rate * qty
        case AddOnBasis.PER_PIECE:
            amount = rate * qty * item_quantity
        case AddOnBasis.PER_SQFT:
            amount = rate * sqft_per_piece * item_quantity
        case AddOnBasis.PER_RUNNING_FT:
            amount = rate * perimeter_per_piece * item_quantity
        case AddOnBasis.PERCENT:
            amount = base_amount * rate / HUNDRED
    return q2(amount)


def price_item(line: ItemLine) -> ItemResult:
    width, height = to_decimal(line.width), to_decimal(line.height)
    rate, min_sqft = to_decimal(line.rate), to_decimal(line.min_sqft)
    sized = width > 0 and height > 0
    if not line.per_piece or width != 0 or height != 0:
        # Per-piece items may leave the size empty (both zero); everything else needs it.
        if width <= 0:
            raise PricingError("Width must be greater than zero.", "width")
        if height <= 0:
            raise PricingError("Height must be greater than zero.", "height")
    if int(line.quantity) < 1:
        raise PricingError("Quantity must be at least 1.", "quantity")
    if rate < 0:
        raise PricingError("Rate cannot be negative.", "rate")
    if min_sqft < 0:
        raise PricingError("Minimum sq ft cannot be negative.", "min_sqft")

    quantity = int(line.quantity)
    sqft = area_sqft(width, height, line.unit) if sized else ZERO
    perimeter = perimeter_ft(width, height, line.unit) if sized else ZERO
    if line.per_piece:
        min_sqft = ZERO
        billable = sqft
        base_amount = q2(rate * quantity)
    else:
        billable = max(sqft, q2(min_sqft))
        base_amount = q2(billable * rate * quantity)

    addon_results = tuple(
        AddOnResult(
            name=a.name,
            basis=a.basis,
            rate=q2(a.rate),
            quantity=to_decimal(a.quantity),
            amount=addon_amount(
                a,
                item_quantity=quantity,
                sqft_per_piece=sqft,
                perimeter_per_piece=perimeter,
                base_amount=base_amount,
            ),
            key=a.key,
        )
        for a in line.addons
    )
    addons_amount = q2(sum((a.amount for a in addon_results), ZERO))
    return ItemResult(
        width_ft=to_feet(width, line.unit),
        height_ft=to_feet(height, line.unit),
        sqft=sqft,
        billable_sqft=billable,
        min_applied=billable > sqft,
        quantity=quantity,
        rate=q2(rate),
        min_sqft=q2(min_sqft),
        base_amount=base_amount,
        addons=addon_results,
        addons_amount=addons_amount,
        line_total=q2(base_amount + addons_amount),
        key=line.key,
    )


def discount_amount_for(subtotal: Decimal, discount_type: str, discount_value: Decimal) -> Decimal:
    value = to_decimal(discount_value)
    if discount_type in ("", "none", None) or value == 0:
        return ZERO
    if value < 0:
        raise PricingError("Discount cannot be negative.", "discount_value")
    if discount_type == "percent":
        if value > HUNDRED:
            raise PricingError("Discount percent cannot exceed 100.", "discount_value")
        return q2(subtotal * value / HUNDRED)
    if discount_type == "amount":
        if value > subtotal:
            raise PricingError("Discount cannot be more than the subtotal.", "discount_value")
        return q2(value)
    raise PricingError(f"Unknown discount type '{discount_type}'.", "discount_type")


def discount_percent(subtotal: Decimal, discount: Decimal) -> Decimal:
    """Effective discount as a percent of subtotal (for staff limits)."""
    if subtotal <= 0:
        return ZERO
    return (discount / subtotal * HUNDRED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def price_order(
    items: Sequence[ItemLine],
    *,
    discount_type: str = "none",
    discount_value: Decimal | int | str = ZERO,
    vat_rate: Decimal | int | str = ZERO,
    round_to_rupee: bool = False,
) -> OrderPricing:
    """Price a whole order. ``vat_rate`` is 0 when the shop is not VAT-registered."""
    results = tuple(price_item(item) for item in items)
    subtotal = q2(sum((r.line_total for r in results), ZERO))
    discount = discount_amount_for(subtotal, discount_type, to_decimal(discount_value))
    taxable = q2(subtotal - discount)
    rate = to_decimal(vat_rate)
    vat = q2(taxable * rate / HUNDRED)
    total = q2(taxable + vat)
    round_off = ZERO
    if round_to_rupee:
        rounded = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        round_off = q2(rounded - total)
        total = q2(rounded)

    warnings = tuple(
        f"Item {i}: minimum {r.min_sqft} sq ft charged instead of {r.sqft} sq ft."
        for i, r in enumerate(results, start=1)
        if r.min_applied
    )
    return OrderPricing(
        items=results,
        totals=Totals(
            subtotal=subtotal,
            discount_amount=discount,
            taxable_amount=taxable,
            vat_rate=q2(rate),
            vat_amount=vat,
            round_off=round_off,
            total=total,
        ),
        warnings=warnings,
    )
