"""Order lifecycle: quotation → confirmed → in production → ready → delivered.

Prices always come from :mod:`apps.catalog.pricing`. Rates are snapshotted on
each item. When an order is edited, unchanged lines keep the rate they were
quoted at; new lines and lines whose media changed use today's rate card.

Staff may also charge a line at the customer's last rate for that item, or at
a custom rate. A custom rate below the rate card counts against the user's
discount limit; the customer's last rate does not, because it was already
agreed once.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.billing.models import InvoiceStatus
from apps.catalog.models import AddOn, MediaType
from apps.catalog.pricing import (
    AddOnLine,
    ItemLine,
    OrderPricing,
    PricingError,
    discount_percent,
    price_order,
)
from apps.core.activity import log_activity
from apps.core.exceptions import BusinessError
from apps.core.models import ShopSettings
from apps.core.money import fmt_qty, q2
from apps.core.sequences import DocType, next_number

from .models import DiscountType, Order, OrderItem, OrderItemAddOn, OrderStatus, RateSource
from .selectors import LastRate, last_rates_for

EDITABLE_STATUSES = {
    OrderStatus.QUOTATION,
    OrderStatus.CONFIRMED,
    OrderStatus.IN_PRODUCTION,
    OrderStatus.READY,
}


@dataclass
class AddOnInput:
    addon: AddOn
    quantity: Decimal = Decimal("1")


@dataclass
class ItemInput:
    media_type: MediaType
    width: Decimal
    height: Decimal
    unit: str
    quantity: int
    description: str = ""
    finishing: str = ""
    design_file_ref: str = ""
    addons: list[AddOnInput] = field(default_factory=list)
    id: int | None = None
    rate: Decimal | None = None  # None = keep the quoted rate, or use the rate card


@dataclass(frozen=True)
class LineMeta:
    """Where a line's rate came from, kept beside the pricing result."""

    card_rate: Decimal
    rate_source: str
    pricing_unit: str
    rate_changed: bool = False


@dataclass(frozen=True)
class PricedOrder:
    pricing: OrderPricing
    lines: tuple[LineMeta, ...]

    @property
    def items(self):
        return self.pricing.items

    @property
    def totals(self):
        return self.pricing.totals

    @property
    def warnings(self):
        return self.pricing.warnings


@dataclass
class OrderInput:
    items: list[ItemInput]
    discount_type: str = DiscountType.NONE
    discount_value: Decimal = Decimal("0")


def item_input_from_data(data: dict[str, Any]) -> ItemInput:
    return ItemInput(
        id=data.get("id"),
        media_type=data["media_type"],
        width=data["width"],
        height=data["height"],
        unit=data.get("unit", "ft"),
        quantity=data.get("quantity", 1),
        description=data.get("description", ""),
        finishing=data.get("finishing", ""),
        design_file_ref=data.get("design_file_ref", ""),
        rate=data.get("rate"),
        addons=[
            AddOnInput(addon=a["addon"], quantity=a.get("quantity", Decimal("1")))
            for a in data.get("addons", [])
        ],
    )


def _item_lines(
    items: list[ItemInput],
    shop: ShopSettings,
    existing: dict[int, OrderItem] | None = None,
    last_rates: dict[int, LastRate] | None = None,
) -> tuple[list[ItemLine], list[LineMeta]]:
    existing = existing or {}
    last_rates = last_rates or {}
    lines: list[ItemLine] = []
    metas: list[LineMeta] = []
    for index, item in enumerate(items):
        media = item.media_type
        if not media.is_active and not (
            item.id in existing and existing[item.id].media_type_id == media.pk
        ):
            raise BusinessError(
                {f"items.{index}.media_type": [f"{media.name} is no longer offered."]}
            )
        previous = existing.get(item.id) if item.id else None
        if previous is not None and previous.media_type_id == media.pk:
            rate, min_sqft = previous.rate, previous.min_sqft
            pricing_unit = previous.pricing_unit
            card_rate = previous.card_rate if previous.card_rate is not None else media.rate
            source = previous.rate_source
            old_addons = {a.addon_id: a for a in previous.addons.all()}
        else:
            rate = card_rate = media.rate
            pricing_unit = media.pricing_unit
            min_sqft = media.min_sqft if media.min_sqft is not None else shop.default_min_sqft
            source = RateSource.CARD
            old_addons = {}

        changed = False
        if item.rate is not None and q2(item.rate) != rate:
            if item.rate < 0:
                raise BusinessError({f"items.{index}.rate": ["Rate cannot be negative."]})
            rate, changed = q2(item.rate), True
            last = last_rates.get(media.pk)
            if rate == card_rate:
                source = RateSource.CARD
            elif last is not None and rate == last.rate:
                source = RateSource.PREVIOUS
            else:
                source = RateSource.CUSTOM

        addon_lines = []
        for a in item.addons:
            old = old_addons.get(a.addon.pk)
            addon_lines.append(
                AddOnLine(
                    name=old.name if old else a.addon.name,
                    basis=old.basis if old else a.addon.basis,
                    rate=old.rate if old else a.addon.rate,
                    quantity=a.quantity,
                    key=a.addon.pk,
                )
            )
        lines.append(
            ItemLine(
                width=item.width,
                height=item.height,
                unit=item.unit,
                quantity=item.quantity,
                rate=rate,
                min_sqft=min_sqft,
                addons=tuple(addon_lines),
                key=index,
                per_piece=pricing_unit == "piece",
            )
        )
        metas.append(
            LineMeta(
                card_rate=card_rate,
                rate_source=source,
                pricing_unit=pricing_unit,
                rate_changed=changed,
            )
        )
    return lines, metas


