"""Money is never counted twice or lost across imports, bills and payments."""

import datetime as dt
import io
from decimal import Decimal as D

import pytest
from freezegun import freeze_time
from openpyxl import Workbook

from apps.billing import services as billing
from apps.billing.models import Payment
from apps.billing.selectors import customer_balance
from apps.core.exceptions import BusinessError
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.reports.selectors import sales_summary
from apps.system.go_live import run_import
from apps.system.work_log import import_work_log

pytestmark = pytest.mark.django_db

HEADER = ["Date", "Particular", "Items", "Qty", "Rate", "Amount", "Payment"]
OPENING_DAY = dt.date(2026, 7, 16)  # 32 Asar 2083: last fiscal year's closing day


@pytest.fixture(autouse=True)
def _today():
    with freeze_time("2026-10-16 10:00"):
        yield


def _xlsx(rows):
    wb = Workbook()
    for row in rows:
        wb.active.append(row)
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def _work_log(owner, rows, **kwargs):
    return import_work_log(
        _xlsx([HEADER, *rows]), name="work.xlsx", user=owner, dry_run=False, **kwargs
    )


def test_billing_an_imported_order_adds_only_the_vat(api, owner, shop):
    _work_log(owner, [["2083.04.10", "Rapti Stores", "Banner", 1, 500, 500, 0]])
    order = Order.objects.get()
    assert api(owner).get(f"/api/v1/orders/{order.pk}/").json()["actions"]["can_invoice"]
    invoice = billing.issue_invoice(order=order, user=owner, add_vat=True)
    assert (invoice.total, invoice.vat_amount) == (D("565.00"), D("65.00"))
    assert customer_balance(order.customer) == D("565.00")  # 500 moved to the bill + VAT
    with pytest.raises(BusinessError, match="already on bill"):
        billing.issue_invoice(order=order, user=owner)
    billing.cancel_invoice(invoice=invoice, user=owner, reason="Wrong customer")
    assert customer_balance(order.customer) == D("500.00")  # back on the account


def test_work_before_the_opening_balance_is_already_inside_it(owner):
    customer = Customer.objects.create(name="Rapti Stores")
    billing.set_opening_balance(customer=customer, amount=D("2000"), user=owner)
    result = _work_log(
        owner,
        [
            ["2083.03.25", "Rapti Stores", "Banner", 1, 700, 700, 0],  # last year
            ["2083.04.10", "Rapti Stores", "Banner", 1, 500, 500, 0],  # this year
        ],
    )
    assert result.rows_imported == 1 and result.rows_before_opening == 1
    assert "already in that balance" in result.warnings[0].message
    assert customer_balance(customer) == D("2500.00")  # not 3,200


def test_a_row_edited_after_import_is_a_problem_not_a_second_order(owner):
    rows = [
        ["2083.04.10", "Rapti Stores", "Banner", 1, 500, 500, 0],
        ["2083.04.11", "Rapti Stores", "Sticker", 2, 100, 200, 0],
    ]
    _work_log(owner, rows)
    edited = [rows[0], ["2083.04.11", "Rapti Stores", "Sticker", 2, 120, 240, 0]]
    result = _work_log(owner, edited)
    assert result.dry_run is True  # blocked by the problem row
    assert "changed after it was imported as ORD-" in result.errors[0].message
    assert Order.objects.count() == 2

    # A genuinely new row next to unchanged ones is still imported.
    more = [*rows, ["2083.04.12", "Rapti Stores", "Banner", 1, 500, 500, 0]]
    added = _work_log(owner, more)
    assert added.errors == [] and added.rows_imported == 1 and Order.objects.count() == 3


