from decimal import Decimal as D

import pytest

from apps.billing import services as billing
from apps.core.exceptions import BusinessError
from apps.orders import services
from apps.orders.models import OrderStatus
from apps.production.models import Stage

pytestmark = pytest.mark.django_db


def test_quotation_has_no_jobs_and_snapshots_rates(make_order, star_flex):
    order = make_order(confirm=False, items=[(D("10"), D("4"), 2)])
    assert order.status == OrderStatus.QUOTATION
    assert order.jobs.count() == 0
    item = order.items.get()
    assert item.rate == D("35") and item.min_sqft == D("5")
    assert order.subtotal == D("2800.00")  # 40 × 35 × 2
    assert order.vat_amount == D("364.00")
    assert order.total == D("3164.00")


def test_confirm_creates_one_job_per_item(make_order, desk):
    order = make_order(confirm=False, items=[(D("10"), D("4"), 1), (D("3"), D("2"), 4)])
    services.confirm_order(order=order, user=desk)
    order.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED
    jobs = list(order.jobs.order_by("job_no"))
    assert [j.job_no for j in jobs] == ["JOB-1001", "JOB-1002"]
    assert all(j.stage == Stage.DESIGN for j in jobs)
    with pytest.raises(BusinessError):
        services.confirm_order(order=order, user=desk)


def test_edit_keeps_quoted_rate_but_new_lines_use_current_rate(make_order, star_flex, desk):
    order = make_order(confirm=False)
    star_flex.rate = D("40")
    star_flex.save()
    existing = order.items.get()
    data = services.OrderInput(
        items=[
            services.ItemInput(
                id=existing.pk,
                media_type=star_flex,
                width=D("10"),
                height=D("4"),
                unit="ft",
                quantity=1,
            ),
            services.ItemInput(
                media_type=star_flex, width=D("10"), height=D("4"), unit="ft", quantity=1
            ),
        ]
    )
    services.update_order(order=order, user=desk, data=data)
    rates = list(order.items.order_by("line_no").values_list("rate", flat=True))
    assert rates == [D("35.00"), D("40.00")]


def test_front_desk_discount_limit(make_order, shop, desk, owner, customer, star_flex):
    data = services.OrderInput(
        items=[
            services.ItemInput(
                media_type=star_flex, width=D("10"), height=D("4"), unit="ft", quantity=1
            )
        ],
        discount_type="percent",
        discount_value=D("15"),
    )
    with pytest.raises(BusinessError) as exc:
        services.create_order(user=desk, customer=customer, data=data)
    assert "discount_value" in exc.value.detail
    order = services.create_order(user=owner, customer=customer, data=data)  # owner has no limit
    assert order.discount_amount == D("210.00")


def test_vat_not_added_when_shop_not_registered(make_order, shop):
    shop.is_vat_registered = False
    shop.save()
    order = make_order()
    assert order.vat_amount == D("0.00")
    assert order.total == order.subtotal


def test_cannot_edit_after_invoice_and_cancel_rules(make_order, desk, owner):
    order = make_order()
    invoice = billing.issue_invoice(order=order, user=desk)
    with pytest.raises(BusinessError):
        services.update_order(order=order, user=desk, data=services.OrderInput(items=[]))
    with pytest.raises(BusinessError):
        services.cancel_order(order=order, user=desk, reason="Customer changed mind")
    billing.cancel_invoice(invoice=invoice, user=owner, reason="Wrong customer chosen")
    services.cancel_order(order=order, user=desk, reason="Customer changed mind")
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert set(order.jobs.values_list("stage", flat=True)) == {Stage.CANCELLED}


def test_cannot_remove_printed_item(make_order, desk, operator, star_flex_rolls):
    from apps.production.services import move_job

    order = make_order(items=[(D("10"), D("4"), 1), (D("3"), D("2"), 1)])
    first, second = order.jobs.order_by("job_no")
    move_job(job=first, user=desk, to_stage=Stage.READY_FOR_PRINT)
    move_job(job=first, user=operator, to_stage=Stage.PRINTING)
    keep_only_second = services.OrderInput(
        items=[
            services.ItemInput(
                id=second.order_item_id,
                media_type=second.order_item.media_type,
                width=D("3"),
                height=D("2"),
                unit="ft",
                quantity=1,
            )
        ]
    )
    with pytest.raises(BusinessError):
        services.update_order(order=order, user=desk, data=keep_only_second)


def test_deliver_requires_ready_jobs_then_invoices_and_settles(
    make_order, desk, operator, star_flex_rolls
):
    from apps.billing.selectors import customer_balance
    from apps.production.services import move_job

    order = make_order()
    with pytest.raises(BusinessError):
        services.deliver_order(order=order, user=desk)
    job = order.jobs.get()
    move_job(job=job, user=desk, to_stage=Stage.READY_FOR_PRINT)
    move_job(job=job, user=operator, to_stage=Stage.PRINTING)
    move_job(
        job=job,
        user=operator,
        to_stage=Stage.READY,
        material={"roll": star_flex_rolls[0], "used_sqft": D("41")},
    )
    order.refresh_from_db()
    assert order.status == OrderStatus.READY
    result = services.deliver_order(
        order=order, user=desk, payment={"amount": order.total, "mode": "cash"}
    )
    order.refresh_from_db()
    assert order.status == OrderStatus.DELIVERED
    assert result["invoice"] is not None
    assert customer_balance(order.customer) == D("0.00")
