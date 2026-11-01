"""Uploading customers with opening balances, the rate card and opening stock,
in the loose layouts shops actually use."""

import io
from decimal import Decimal as D

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook, load_workbook

from apps.billing import services as billing
from apps.billing.selectors import customer_balance
from apps.catalog.models import AddOn, AddOnBasis, MediaType, PricingUnit
from apps.customers.models import Customer
from apps.inventory.models import StockItem, StockKind, StockUnit
from apps.system.go_live import run_import

pytestmark = pytest.mark.django_db


def _xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    for row in rows:
        wb.active.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _run(owner, kind, rows, **kwargs):
    return run_import(kind, _xlsx(rows), name=f"{kind}.xlsx", user=owner, **kwargs)


LEDGER = [
    ["Party ledger as on 2083.07.15"],
    ["S.N.", "Party Name", "Contact", "Address", "PAN No.", "Dr", "Cr"],
    [1, "Hotel Kalpana", "9858020005 / 9812345678", "Nepalgunj", "304567890", "Rs. 4,500", ""],
    [2, "Ramesh Gupta", "", "Kohalpur", "1234", "", 500],
    [3, "Hotel Kalpana", "9858020005", "Nepalgunj", "", 4500, ""],
    [None, "Total", "", "", "", 4500, 500],
]


def test_customer_ledger_in_a_loose_layout(owner):
    result = _run(owner, "customers", LEDGER, dry_run=False)
    assert result.errors == [] and result.dry_run is False
    assert (result.created, result.skipped) == (2, 1)
    assert result.columns["balance"] == "Dr" and result.columns["credit"] == "Cr"
    kalpana = Customer.objects.get(name="Hotel Kalpana")
    assert (kalpana.phone, kalpana.alt_phone) == ("9858020005", "9812345678")
    assert customer_balance(kalpana) == D("4500.00")
    assert customer_balance(Customer.objects.get(name="Ramesh Gupta")) == D("-500.00")
    assert result.summary == {"opening_due": "4500", "opening_advance": "500"}
    notes = " ".join(w.message for w in result.warnings)
    assert "PAN '1234' is not 9 digits" in notes and "appears again" in notes

    again = _run(owner, "customers", LEDGER, dry_run=False)
    assert again.created == 0 and Customer.objects.count() == 2


def test_an_existing_customer_with_transactions_is_not_charged_twice(owner):
    customer = Customer.objects.create(name="Hotel Kalpana", phone="9858020005")
    billing.post_adjustment(customer=customer, amount=D("100"), narration="Earlier", user=owner)
    result = _run(owner, "customers", LEDGER[:3], dry_run=False)
    assert result.skipped == 1
    assert "already has entries in the ledger" in result.warnings[0].message
    assert customer_balance(customer) == D("100.00")


def test_a_dr_cr_column_and_signed_balances(owner):
    rows = [
        ["Name", "Balance", "Dr/Cr"],
        ["Advance Party", 700, "Cr"],
        ["Due Party", "(300)", ""],
    ]
    _run(owner, "customers", rows, dry_run=False)
    assert customer_balance(Customer.objects.get(name="Advance Party")) == D("-700.00")
    assert customer_balance(Customer.objects.get(name="Due Party")) == D("-300.00")


def test_rate_card_in_a_loose_layout(owner):
    rows = [
        ["Item", "Price", "Unit", "Type", "Basis"],
        ["Star Flex", "Rs. 35", "per sq ft", "", ""],
        ["Photo print A4", "60/pc", "", "", ""],
        ["Eyelets", 5, "", "Add-on", "per piece"],
        ["Lamination", 10, "", "", "per sq ft"],
    ]
    result = _run(owner, "rate-card", rows, dry_run=False)
    assert result.errors == [] and result.created == 4
    assert MediaType.objects.get(name="Star Flex").pricing_unit == PricingUnit.SQFT
    photo = MediaType.objects.get(name="Photo print A4")
    assert (photo.pricing_unit, photo.rate) == (PricingUnit.PIECE, D("60.00"))
    assert AddOn.objects.get(name="Eyelets").basis == AddOnBasis.PER_PIECE
    assert AddOn.objects.get(name="Lamination").basis == AddOnBasis.PER_SQFT

    rows[1][1] = 38
    again = _run(owner, "rate-card", rows, dry_run=False)
    assert again.updated == 4 and MediaType.objects.get(name="Star Flex").rate == D("38.00")


def test_opening_stock_in_a_loose_layout(owner):
    rows = [
        ["Material", "Width", "Length", "Rolls", "Qty", "Unit"],
        ["Star Flex", 10, 164, 2, "", ""],
        ["Black ink", "", "", "", 4, "ltr"],
        ["Eyelets (box of 500)", "", "", "", 3, "box"],
    ]
    result = _run(owner, "opening-stock", rows, dry_run=False)
    assert result.errors == [] and result.created == 3
    flex = StockItem.objects.get(name="Star Flex")
    assert flex.kind == StockKind.ROLL_MEDIA and flex.rolls.count() == 2
    assert flex.on_hand == D("3280.00")
    ink = StockItem.objects.get(name="Black ink")
    assert (ink.kind, ink.unit, ink.on_hand) == (StockKind.INK, StockUnit.LITRE, D("4.00"))
    assert StockItem.objects.get(name__startswith="Eyelets").kind == StockKind.EYELETS

    again = _run(owner, "opening-stock", rows, dry_run=False)
    assert again.skipped == 3 and StockItem.objects.get(name="Star Flex").rolls.count() == 2


def test_errors_save_nothing_unless_skipped(owner):
    rows = [["Name", "Balance"], ["Good", 100], ["Bad", "lots"]]
    blocked = _run(owner, "customers", rows, dry_run=False)
    assert blocked.dry_run is True and blocked.errors[0].row == 3
    assert Customer.objects.count() == 0
    _run(owner, "customers", rows, dry_run=False, skip_errors=True)
    assert list(Customer.objects.values_list("name", flat=True)) == ["Good"]


def test_api_check_import_and_templates(api, owner, desk):
    url = "/api/v1/system/import/customers/"
    upload = SimpleUploadedFile("ledger.xlsx", _xlsx(LEDGER))
    assert api(desk).post(url, {"file": upload}).status_code == 403
    checked = api(owner).post(url, {"file": SimpleUploadedFile("l.xlsx", _xlsx(LEDGER))}).json()
    assert checked["dry_run"] is True and checked["created"] == 2
    assert Customer.objects.count() == 0
    saved = (
        api(owner)
        .post(
            url,
            {
                "file": SimpleUploadedFile("l.xlsx", _xlsx(LEDGER)),
                "dry_run": "false",
                "as_of": "2026-11-09",
            },
        )
        .json()
    )
    assert saved["dry_run"] is False and Customer.objects.count() == 2

    for kind in ("customers", "rate-card", "opening-stock"):
        response = api(owner).get(f"/api/v1/system/import/{kind}/template/")
        assert response.status_code == 200
        load_workbook(io.BytesIO(response.content))
    assert api(owner).get("/api/v1/system/import/nothing/template/").status_code == 404
