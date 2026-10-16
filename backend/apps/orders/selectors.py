"""Read-side queries for orders: what a customer was charged before."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Count

from .models import OrderItem, OrderStatus

# Quotations were never agreed and cancelled orders never happened, so neither sets a rate.
_NOT_SOLD = (OrderStatus.QUOTATION, OrderStatus.CANCELLED)


@dataclass(frozen=True)
class LastRate:
    media_type_id: int
    media_name: str
    pricing_unit: str
    rate: Decimal
    order_id: int
    order_no: str
    order_date: dt.date
    times: int = 1


def _sold_items(customer: Any, exclude_order: Any = None):
    qs = OrderItem.objects.filter(order__customer=customer).exclude(order__status__in=_NOT_SOLD)
    if exclude_order is not None and exclude_order.pk:
        qs = qs.exclude(order=exclude_order)
    return qs


def last_rates_for(customer: Any, *, exclude_order: Any = None) -> dict[int, LastRate]:
    """The most recent rate charged to ``customer`` for each media type, keyed by media id."""
    if customer is None:
        return {}
    items = _sold_items(customer, exclude_order)
    latest = (
        items.order_by("media_type_id", "-order__order_date", "-order_id", "-line_no")
        .distinct("media_type_id")
        .values(
            "media_type_id",
            "media_name",
            "pricing_unit",
            "rate",
            "order_id",
            "order__order_no",
            "order__order_date",
        )
    )
    counts = dict(
        items.values("media_type_id")
        .annotate(n=Count("order_id", distinct=True))
        .values_list("media_type_id", "n")
    )
    return {
        row["media_type_id"]: LastRate(
            media_type_id=row["media_type_id"],
            media_name=row["media_name"],
            pricing_unit=row["pricing_unit"],
            rate=row["rate"],
            order_id=row["order_id"],
            order_no=row["order__order_no"],
            order_date=row["order__order_date"],
            times=counts.get(row["media_type_id"], 1),
        )
        for row in latest
    }
