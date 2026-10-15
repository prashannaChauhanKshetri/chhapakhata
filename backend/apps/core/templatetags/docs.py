"""Template filters for printed documents."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template

from apps.core.dates import bs_long as _bs_long
from apps.core.dates import bs_string
from apps.core.money import amount_in_words, format_npr

register = template.Library()


@register.filter
def npr(value) -> str:
    """``Rs. 1,25,000.00``"""
    return format_npr(value)


@register.filter
def amount(value) -> str:
    """``1,25,000.00`` (no currency prefix, for table cells)."""
    if value in (None, ""):
        return ""
    return format_npr(value).replace("Rs. ", "")


@register.filter
def words(value) -> str:
    return amount_in_words(value)


@register.filter
def bs(value) -> str:
    return bs_string(value) or ""


@register.filter
def bs_long(value) -> str:
    return _bs_long(value) or ""


@register.filter(is_safe=True)
def css_string(value) -> str:
    """Make text safe inside a CSS ``content: "..."`` string within a <style> block."""
    text = str(value or "")
    for ch in '"\\<>\n\r':
        text = text.replace(ch, " ")
    return text


@register.filter
def qty(value) -> str:
    """Drop needless trailing zeros: ``12.50`` → ``12.5``, ``8.00`` → ``8``."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    text = f"{number:,.2f}"
    return text.rstrip("0").rstrip(".") if "." in text else text
