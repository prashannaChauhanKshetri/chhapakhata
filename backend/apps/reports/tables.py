"""A small, format-neutral report structure.

Every report builds a :class:`Report`. The same object renders as JSON for the
web app, as an Excel workbook and as a PDF, so the three always match.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from apps.core.dates import bs_string

KINDS = {"text", "money", "number", "sqft", "date", "percent"}


@dataclass
class Column:
    key: str
    label: str
    kind: str = "text"

    @property
    def numeric(self) -> bool:
        return self.kind in {"money", "number", "sqft", "percent"}


@dataclass
class Table:
    title: str
    columns: list[Column]
    rows: list[dict[str, Any]]
    totals: dict[str, Any] | None = None
    empty_message: str = "Nothing to show for this period."


@dataclass
class Metric:
    label: str
    value: Any
    kind: str = "money"


@dataclass
class Report:
    slug: str
    title: str
    period: str
    summary: list[Metric] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


def period_label(date_from: dt.date | None, date_to: dt.date) -> str:
    if date_from is None or date_from == date_to:
        return f"{date_to:%d %b %Y} ({bs_string(date_to)} BS)"
    return (
        f"{date_from:%d %b %Y} to {date_to:%d %b %Y} "
        f"({bs_string(date_from)} to {bs_string(date_to)} BS)"
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    return value


def report_to_json(report: Report) -> dict[str, Any]:
    return {
        "slug": report.slug,
        "title": report.title,
        "period": report.period,
        "params": {k: _json_value(v) for k, v in report.params.items()},
        "summary": [
            {"label": m.label, "value": _json_value(m.value), "kind": m.kind}
            for m in report.summary
        ],
        "tables": [
            {
                "title": t.title,
                "columns": [{"key": c.key, "label": c.label, "kind": c.kind} for c in t.columns],
                "rows": [{k: _json_value(v) for k, v in row.items()} for row in t.rows],
                "totals": {k: _json_value(v) for k, v in t.totals.items()} if t.totals else None,
                "empty_message": t.empty_message,
            }
            for t in report.tables
        ],
    }