def calculate(
    data: OrderInput,
    *,
    order: Order | None = None,
    shop: ShopSettings | None = None,
    customer: Any = None,
) -> PricedOrder:
    """Price an order input. Raises ``BusinessError`` with form-friendly field paths."""
    if not data.items:
        raise BusinessError({"items": ["Add at least one item."]})
    shop = shop or ShopSettings.load()
    existing = None
    if order is not None:
        existing = {i.pk: i for i in order.items.prefetch_related("addons")}
        customer = customer or order.customer
    last_rates = (
        last_rates_for(customer, exclude_order=order)
        if customer is not None and any(i.rate is not None for i in data.items)
        else {}
    )
    lines, metas = _item_lines(data.items, shop, existing, last_rates)
    vat_rate = (
        order.vat_rate
        if order is not None and order.status != OrderStatus.QUOTATION
        else (shop.vat_rate if shop.is_vat_registered else Decimal("0"))
    )
    try:
        pricing = price_order(
            lines,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            vat_rate=vat_rate,
            round_to_rupee=shop.round_total_to_rupee,
        )
    except PricingError as exc:
        raise BusinessError({exc.field: [exc.message]}) from exc
    return PricedOrder(pricing=pricing, lines=tuple(metas))


def check_discount_limit(user: Any, pricing: PricedOrder) -> None:
    """Staff limits: the order discount, and custom rates below the rate card."""
    limit = user.discount_limit()
    if limit is None:
        return
    for index, (meta, result) in enumerate(zip(pricing.lines, pricing.items, strict=True)):
        if not meta.rate_changed or meta.rate_source != RateSource.CUSTOM:
            continue
        if meta.card_rate <= 0 or result.rate >= meta.card_rate:
            continue
        below = discount_percent(meta.card_rate, meta.card_rate - result.rate)
        if below > limit:
            raise BusinessError(
                {
                    f"items.{index}.rate": [
                        f"Rs {fmt_qty(result.rate)} is {fmt_qty(below)}% below the rate card "
                        f"(Rs {fmt_qty(meta.card_rate)}). Your limit is {fmt_qty(limit)}%; "
                        "ask the owner to approve this rate."
                    ]
                }
            )
    effective = discount_percent(pricing.totals.subtotal, pricing.totals.discount_amount)
    if effective > limit:
        raise BusinessError(
            {
                "discount_value": [
                    f"Your discount limit is {fmt_qty(limit)}% of the subtotal "
                    f"(this is {fmt_qty(effective)}%). Ask the owner to approve a bigger discount."
                ]
            }
        )


def _apply_totals(order: Order, pricing: PricedOrder) -> None:
    t = pricing.totals
    order.subtotal = t.subtotal
    order.discount_amount = t.discount_amount
    order.taxable_amount = t.taxable_amount
    order.vat_rate = t.vat_rate
    order.vat_amount = t.vat_amount
    order.round_off = t.round_off
    order.total = t.total


