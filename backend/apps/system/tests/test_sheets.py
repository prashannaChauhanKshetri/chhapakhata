"""The forgiving spreadsheet reader shared by every import."""

import datetime as dt
import io
import zipfile
from decimal import Decimal as D

import pytest
from openpyxl import Workbook

from apps.system import work_log
from apps.system.sheets import ColumnsNeeded, locate, parse_date, read_tables, to_decimal

SHRAWAN_1 = dt.date(2026, 7, 17)  # 2083.04.01 BS


@pytest.mark.parametrize(
    "value",
    [
        "2083.04.01",
        "2083-4-1",
        "2083/04/01 BS",
        "२०८३.०४.०१",
        "01/04/2083",
        "1 Shrawan 2083",
        "Saun 1, 2083",
        "१ साउन २०८३",
        "2026-07-17",
        "17/07/2026",
        "17 Jul 2026",
        "July 17, 2026",
        "2026-07-17 00:00:00",
        dt.date(2026, 7, 17),
        dt.datetime(2083, 4, 1),  # Excel turned the typed BS date into an AD date
        (SHRAWAN_1 - dt.date(1899, 12, 30)).days,  # an Excel date stored as a number
    ],
)
def test_dates_in_many_forms(value):
    assert parse_date(value) == SHRAWAN_1


@pytest.mark.parametrize("value", ["2083.13.40", "next week", "1 Shrawan 2026"])
def test_bad_dates_are_explained(value):
    with pytest.raises(ValueError, match="Date"):
        parse_date(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Rs. 1,20,000/-", "120000"),
        ("2 pcs", "2"),
        ("१२००", "1200"),
        ("(500)", "-500"),
        ("-", "0"),
        ("35/sqft", "35"),
        ("@ 35", "35"),
        ("NPR 450.50", "450.50"),
        (12.5, "12.5"),
        (None, "0"),
    ],
)
def test_numbers_in_many_forms(value, expected):
    assert to_decimal(value, "Amount") == D(expected)


def test_text_that_is_not_a_number_is_explained():
    with pytest.raises(ValueError, match="Rate must be a number, not 'ask'"):
        to_decimal("ask", "Rate")


@pytest.mark.parametrize(
    ("header", "field"),
    [
        ("Rate (Rs.)", "rate"),
        ("Customer's Name", "customer"),
        ("Party Name", "customer"),
        ("Qty.", "quantity"),
        ("मिति", "date"),
        ("Payment S", "paid"),
        ("Payment Status", "paid"),
        ("Payment M", "mode"),
        ("Paid Amount", "paid"),
        ("Total Sq. Ft.", "sqft"),
        ("Rate per sq ft", "rate"),
        ("Dues", "balance"),
        ("Height in ft", "height"),
        ("Item Name", "item"),
        ("Work Details", "details"),
        ("Mob. No.", "phone"),
        ("Size", "size"),
        ("S.N.", None),
        ("Bill No", None),
    ],
)
def test_header_names_people_use(header, field):
    assert work_log.COLUMNS.field_for(header) == field


def _xlsx(sheets: dict[str, list[list]], hidden: tuple[str, ...] = ()) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
        if name in hidden:
            ws.sheet_state = "hidden"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_every_visible_sheet_is_read():
    content = _xlsx({"Shrawan": [["a"]], "Bhadra": [["b"]], "Calc": [["c"]]}, hidden=("Calc",))
    assert [t.name for t in read_tables(content, "log.xlsx")] == ["Shrawan", "Bhadra"]


@pytest.mark.parametrize(
    "content",
    [
        b"Date;Particular;Items\n2083.04.01;Ram;Banner\n",
        b"Date\tParticular\tItems\n2083.04.01\tRam\tBanner\n",
        "Date,Particular,Items\n2083.04.01,Ram,Banner\n".encode("utf-16"),
        b"Date|Particular|Items\n2083.04.01|Ram|Banner\n",
    ],
)
def test_text_files_with_any_separator_or_encoding(content):
    rows = read_tables(content, "log.csv")[0].rows
    assert rows[1] == ("2083.04.01", "Ram", "Banner")


def test_a_web_page_saved_as_xls():
    page = (
        b"<html><body><table><tr><th>Date</th><th>Particular</th><th>Items</th></tr>"
        b"<tr><td>2083.04.01</td><td>Ram  Sharma</td><td>Banner</td></tr></table></body></html>"
    )
    rows = read_tables(page, "export.xls")[0].rows
    assert rows == [("Date", "Particular", "Items"), ("2083.04.01", "Ram Sharma", "Banner")]


def _ods(rows: list[list]) -> bytes:
    ns = (
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
    )
    body = []
    for row in rows:
        cells = []
        for value in row:
            if isinstance(value, int | float):
                cells.append(
                    f'<table:table-cell office:value-type="float" office:value="{value}">'
                    f"<text:p>{value}</text:p></table:table-cell>"
                )
            else:
                cells.append(f"<table:table-cell><text:p>{value}</text:p></table:table-cell>")
        body.append(f"<table:table-row>{''.join(cells)}</table:table-row>")
    body.append(
        '<table:table-row table:number-rows-repeated="1048000"><table:table-cell/>'
        "</table:table-row>"
    )
    xml = (
        f'<?xml version="1.0"?><office:document-content {ns}><office:body><office:spreadsheet>'
        f'<table:table table:name="Log">{"".join(body)}</table:table>'
        "</office:spreadsheet></office:body></office:document-content>"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        archive.writestr("content.xml", xml)
    return out.getvalue()


def test_libreoffice_and_google_sheets_ods():
    tables = read_tables(
        _ods([["Date", "Particular", "Amount"], ["2083.04.01", "Ram", 500]]), "log.ods"
    )
    assert tables[0].name == "Log"
    assert tables[0].rows[:2] == [("Date", "Particular", "Amount"), ("2083.04.01", "Ram", 500.0)]
    assert len(tables[0].rows) == 3  # the huge run of empty rows is cut short


@pytest.mark.parametrize(
    ("content", "name", "message"),
    [
        (b"", "log.xlsx", "empty"),
        (b"just some notes", "log.xlsx", "not a spreadsheet"),
        (b"PK\x03\x04broken", "log.xlsx", "damaged"),
    ],
)
def test_unreadable_files_are_explained(content, name, message):
    with pytest.raises(ValueError, match=message):
        read_tables(content, name)


def test_a_header_over_two_rows():
    content = _xlsx(
        {
            "Log": [
                ["Date", "Particular", "Size", None, "Amount"],
                [None, None, "Height", "Width", None],
                ["2083.04.01", "Ram", 3, 4, 360],
            ]
        }
    )
    [found] = locate(read_tables(content, "log.xlsx"), work_log.COLUMNS)
    assert found.header_index == 1
    assert sorted(found.mapping.values()) == ["amount", "customer", "date", "height", "width"]


def test_unknown_headers_ask_for_columns_with_the_best_guess():
    content = _xlsx({"Log": [["My shop"], ["When", "Who", "What", "Money"], ["x", "y", "z", 1]]})
    with pytest.raises(ColumnsNeeded) as caught:
        locate(read_tables(content, "log.xlsx"), work_log.COLUMNS)
    assert caught.value.headers == ["When", "Who", "What", "Money"]
    overrides = {"when": "date", "who": "customer", "what": "item", "money": "amount"}
    [found] = locate(read_tables(content, "log.xlsx"), work_log.COLUMNS, overrides)
    assert found.mapping == {0: "date", 1: "customer", 2: "item", 3: "amount"}