def test_the_same_payment_saved_twice_in_a_moment_is_refused(api, customer, desk):
    billing.receive_payment(user=desk, customer=customer, amount="750", mode="cash")
    with pytest.raises(BusinessError) as caught:
        billing.receive_payment(user=desk, customer=customer, amount="750", mode="cash")
    assert "saved a moment ago" in str(caught.value.detail)
    second = billing.receive_payment(
        user=desk, customer=customer, amount="750", mode="cash", allow_repeat=True
    )
    assert second.pk and Payment.objects.count() == 2

    body = {"customer": customer.pk, "amount": "750", "mode": "cash"}
    refused = api(desk).post("/api/v1/payments/", body, format="json")
    assert refused.status_code == 400 and refused.json()["errors"][0]["attr"] == "repeat"
    allowed = api(desk).post("/api/v1/payments/", {**body, "allow_repeat": True}, format="json")
    assert allowed.status_code == 201


def test_two_minutes_later_the_same_amount_is_a_new_payment(customer, desk):
    with freeze_time("2026-10-16 10:00"):
        billing.receive_payment(user=desk, customer=customer, amount="750", mode="cash")
    with freeze_time("2026-10-16 10:03"):
        billing.receive_payment(user=desk, customer=customer, amount="750", mode="cash")
    assert Payment.objects.count() == 2


def test_sales_summary_shows_imported_work_on_its_own_line(owner):
    _work_log(owner, [["2083.04.10", "Rapti Stores", "Banner", 1, 500, 500, 0]])
    report = sales_summary(dt.date(2026, 7, 17), dt.date(2026, 10, 16))
    metrics = {m.label: m.value for m in report.summary}
    assert metrics["Total sales"] == D("0")  # no bills: the IRD sales register is unchanged
    assert metrics["Work imported from the work log (not billed)"] == D("500.00")


def test_a_corrected_payment_sheet_points_to_correct_payment(owner):
    customer = Customer.objects.create(name="Rapti Stores")
    first = [["Date", "Customer", "Amount", "Remark"], ["2083.04.10", "Rapti Stores", 500, "Cash"]]
    run_import("payments", _xlsx(first).getvalue(), name="p.xlsx", user=owner, dry_run=False)
    fixed = [first[0], ["2083.04.10", "Rapti Stores", 550, "Cash"]]
    result = run_import(
        "payments", _xlsx(fixed).getvalue(), name="p.xlsx", user=owner, dry_run=True
    )
    assert "use Correct payment" in result.warnings[0].message
    assert customer_balance(customer) == D("-500.00")


def test_customers_sheet_fills_the_phone_of_a_customer_the_work_log_made(owner):
    _work_log(owner, [["2083.04.10", "Rapti Stores", "Banner", 1, 500, 500, 0]])
    sheet = [["Name", "Phone", "Balance"], ["Rapti Stores", "9800000001", 1200]]
    run_import("customers", _xlsx(sheet).getvalue(), name="c.xlsx", user=owner, dry_run=False)
    customer = Customer.objects.get()  # one customer, not two
    assert customer.phone == "9800000001"
    assert customer_balance(customer) == D("1700.00")  # 1,200 carried in + 500 this year


def test_customers_with_different_phones_stay_apart(owner):
    Customer.objects.create(name="Ram Prints", phone="9800000001")
    sheet = [["Name", "Phone", "Balance"], ["Ram Prints", "9800000002", 300]]
    run_import("customers", _xlsx(sheet).getvalue(), name="c.xlsx", user=owner, dry_run=False)
    assert Customer.objects.filter(name="Ram Prints").count() == 2


def test_the_same_adjustment_twice_in_a_moment_is_refused(customer, owner):
    billing.post_adjustment(
        customer=customer, amount=D("100"), narration="Missed charge", user=owner
    )
    with pytest.raises(BusinessError, match="saved a moment ago"):
        billing.post_adjustment(
            customer=customer, amount=D("100"), narration="Missed charge", user=owner
        )
    assert customer_balance(customer) == D("100.00")