def _write_item(
    order: Order,
    line_no: int,
    data: ItemInput,
    result: Any,
    meta: LineMeta,
    item: OrderItem | None,
) -> OrderItem:
    item = item or OrderItem(order=order)
    item.line_no = line_no
    item.media_type = data.media_type
    item.media_name = data.media_type.name
    item.description = data.description
    item.width = data.width
    item.height = data.height
    item.unit = data.unit
    item.quantity = result.quantity
    item.width_ft = result.width_ft
    item.height_ft = result.height_ft
    item.sqft = result.sqft
    item.billable_sqft = result.billable_sqft
    item.pricing_unit = meta.pricing_unit
    item.rate = result.rate
    item.rate_source = meta.rate_source
    item.card_rate = meta.card_rate
    item.min_sqft = result.min_sqft
    item.base_amount = result.base_amount
    item.addons_amount = result.addons_amount
    item.line_total = result.line_total
    item.finishing = data.finishing
    item.design_file_ref = data.design_file_ref
    item.save()
    item.addons.all().delete()
    OrderItemAddOn.objects.bulk_create(
        OrderItemAddOn(
            item=item,
            addon_id=addon_result.key,
            name=addon_result.name,
            basis=addon_result.basis,
            rate=addon_result.rate,
            quantity=addon_result.quantity,
            amount=addon_result.amount,
        )
        for addon_result in result.addons
    )
    return item


def _validate_deadline(deadline: dt.datetime | None, *, is_new: bool) -> None:
    if deadline is not None and is_new and deadline < timezone.now() - dt.timedelta(minutes=5):
        raise BusinessError({"deadline": ["The deadline is in the past."]})


@transaction.atomic
def create_order(
    *,
    user: Any,
    customer: Any,
    data: OrderInput,
    deadline: dt.datetime | None = None,
    is_urgent: bool = False,
    notes: str = "",
    confirm: bool = False,
    request: Any = None,
) -> Order:
    """Create a quotation (default) or a confirmed order."""
    if not customer.is_active:
        raise BusinessError({"customer": ["This customer is inactive."]})
    _validate_deadline(deadline, is_new=True)
    shop = ShopSettings.load()
    pricing = calculate(data, shop=shop, customer=customer)
    check_discount_limit(user, pricing)

    order = Order(
        order_no=next_number(DocType.ORDER).number,
        customer=customer,
        status=OrderStatus.QUOTATION,
        deadline=deadline,
        is_urgent=is_urgent,
        notes=notes,
        discount_type=data.discount_type,
        discount_value=data.discount_value,
        created_by=user,
    )
    _apply_totals(order, pricing)
    order.save()
    for line_no, (item_data, result, meta) in enumerate(
        zip(data.items, pricing.items, pricing.lines, strict=True), 1
    ):
        _write_item(order, line_no, item_data, result, meta, None)
    log_activity(user, "order.created", order, message=f"Total {order.total}", request=request)
    if confirm:
        confirm_order(order=order, user=user, request=request)
    return order


def has_active_invoice(order: Order) -> bool:
    return order.invoices.filter(status=InvoiceStatus.ISSUED).exists()


@transaction.atomic
def update_order(
    *,
    order: Order,
    user: Any,
    data: OrderInput,
    deadline: dt.datetime | None = None,
    is_urgent: bool = False,
    notes: str = "",
    request: Any = None,
) -> Order:
    """Edit items and terms. Locked once invoiced; printed items cannot be removed."""
    from apps.production.models import Stage
    from apps.production.services import create_jobs_for_order

    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in EDITABLE_STATUSES:
        raise BusinessError(f"A {order.get_status_display().lower()} order cannot be edited.")
    if has_active_invoice(order):
        raise BusinessError("This order has an issued invoice. Cancel the invoice to edit it.")

    pricing = calculate(data, order=order)
    check_discount_limit(user, pricing)

    existing = {i.pk: i for i in order.items.select_related("job")}
    kept_ids = {i.id for i in data.items if i.id}
    unknown = kept_ids - set(existing)
    if unknown:
        raise BusinessError({"items": ["An item does not belong to this order."]})
    for item_id, item in existing.items():
        if item_id in kept_ids:
            continue
        job = getattr(item, "job", None)
        if job is not None and (job.stage >= Stage.PRINTING or job.material_recorded):
            raise BusinessError(
                {
                    "items": [
                        f"Item {item.line_no} ({job.job_no}) is already printed, "
                        "so it cannot be removed."
                    ]
                }
            )
        item.delete()

    # Move kept lines out of the way of the (order, line_no) constraint before renumbering.
    for offset, pk in enumerate(sorted(kept_ids)):
        OrderItem.objects.filter(pk=pk).update(line_no=1000 + offset)

    deadline_changed = order.deadline != deadline
    for line_no, (item_data, result, meta) in enumerate(
        zip(data.items, pricing.items, pricing.lines, strict=True), 1
    ):
        previous = existing.get(item_data.id) if item_data.id else None
        if previous is not None:
            previous.refresh_from_db()
        item = _write_item(order, line_no, item_data, result, meta, previous)
        job = getattr(item, "job", None) if previous is not None else None
        if job is not None:
            job.design_file_ref = item.design_file_ref
            if deadline_changed:
                job.deadline = deadline
            job.save(update_fields=["design_file_ref", "deadline", "updated_at"])

    order.discount_type = data.discount_type
    order.discount_value = data.discount_value
    order.deadline = deadline
    order.is_urgent = is_urgent
    order.notes = notes
    _apply_totals(order, pricing)
    order.save()
    if order.status != OrderStatus.QUOTATION:
        create_jobs_for_order(order, user)  # jobs for newly added items
    log_activity(user, "order.updated", order, message=f"Total {order.total}", request=request)
    return order


