"""Stock operations. Every change goes through ``_post`` so the cached balances
and the append-only movement ledger always agree.

Concurrency: item and roll rows are locked with ``SELECT ... FOR UPDATE``
before reading balances, so two operators recording usage at the same time
cannot both take the last square feet of a roll.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.activity import log_activity
from apps.core.exceptions import BusinessError
from apps.core.money import ZERO, fmt_qty, q2, to_decimal
from apps.core.sequences import DocType, next_number

from .models import (
    MovementType,
    Purchase,
    PurchaseLine,
    Roll,
    RollStatus,
    StockItem,
    StockMovement,
    Supplier,
)


@dataclass(frozen=True)
class RollSpec:
    width_ft: Decimal
    length_ft: Decimal
    remaining_sqft: Decimal | None = None  # opening stock of a part-used roll


def _lock_item(item: StockItem | int) -> StockItem:
    pk = item.pk if isinstance(item, StockItem) else item
    return StockItem.objects.select_for_update().get(pk=pk)


def _lock_roll(roll: Roll | int) -> Roll:
    pk = roll.pk if isinstance(roll, Roll) else roll
    try:
        return Roll.objects.select_for_update().select_related("stock_item").get(pk=pk)
    except Roll.DoesNotExist as exc:
        raise BusinessError({"roll": ["Choose a valid roll."]}) from exc


def _post(
    item: StockItem,
    *,
    movement_type: str,
    quantity: Decimal,
    user: Any,
    roll: Roll | None = None,
    job: Any = None,
    purchase_line: PurchaseLine | None = None,
    reason: str = "",
) -> StockMovement:
    """Apply a signed quantity to an item (and roll) and append the ledger row.

    Callers must hold row locks on ``item`` and ``roll``.
    """
    quantity = q2(quantity)
    item.on_hand = q2(item.on_hand + quantity)
    item.save(update_fields=["on_hand", "updated_at"])
    if roll is not None:
        roll.remaining_sqft = q2(roll.remaining_sqft + quantity)
        if roll.remaining_sqft <= 0 and roll.status == RollStatus.ACTIVE:
            roll.status = RollStatus.FINISHED
            roll.finished_at = timezone.now()
        elif roll.remaining_sqft > 0 and roll.status == RollStatus.FINISHED:
            roll.status = RollStatus.ACTIVE
            roll.finished_at = None
        roll.save(update_fields=["remaining_sqft", "status", "finished_at", "updated_at"])
    return StockMovement.objects.create(
        stock_item=item,
        roll=roll,
        movement_type=movement_type,
        quantity=quantity,
        balance_after=item.on_hand,
        roll_balance_after=roll.remaining_sqft if roll is not None else None,
        job=job,
        purchase_line=purchase_line,
        reason=reason[:255],
        created_by=user,
    )


def _create_roll(
    item: StockItem, spec: RollSpec, purchase_line: PurchaseLine | None = None
) -> Roll:
    width, length = to_decimal(spec.width_ft), to_decimal(spec.length_ft)
    if width <= 0 or length <= 0:
        raise BusinessError("Roll width and length must be greater than zero.")
    total = q2(width * length)
    return Roll.objects.create(
        code=next_number(DocType.ROLL).number,
        stock_item=item,
        width_ft=width,
        length_ft=length,
        total_sqft=total,
        remaining_sqft=ZERO,  # filled by the movement that brings it into stock
        status=RollStatus.FINISHED,
        purchase_line=purchase_line,
    )


@transaction.atomic
def receive_purchase(
    *,
    user: Any,
    supplier: Supplier,
    purchase_date: dt.date,
    lines: list[dict[str, Any]],
    bill_no: str = "",
    notes: str = "",
    request: Any = None,
) -> Purchase:
    """Record a supplier purchase. Roll media lines create one Roll per physical roll.

    Each line: ``stock_item``, ``amount`` and either ``quantity`` (non-roll items)
    or ``roll_count``, ``roll_width_ft``, ``roll_length_ft`` (roll media).
    """
    if not lines:
        raise BusinessError({"lines": ["Add at least one item."]})
    purchase = Purchase.objects.create(
        purchase_no=next_number(DocType.PURCHASE, purchase_date).number,
        supplier=supplier,
        purchase_date=purchase_date,
        bill_no=bill_no,
        notes=notes,
        created_by=user,
    )
    total = ZERO
    for index, data in enumerate(lines):
        item = _lock_item(data["stock_item"])
        amount = q2(data.get("amount") or 0)
        if amount < 0:
            raise BusinessError({f"lines.{index}.amount": ["Amount cannot be negative."]})
        if item.is_roll_media:
            count = int(data.get("roll_count") or 0)
            width = to_decimal(data.get("roll_width_ft"))
            length = to_decimal(data.get("roll_length_ft"))
            if count < 1 or width <= 0 or length <= 0:
                raise BusinessError(
                    {
                        f"lines.{index}.roll_count": [
                            "Enter the number of rolls, roll width and roll length."
                        ]
                    }
                )
            quantity = q2(count * width * length)
        else:
            count, width, length = None, None, None
            quantity = q2(data.get("quantity") or 0)
            if quantity <= 0:
                raise BusinessError({f"lines.{index}.quantity": ["Quantity must be above zero."]})
        line = PurchaseLine.objects.create(
            purchase=purchase,
            stock_item=item,
            quantity=quantity,
            amount=amount,
            rate=(amount / quantity).quantize(Decimal("0.0001")),
            roll_count=count,
            roll_width_ft=width,
            roll_length_ft=length,
        )
        reason = f"{purchase.purchase_no} from {supplier.name}"
        if item.is_roll_media:
            for _ in range(count or 0):
                roll = _create_roll(item, RollSpec(width, length), purchase_line=line)
                _post(
                    item,
                    movement_type=MovementType.PURCHASE,
                    quantity=roll.total_sqft,
                    user=user,
                    roll=roll,
                    purchase_line=line,
                    reason=reason,
                )
        else:
            _post(
                item,
                movement_type=MovementType.PURCHASE,
                quantity=quantity,
                user=user,
                purchase_line=line,
                reason=reason,
            )
        total += amount
    purchase.total_amount = q2(total)
    purchase.save(update_fields=["total_amount", "updated_at"])
    log_activity(
        user,
        "stock.purchase_received",
        purchase,
        message=f"{len(lines)} line(s), total {purchase.total_amount}",
        request=request,
    )
    return purchase


@transaction.atomic
def add_opening_stock(
    *,
    user: Any,
    stock_item: StockItem,
    quantity: Decimal | None = None,
    rolls: list[RollSpec] | None = None,
    reason: str = "Opening stock",
) -> list[StockMovement]:
    """Bring existing stock into the system at go-live."""
    item = _lock_item(stock_item)
    movements = []
    if item.is_roll_media:
        if not rolls:
            raise BusinessError({"rolls": ["Add at least one roll."]})
        for spec in rolls:
            roll = _create_roll(item, spec)
            remaining = (
                q2(spec.remaining_sqft) if spec.remaining_sqft is not None else roll.total_sqft
            )
            if remaining <= 0 or remaining > roll.total_sqft:
                raise BusinessError(
                    {"rolls": ["Remaining sq ft must be between 0 and the roll size."]}
                )
            movements.append(
                _post(
                    item,
                    movement_type=MovementType.OPENING,
                    quantity=remaining,
                    user=user,
                    roll=roll,
                    reason=reason,
                )
            )
    else:
        qty = q2(quantity or 0)
        if qty <= 0:
            raise BusinessError({"quantity": ["Quantity must be above zero."]})
        movements.append(
            _post(item, movement_type=MovementType.OPENING, quantity=qty, user=user, reason=reason)
        )
    log_activity(user, "stock.opening_added", item, message=f"{len(movements)} entr(ies)")
    return movements


@transaction.atomic
def record_job_consumption(
    *,
    user: Any,
    job: Any,
    roll: Roll | int,
    used_sqft: Decimal | str,
    wastage_sqft: Decimal | str = ZERO,
    wastage_reason: str = "",
    request: Any = None,
) -> dict[str, Any]:
    """Deduct the material a printed job used from the chosen roll.

    Returns the movements plus any non-blocking warnings (e.g. roll too narrow).
    """
    material = job.order_item.media_type.material
    if material is None:
        raise BusinessError(
            {"material": [f"{job.order_item.media_name} is not linked to a stock item."]}
        )
    roll_obj = _lock_roll(roll)
    if roll_obj.stock_item_id != material.pk:
        raise BusinessError(
            {
                "roll": [
                    f"Roll {roll_obj.code} is {roll_obj.stock_item.name}, "
                    f"but this job needs {material.name}."
                ]
            }
        )
    if roll_obj.status != RollStatus.ACTIVE:
        raise BusinessError({"roll": [f"Roll {roll_obj.code} is marked finished."]})

    used, wasted = q2(used_sqft), q2(wastage_sqft or 0)
    if used <= 0:
        raise BusinessError({"used_sqft": ["Enter the sq ft used (above zero)."]})
    if wasted < 0:
        raise BusinessError({"wastage_sqft": ["Wastage cannot be negative."]})
    if used + wasted > roll_obj.remaining_sqft:
        raise BusinessError(
            {
                "used_sqft": [
                    f"Roll {roll_obj.code} has only {roll_obj.remaining_sqft} sq ft left. "
                    "Choose another roll, or ask the owner to adjust the roll after a count."
                ]
            }
        )

    warnings = []
    item = job.order_item
    short_side = min(item.width_ft, item.height_ft)
    if short_side > roll_obj.width_ft:
        warnings.append(
            f"The print's shorter side ({fmt_qty(short_side)} ft) is wider than roll "
            f"{roll_obj.code} ({fmt_qty(roll_obj.width_ft)} ft)."
        )

    stock = _lock_item(material)
    movements = [
        _post(
            stock,
            movement_type=MovementType.CONSUMPTION,
            quantity=-used,
            user=user,
            roll=roll_obj,
            job=job,
            reason=f"{job.job_no} ({job.order.order_no})",
        )
    ]
    if wasted:
        movements.append(
            _post(
                stock,
                movement_type=MovementType.WASTAGE,
                quantity=-wasted,
                user=user,
                roll=roll_obj,
                job=job,
                reason=wastage_reason or f"Print wastage on {job.job_no}",
            )
        )
    job.material_recorded = True
    job.save(update_fields=["material_recorded", "updated_at"])
    log_activity(
        user,
        "stock.consumed",
        job,
        message=f"{used} sq ft from {roll_obj.code}"
        + (f", {wasted} sq ft wasted" if wasted else ""),
        request=request,
    )
    return {"movements": movements, "warnings": warnings}


def _check_available(item: StockItem, roll: Roll | None, quantity: Decimal) -> None:
    available = roll.remaining_sqft if roll is not None else item.on_hand
    if quantity > available:
        where = f"Roll {roll.code}" if roll is not None else item.name
        raise BusinessError(
            {"quantity": [f"{where} has only {available} {item.get_unit_display()} left."]}
        )


def _resolve_roll(item: StockItem, roll: Roll | int | None) -> Roll | None:
    if item.is_roll_media:
        if roll is None:
            raise BusinessError({"roll": ["Choose the roll."]})
        roll_obj = _lock_roll(roll)
        if roll_obj.stock_item_id != item.pk:
            raise BusinessError({"roll": [f"Roll {roll_obj.code} does not belong to {item.name}."]})
        return roll_obj
    if roll is not None:
        raise BusinessError({"roll": ["Only roll media is tracked by roll."]})
    return None


@transaction.atomic
def record_wastage(
    *,
    user: Any,
    stock_item: StockItem,
    quantity: Decimal | str,
    reason: str,
    roll: Roll | int | None = None,
    job: Any = None,
    request: Any = None,
) -> StockMovement:
    """Misprints, test prints and trimming not tied to a normal job deduction."""
    qty = q2(quantity)
    if qty <= 0:
        raise BusinessError({"quantity": ["Quantity must be above zero."]})
    if not reason.strip():
        raise BusinessError({"reason": ["Say why the material was wasted."]})
    item = _lock_item(stock_item)
    roll_obj = _resolve_roll(item, roll)
    _check_available(item, roll_obj, qty)
    movement = _post(
        item,
        movement_type=MovementType.WASTAGE,
        quantity=-qty,
        user=user,
        roll=roll_obj,
        job=job,
        reason=reason,
    )
    log_activity(
        user, "stock.wastage", item, message=f"{qty} {item.unit}: {reason}", request=request
    )
    return movement


@transaction.atomic
def record_usage(
    *,
    user: Any,
    stock_item: StockItem,
    quantity: Decimal | str,
    reason: str = "",
    roll: Roll | int | None = None,
    job: Any = None,
    request: Any = None,
) -> StockMovement:
    """General consumption, e.g. ink, eyelets or frame material used in production."""
    qty = q2(quantity)
    if qty <= 0:
        raise BusinessError({"quantity": ["Quantity must be above zero."]})
    item = _lock_item(stock_item)
    roll_obj = _resolve_roll(item, roll)
    _check_available(item, roll_obj, qty)
    movement = _post(
        item,
        movement_type=MovementType.CONSUMPTION,
        quantity=-qty,
        user=user,
        roll=roll_obj,
        job=job,
        reason=reason or "Used in production",
    )
    log_activity(user, "stock.used", item, message=f"{qty} {item.unit}", request=request)
    return movement


@transaction.atomic
def adjust_stock(
    *,
    user: Any,
    stock_item: StockItem,
    counted_quantity: Decimal | str,
    reason: str,
    roll: Roll | int | None = None,
    request: Any = None,
) -> StockMovement:
    """Set stock to a physically counted quantity (owner only, reason required)."""
    if not reason.strip():
        raise BusinessError({"reason": ["Give a reason for the adjustment."]})
    counted = q2(counted_quantity)
    if counted < 0:
        raise BusinessError({"counted_quantity": ["Counted quantity cannot be negative."]})
    item = _lock_item(stock_item)
    roll_obj = _resolve_roll(item, roll)
    if roll_obj is not None and counted > roll_obj.total_sqft:
        raise BusinessError(
            {
                "counted_quantity": [
                    f"Roll {roll_obj.code} holds at most {roll_obj.total_sqft} sq ft."
                ]
            }
        )
    current = roll_obj.remaining_sqft if roll_obj is not None else item.on_hand
    delta = q2(counted - current)
    if delta == 0:
        raise BusinessError({"counted_quantity": ["The count matches the current stock."]})
    movement = _post(
        item,
        movement_type=MovementType.ADJUSTMENT,
        quantity=delta,
        user=user,
        roll=roll_obj,
        reason=reason,
    )
    log_activity(
        user,
        "stock.adjusted",
        roll_obj or item,
        message=f"{current} → {counted}: {reason}",
        request=request,
    )
    return movement


@transaction.atomic
def finish_roll(*, user: Any, roll: Roll | int, reason: str = "", request: Any = None) -> Roll:
    """Mark a roll finished, writing off any leftover as wastage (roll end/offcut)."""
    roll_obj = _lock_roll(roll)
    if roll_obj.status == RollStatus.FINISHED:
        raise BusinessError({"roll": [f"Roll {roll_obj.code} is already finished."]})
    item = _lock_item(roll_obj.stock_item)
    if roll_obj.remaining_sqft > 0:
        _post(
            item,
            movement_type=MovementType.WASTAGE,
            quantity=-roll_obj.remaining_sqft,
            user=user,
            roll=roll_obj,
            reason=reason or "Roll end written off",
        )
    else:
        roll_obj.status = RollStatus.FINISHED
        roll_obj.finished_at = timezone.now()
        roll_obj.save(update_fields=["status", "finished_at", "updated_at"])
    log_activity(user, "stock.roll_finished", roll_obj, message=reason, request=request)
    roll_obj.refresh_from_db()
    return roll_obj
