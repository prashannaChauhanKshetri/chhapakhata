import threading
from decimal import Decimal as D

import pytest
from django.db import connection

from apps.core.exceptions import BusinessError
from apps.inventory import services
from apps.inventory.models import (
    AppendOnlyError,
    MovementType,
    RollStatus,
    StockItem,
    StockKind,
    StockUnit,
)

pytestmark = pytest.mark.django_db


def test_purchase_creates_rolls_and_movements(star_flex_rolls, star_flex_stock):
    star_flex_stock.refresh_from_db()
    assert star_flex_stock.on_hand == D("1250.00")
    assert [r.code for r in star_flex_rolls] == ["R-0001", "R-0002"]
    assert all(r.status == RollStatus.ACTIVE for r in star_flex_rolls)
    movement = star_flex_stock.movements.first()
    assert movement.movement_type == MovementType.PURCHASE
    purchase_line = star_flex_rolls[0].purchase_line
    assert purchase_line.quantity == D("1000.00")
    assert purchase_line.rate == D("9.0000")  # Rs 9,000 / 1,000 sq ft


def test_movements_are_append_only(star_flex_rolls, star_flex_stock):
    movement = star_flex_stock.movements.first()
    movement.reason = "edited"
    with pytest.raises(AppendOnlyError):
        movement.save()
    with pytest.raises(AppendOnlyError):
        movement.delete()


def test_wastage_cannot_exceed_roll(star_flex_rolls, star_flex_stock, operator):
    small = star_flex_rolls[1]
    with pytest.raises(BusinessError):
        services.record_wastage(
            user=operator,
            stock_item=star_flex_stock,
            roll=small,
            quantity=D("251"),
            reason="Misprint",
        )
    services.record_wastage(
        user=operator, stock_item=star_flex_stock, roll=small, quantity=D("250"), reason="Misprint"
    )
    small.refresh_from_db()
    assert small.remaining_sqft == D("0.00")
    assert small.status == RollStatus.FINISHED


def test_roll_media_requires_a_roll(star_flex_rolls, star_flex_stock, operator):
    with pytest.raises(BusinessError):
        services.record_wastage(
            user=operator, stock_item=star_flex_stock, quantity=D("1"), reason="x"
        )


def test_adjust_to_counted_quantity(star_flex_rolls, star_flex_stock, owner):
    roll = star_flex_rolls[0]
    movement = services.adjust_stock(
        user=owner,
        stock_item=star_flex_stock,
        roll=roll,
        counted_quantity=D("980"),
        reason="Physical count",
    )
    assert movement.quantity == D("-20.00")
    star_flex_stock.refresh_from_db()
    assert star_flex_stock.on_hand == D("1230.00")
    with pytest.raises(BusinessError):
        services.adjust_stock(
            user=owner,
            stock_item=star_flex_stock,
            roll=roll,
            counted_quantity=D("980"),
            reason="Again",
        )
    with pytest.raises(BusinessError):
        services.adjust_stock(
            user=owner, stock_item=star_flex_stock, roll=roll, counted_quantity=D("900"), reason=""
        )


def test_non_roll_items_opening_and_usage(owner, operator):
    ink = StockItem.objects.create(
        name="Ink", kind=StockKind.INK, unit=StockUnit.LITRE, low_stock_level=D("2")
    )
    services.add_opening_stock(user=owner, stock_item=ink, quantity=D("3"))
    services.record_usage(user=operator, stock_item=ink, quantity=D("1.5"))
    ink.refresh_from_db()
    assert ink.on_hand == D("1.50")
    assert ink.is_low
    with pytest.raises(BusinessError):
        services.record_usage(user=operator, stock_item=ink, quantity=D("2"))


def test_finish_roll_writes_off_leftover(star_flex_rolls, star_flex_stock, owner):
    roll = services.finish_roll(user=owner, roll=star_flex_rolls[1], reason="Offcut too small")
    assert roll.status == RollStatus.FINISHED
    assert roll.remaining_sqft == D("0.00")
    assert star_flex_stock.movements.filter(movement_type=MovementType.WASTAGE).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_wastage_never_overdraws(owner, operator, supplier):
    item = StockItem.objects.create(name="Vinyl", kind=StockKind.ROLL_MEDIA, unit=StockUnit.SQFT)
    services.receive_purchase(
        user=owner,
        supplier=supplier,
        purchase_date=__import__("datetime").date.today(),
        lines=[
            {
                "stock_item": item,
                "roll_count": 1,
                "roll_width_ft": D("1"),
                "roll_length_ft": D("10"),
                "amount": D("100"),
            }
        ],
    )
    roll = item.rolls.get()
    outcomes: list[str] = []

    def worker():
        try:
            services.record_wastage(
                user=operator, stock_item=item, roll=roll.pk, quantity=D("3"), reason="Test"
            )
            outcomes.append("ok")
        except BusinessError:
            outcomes.append("blocked")
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    roll.refresh_from_db()
    assert outcomes.count("ok") == 3  # 3 × 3 = 9 of 10 sq ft
    assert roll.remaining_sqft == D("1.00")
