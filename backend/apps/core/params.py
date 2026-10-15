"""Helpers for reading query parameters consistently."""

from __future__ import annotations

import datetime as dt

from rest_framework.exceptions import ValidationError


def parse_date(value: str | None, name: str) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({name: ["Use the format YYYY-MM-DD."]}) from exc


def parse_range(params, default_from: dt.date | None, default_to: dt.date) -> tuple:
    date_from = parse_date(params.get("from"), "from") or default_from
    date_to = parse_date(params.get("to"), "to") or default_to
    if date_from and date_to and date_from > date_to:
        raise ValidationError({"from": ["The start date is after the end date."]})
    return date_from, date_to


def output_format(params, allowed: tuple[str, ...] = ("json", "pdf", "xlsx")) -> str:
    fmt = (params.get("export") or "json").lower()
    if fmt not in allowed:
        raise ValidationError({"export": [f"Choose one of: {', '.join(allowed)}."]})
    return fmt