@transaction.atomic
def confirm_order(*, order: Order, user: Any, request: Any = None) -> Order:
    """Turn a quotation into a confirmed order and open one job per item."""
    from apps.production.services import create_jobs_for_order

    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != OrderStatus.QUOTATION:
        raise BusinessError("Only quotations can be confirmed.")
    order.status = OrderStatus.CONFIRMED
    order.confirmed_at = timezone.now()
    order.save(update_fields=["status", "confirmed_at", "updated_at"])
    create_jobs_for_order(order, user)
    log_activity(user, "order.confirmed", order, request=request)
    return order


@transaction.atomic
def cancel_order(*, order: Order, user: Any, reason: str, request: Any = None) -> Order:
    """Cancel an order and its jobs. Payments already taken stay as customer credit."""
    from apps.production.services import cancel_jobs_for_order

    reason = (reason or "").strip()
    if len(reason) < 5:
        raise BusinessError({"reason": ["Write a short reason (at least 5 characters)."]})
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status in (OrderStatus.CANCELLED, OrderStatus.DELIVERED):
        raise BusinessError(f"A {order.get_status_display().lower()} order cannot be cancelled.")
    if has_active_invoice(order):
        raise BusinessError("Cancel the order's invoice first.")
    cancel_jobs_for_order(order, user, reason)
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancel_reason = reason
    order.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    log_activity(user, "order.cancelled", order, message=reason, request=request)
    return order


@transaction.atomic
def deliver_order(
    *,
    order: Order,
    user: Any,
    issue_invoice: bool = True,
    payment: dict[str, Any] | None = None,
    note: str = "",
    request: Any = None,
) -> dict[str, Any]:
    """Counter checkout: invoice if needed, take payment (optional), mark delivered."""
    from apps.billing import services as billing
    from apps.production.models import Stage
    from apps.production.services import move_job, refresh_order_status

    order = Order.objects.select_for_update().select_related("customer").get(pk=order.pk)
    if order.status in (OrderStatus.QUOTATION, OrderStatus.CANCELLED, OrderStatus.DELIVERED):
        raise BusinessError(f"A {order.get_status_display().lower()} order cannot be delivered.")
    jobs = list(order.jobs.exclude(stage__in=[Stage.CANCELLED, Stage.DELIVERED]))
    not_ready = [j.job_no for j in jobs if j.stage < Stage.READY]
    if not_ready:
        raise BusinessError(f"These jobs are not ready for collection yet: {', '.join(not_ready)}.")

    invoice = order.invoices.filter(status=InvoiceStatus.ISSUED).first()
    if invoice is None and issue_invoice:
        invoice = billing.issue_invoice(order=order, user=user, request=request)

    received = None
    if payment and payment.get("amount"):
        received = billing.receive_payment(
            user=user, customer=order.customer, order=order, request=request, **payment
        )

    for job in jobs:
        move_job(
            job=job,
            user=user,
            to_stage=Stage.DELIVERED,
            note=note or "Delivered to customer",
            request=request,
            refresh_order=False,
        )
    refresh_order_status(order)
    log_activity(user, "order.delivered", order, request=request)
    return {"order": order, "invoice": invoice, "payment": received}