def test_one_order_paid_in_two_ways_with_equal_amounts_keeps_both(owner):
    header = ["Date", "Particular", "Items", "Qty", "Rate", "Amount", "Payment", "Payment Mode"]
    rows = [
        ["2083.04.10", "Rapti Stores", "Banner", 1, 375, 375, 375, "Cash"],
        ["2083.04.10", "Rapti Stores", "Sticker", 1, 375, 375, 375, "eSewa"],
    ]
    result = import_work_log(_xlsx([header, *rows]), name="work.xlsx", user=owner, dry_run=False)
    assert result.payments == 2 and result.warnings == []
    assert customer_balance(Customer.objects.get()) == D("0.00")


def _pay_sheet(owner, rows, **kwargs):
    sheet = [["Date", "Customer", "Amount", "Remark"], *rows]
    return run_import(
        "payments", _xlsx(sheet).getvalue(), name="p.xlsx", user=owner, dry_run=False, **kwargs
    )


def test_a_days_payments_split_differently_are_not_counted_twice(owner):
    """OM Traders: the work log had 500 + 450 (two ways), the sheet one 950."""
    header = ["Date", "Particular", "Items", "Qty", "Rate", "Amount", "Payment", "Payment Mode"]
    rows = [
        ["2083.05.25", "Aayan Digital", "Banner", 1, 500, 500, 500, "Cash"],
        ["2083.05.25", "Aayan Digital", "Photo", 1, 450, 450, 450, "eSewa"],
        ["2083.06.25", "Best Design", "Banner", 1, 4810, 4810, 4810, "Cash"],
    ]
    import_work_log(_xlsx([header, *rows]), name="w.xlsx", user=owner, dry_run=False)
    result = _pay_sheet(
        owner,
        [
            ["2083.05.25", "Aayan Digital", 950, "Bill payment"],
            ["2083.06.25", "Best Design", 3170, "Bill payment"],  # 4810 split the other way
            ["2083.06.25", "Best Design", 1640, "Bill payment"],
            ["2083.06.26", "Best Design", 1000, "A new payment"],
        ],
    )
    assert (result.created, result.skipped) == (1, 3)
    assert "split differently" in result.warnings[0].message
    assert customer_balance(Customer.objects.get(name="Aayan Digital")) == D("0.00")
    assert customer_balance(Customer.objects.get(name="Best Design")) == D("-1000.00")


def test_work_log_after_a_sheet_with_the_day_split_differently(owner):
    Customer.objects.create(name="Aayan Digital")
    _pay_sheet(owner, [["2083.05.25", "Aayan Digital", 950, "Bill payment"]])
    header = ["Date", "Particular", "Items", "Qty", "Rate", "Amount", "Payment", "Payment Mode"]
    rows = [
        ["2083.05.25", "Aayan Digital", "Banner", 1, 500, 500, 500, "Cash"],
        ["2083.05.25", "Aayan Digital", "Photo", 1, 450, 450, 450, "eSewa"],
    ]
    result = import_work_log(_xlsx([header, *rows]), name="w.xlsx", user=owner, dry_run=False)
    assert result.payments == 0 and "already recorded" in result.warnings[0].message
    assert customer_balance(Customer.objects.get()) == D("0.00")


def test_the_duplicate_checker_finds_days_split_differently(owner):
    from apps.billing.services import duplicate_sheet_payments

    header = ["Date", "Particular", "Items", "Qty", "Rate", "Amount", "Payment", "Payment Mode"]
    rows = [
        ["2083.05.25", "Aayan Digital", "Banner", 1, 500, 500, 500, "Cash"],
        ["2083.05.25", "Aayan Digital", "Photo", 1, 450, 450, 450, "eSewa"],
    ]
    import_work_log(_xlsx([header, *rows]), name="w.xlsx", user=owner, dry_run=False)
    customer = Customer.objects.get()
    billing.record_imported_payment(  # what an older import made
        user=owner,
        customer=customer,
        amount=D("950"),
        mode="cash",
        payment_date=dt.date(2026, 9, 10),
        import_ref="old-sheet-row",
    )
    assert [copy.amount for copy, _ in duplicate_sheet_payments()] == [D("950.00")]
