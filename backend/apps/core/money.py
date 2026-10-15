"""Money helpers. All amounts are ``Decimal``; floats are never used for money."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")

_ONES = (
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
)
_TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


def to_decimal(value: Decimal | int | str | float | None) -> Decimal:
    if value is None or value == "":
        return ZERO
    if isinstance(value, float):
        value = repr(value)
    return Decimal(value)


def q2(value: Decimal | int | str | float | None) -> Decimal:
    """Round to 2 decimal places, half up (the convention on Nepali bills)."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def fmt_qty(value: Decimal | int | str | float | None) -> str:
    """Quantity without needless zeros: ``Decimal("10.00")`` → ``"10"``, ``2.50`` → ``"2.5"``."""
    number = to_decimal(value)
    text = f"{number:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _two_digits(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")


def _three_digits(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} Hundred")
    if rest:
        parts.append(_two_digits(rest))
    return " ".join(parts)


def integer_in_words(n: int) -> str:
    """Spell an integer using the South Asian system (thousand, lakh, crore)."""
    if n == 0:
        return "Zero"
    if n < 0:
        return "Minus " + integer_in_words(-n)
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1_000)
    if crore:
        parts.append(f"{integer_in_words(crore)} Crore")
    if lakh:
        parts.append(f"{_two_digits(lakh)} Lakh")
    if thousand:
        parts.append(f"{_two_digits(thousand)} Thousand")
    if n:
        parts.append(_three_digits(n))
    return " ".join(parts)


def amount_in_words(amount: Decimal | int | str) -> str:
    """Spell an amount for bills.

    ``Decimal("125000.50")`` → ``"Rupees One Lakh Twenty-Five Thousand and Fifty Paisa Only"``
    """
    value = q2(amount)
    negative = value < 0
    value = abs(value)
    rupees = int(value)
    paisa = int((value - rupees) * 100)
    words = f"Rupees {integer_in_words(rupees)}"
    if paisa:
        words += f" and {_two_digits(paisa)} Paisa"
    words += " Only"
    return f"Minus {words}" if negative else words


def format_npr(amount: Decimal | int | str | None) -> str:
    """Format with South Asian digit grouping: ``Rs. 1,25,000.00``."""
    value = q2(amount)
    sign = "-" if value < 0 else ""
    integer, _, fraction = f"{abs(value):.2f}".partition(".")
    if len(integer) > 3:
        head, tail = integer[:-3], integer[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        integer = ",".join([*groups, tail])
    return f"{sign}Rs. {integer}.{fraction}"
