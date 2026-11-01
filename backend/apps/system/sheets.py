"""Forgiving spreadsheet reading, shared by every import.

Shops keep their sheets in many slightly different ways, so the readers here
accept what people actually type instead of one exact layout:

* files: Excel .xlsx, .xlsm, .xltx, .xltm, .xlsb and old .xls, LibreOffice /
  Google Sheets .ods, web-page tables saved as .xls, and CSV / TSV text
  (comma, semicolon, tab or bar; UTF-8, UTF-16 or Windows encodings). The
  type is read from the file's contents, not its name, and every visible
  sheet of a workbook is read, so one sheet per month works;
* headers: anywhere in the first 30 rows, over one or two rows, in any order
  and spelling ("Rate (Rs.)", "Customer's Name", "Qty.", "मिति"), and the
  person importing can say which column is which when a guess is wrong;
* numbers: "Rs. 1,20,000/-", "2 pcs", "१२००", "(500)";
* dates: BS or AD, as text (2083.04.01, 01/04/2083, 1 Shrawan 2083,
  31 Oct 2026, Nepali digits) or as Excel date cells, including the BS
  dates Excel mistakes for AD dates in the year 2083.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import fromstring as parse_xml
from openpyxl import load_workbook

from apps.core.dates import from_bs
from apps.core.money import ZERO

HEADER_SEARCH_ROWS = 30
FILE_TYPES = (
    ".xlsx",
    ".xlsm",
    ".xltx",
    ".xltm",
    ".xlsb",
    ".xls",
    ".ods",
    ".csv",
    ".tsv",
    ".txt",
)
MAX_ROWS = 100_000
MAX_UNPACKED_BYTES = 200 * 1024 * 1024

# ---------- text ----------

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def digits(text: str) -> str:
    """Nepali (Devanagari) digits as 0-9."""
    return text.translate(_DEVANAGARI_DIGITS)


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return re.sub(r"\s+", " ", str(value)).strip()


# Words that only describe a header's unit or currency: "Rate (Rs.)", "Height in ft".
_HEADER_NOISE = {"rs", "npr", "nrs", "in", "ft", "feet", "inch", "of", "the", "s", "रु"}


def header_key(value: Any) -> str:
    """A header reduced to plain words: "Customer's Name:" -> "customer name"."""
    text = digits(str(value or "")).lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", text)
    text = re.sub(r"[^0-9a-zऀ-ॿ]+", " ", text)
    text = re.sub(r"\bsq (?:ft|feet|foot)\b", "sqft", text)  # before "ft" is dropped as a unit
    return " ".join(w for w in text.split() if w not in _HEADER_NOISE)


# ---------- files ----------


@dataclass
class Table:
    name: str
    rows: list[tuple[Any, ...]]


def _csv_rows(content: bytes) -> list[tuple[Any, ...]]:
    text = _decode(content)
    try:
        delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    return [tuple(r) for r in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _xls_tables(content: bytes) -> list[Table]:
    import xlrd

    try:
        book = xlrd.open_workbook(file_contents=content)
    except Exception as exc:  # xlrd raises its own error types for bad files
        raise ValueError("This is not a readable Excel (.xls) file.") from exc
    tables = []
    for sheet in book.sheets():
        if sheet.visibility:  # hidden sheets often hold calculations
            continue
        rows = []
        for r in range(sheet.nrows):
            row = []
            for cell in sheet.row(r):
                if cell.ctype == xlrd.XL_CELL_DATE:
                    row.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
                else:
                    row.append(cell.value)
            rows.append(tuple(row))
        tables.append(Table(sheet.name, rows))
    return tables


def _xlsx_tables(content: bytes) -> list[Table]:
    try:
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises several unrelated types for bad files
        raise ValueError("This Excel file could not be read; open it and save it again.") from exc
    return [
        Table(ws.title, [tuple(r) for r in ws.iter_rows(values_only=True)][:MAX_ROWS])
        for ws in book.worksheets
        if getattr(ws, "sheet_state", "visible") == "visible"
    ]


def _xlsb_tables(content: bytes) -> list[Table]:
    from pyxlsb import open_workbook

    tables = []
    with open_workbook(io.BytesIO(content)) as book:
        for name in book.sheets:
            with book.get_sheet(name) as sheet:
                rows = [tuple(cell.v for cell in row) for row in sheet.rows()]
            tables.append(Table(name, rows[:MAX_ROWS]))
    return tables  # dates arrive as Excel day numbers; parse_date reads those


_ODS_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_ODS_OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
_ODS_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


def _ods_cell(cell: Element) -> Any:
    kind = cell.get(f"{_ODS_OFFICE}value-type")
    if kind in ("float", "currency", "percentage"):
        return float(cell.get(f"{_ODS_OFFICE}value") or 0)
    if kind == "date":
        return dt.date.fromisoformat((cell.get(f"{_ODS_OFFICE}date-value") or "")[:10])
    text = "\n".join("".join(p.itertext()) for p in cell.iter(f"{_ODS_TEXT}p"))
    return text or None


def _ods_tables(archive: zipfile.ZipFile) -> list[Table]:
    if archive.getinfo("content.xml").file_size > MAX_UNPACKED_BYTES:
        raise ValueError("This spreadsheet is too large to import; split it into smaller files.")
    root = parse_xml(archive.read("content.xml"))
    tables = []
    for table in root.iter(f"{_ODS_TABLE}table"):
        rows: list[tuple[Any, ...]] = []
        for row in table.iter(f"{_ODS_TABLE}table-row"):
            cells: list[Any] = []
            for cell in row:
                repeat = int(cell.get(f"{_ODS_TABLE}number-columns-repeated") or 1)
                cells.extend([_ods_cell(cell)] * min(repeat, 256))
            while cells and cells[-1] in (None, ""):
                cells.pop()
            # Empty rows are often stored as "repeat 1,048,000 times" at the end.
            repeat = int(row.get(f"{_ODS_TABLE}number-rows-repeated") or 1)
            rows.extend([tuple(cells)] * (min(repeat, 1000) if cells else min(repeat, 1)))
            if len(rows) >= MAX_ROWS:
                break
        tables.append(Table(table.get(f"{_ODS_TABLE}name") or "", rows))
    return tables


class _HtmlTables(HTMLParser):
    """Tables in a web page; some programs export these and call them .xls."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[Table] = []
        self._rows: list[tuple[Any, ...]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "table":
            self._rows = []
        elif tag == "tr" and self._rows is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._rows is not None and self._row is not None:
            self._rows.append(tuple(self._row))
            self._row = None
        elif tag == "table" and self._rows is not None:
            self.tables.append(Table(f"Table {len(self.tables) + 1}", self._rows))
            self._rows = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")  # pragma: no cover


def read_tables(content: bytes, name: str) -> list[Table]:
    """Every visible sheet of the file, as rows of cell values."""
    if not content.strip():
        raise ValueError("The file is empty.")
    if content[:4] == b"PK\x03\x04":  # a zip: xlsx, xlsm, xltx, xlsb or ods
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
                if "content.xml" in names and "mimetype" in names:
                    return _ods_tables(archive)
                if "xl/workbook.bin" in names:
                    return _xlsb_tables(content)
        except zipfile.BadZipFile as exc:
            raise ValueError("The file is damaged; open it and save it again.") from exc
        return _xlsx_tables(content)
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":  # old Excel (or a locked file)
        try:
            return _xls_tables(content)
        except ValueError as exc:
            raise ValueError(
                "This old-style Excel file could not be read. If it has a password, "
                "remove it; otherwise save it as .xlsx and upload again."
            ) from exc
    text = _decode(content)
    if re.search(r"(?is)<table\b", text[:200_000]):
        parser = _HtmlTables()
        parser.feed(text)
        if parser.tables:
            return parser.tables
    if Path(name).suffix.lower() in (".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"):
        raise ValueError("This file is not a spreadsheet, though its name says so.")
    return [Table("", _csv_rows(content)[:MAX_ROWS])]


# ---------- values ----------

_NUMBER_NOISE = re.compile(
    r"(?i)\b(?:rs|npr|nrs)\b\.?|रु\.?|/-|"
    r"\b(?:sq\.?\s*ft|sqft|sft|ft|feet|pcs|pc|nos|piece|pieces|ltr|litre|box)\b\.?|['\"]"
)
_BLANK_NUMBERS = {"", "-", "--", "nil", "na", "n/a", "none"}


def to_decimal(value: Any, label: str) -> Decimal:
    """A number from a cell, ignoring currency, units and thousands separators."""
    if value is None or value == "":
        return ZERO
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number, not '{value}'.")
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value))
    text = _NUMBER_NOISE.sub("", digits(str(value))).replace(",", "").replace(" ", "")
    text = re.sub(r"(?i)^@|/(?:per)?$|^per", "", text)  # "@35", "35/" left from "35/sqft"
    if text.lower() in _BLANK_NUMBERS:
        return ZERO
    negative = text.startswith("(") and text.endswith(")")
    try:
        number = Decimal(text.strip("()"))
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a number, not '{value}'.") from exc
    return -number if negative else number


def to_bool(value: Any, default: bool = True) -> bool:
    text = norm(value)
    if not text:
        return default
    return text in {"1", "yes", "y", "true", "active", "on", "हो", "छ"}


_BS_MONTHS = {
    1: ("baisakh", "baishakh", "vaishakh", "baisak", "बैशाख", "वैशाख"),
    2: ("jestha", "jeth", "jesth", "जेठ", "ज्येष्ठ"),
    3: ("asar", "asadh", "ashadh", "ashar", "असार", "आषाढ"),
    4: ("shrawan", "srawan", "saun", "sawan", "shravan", "श्रावण", "साउन"),
    5: ("bhadra", "bhadau", "bhadra", "भदौ", "भाद्र"),
    6: ("asoj", "ashwin", "aswin", "asauj", "असोज", "आश्विन"),
    7: ("kartik", "kattik", "कार्तिक", "कात्तिक"),
    8: ("mangsir", "mansir", "marga", "मंसिर", "मङ्सिर"),
    9: ("poush", "push", "pous", "paush", "पुष", "पौष", "पुस"),
    10: ("magh", "माघ"),
    11: ("falgun", "fagun", "phalgun", "फाल्गुन", "फागुन"),
    12: ("chaitra", "chait", "चैत", "चैत्र"),
}
_AD_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_YMD = re.compile(r"^(\d{4})\s*[.\-/ ]\s*(\d{1,2})\s*[.\-/ ]\s*(\d{1,2})$")
_DMY = re.compile(r"^(\d{1,2})\s*[.\-/ ]\s*(\d{1,2})\s*[.\-/ ]\s*(\d{4})$")
_EXCEL_EPOCH = dt.date(1899, 12, 30)


def _make_date(year: int, month: int, day: int, text: str) -> dt.date:
    try:
        if year >= 2050:  # Bikram Sambat (AD 2050 is far in the future)
            return from_bs(year, month, day)
        return dt.date(year, month, day)
    except (ValueError, OverflowError, KeyError, IndexError) as exc:
        raise ValueError(f"Date '{text}' does not exist.") from exc


def _month_of(word: str) -> tuple[int, str] | None:
    for number, names in _BS_MONTHS.items():
        if word in names:
            return number, "bs"
    if word[:3] in _AD_MONTHS and word.isascii():
        return _AD_MONTHS.index(word[:3]) + 1, "ad"
    return None


def parse_date(value: Any) -> dt.date:
    """A BS or AD date from a cell; see the module notes for the forms accepted."""
    if isinstance(value, dt.datetime):
        value = value.date()
    if isinstance(value, dt.date):
        # Excel reads a typed BS date such as 2083/04/01 as an AD date in 2083.
        return _make_date(value.year, value.month, value.day, str(value))
    if isinstance(value, int | float) and not isinstance(value, bool) and 20000 < value < 80000:
        return _EXCEL_EPOCH + dt.timedelta(days=int(value))  # an Excel date stored as a number
    text = digits(cell_text(value))
    clean = re.sub(r"\s+\d{1,2}:\d{2}(:\d{2})?\s*$", "", text)  # a time after the date
    clean = re.sub(r"(?i)\s*\b(b\.?\s*s|a\.?\s*d)\b\.?\s*$", "", clean).strip(" ,")
    if match := _YMD.match(clean):
        year, month, day = (int(p) for p in match.groups())
        return _make_date(year, month, day, text)
    if match := _DMY.match(clean):
        day, month, year = (int(p) for p in match.groups())
        return _make_date(year, month, day, text)
    words = re.findall(r"[a-zऀ-ॿ]+|\d+", clean.lower())
    numbers = [int(w) for w in words if w.isdigit()]
    months = [m for w in words if not w.isdigit() and (m := _month_of(w))]
    years = [n for n in numbers if n >= 1900]
    days = [n for n in numbers if n < 1900]
    if len(months) == 1 and len(years) == 1 and len(days) == 1:
        (month, calendar), year, day = months[0], years[0], days[0]
        if calendar == "bs" and year < 2050:
            raise ValueError(f"Date '{text}' mixes a BS month with an AD year.")
        return _make_date(year, month, day, text)
    raise ValueError(
        f"Date '{text}' is not a date we can read; use 2083.04.01 (BS) or 2026-07-17 (AD)."
    )


# ---------- columns ----------


@dataclass(frozen=True)
class Column:
    field: str
    label: str
    exact: tuple[str, ...] = ()
    words: tuple[str, ...] = ()


@dataclass
class Columns:
    """The fields an import understands, with the header names that mean each.

    Exact names are tried first, then the first column whose header contains
    one of the field's words, in the order given (so put "total sqft" style
    fields before "total" style ones).
    """

    fields: list[Column]
    required: tuple[str, ...]
    any_of: tuple[str, ...] = ()
    special: Callable[[str], str | None] | None = None
    ignored: frozenset[str] = frozenset(
        {"sn", "s n", "sno", "s no", "sl", "sl no", "serial", "serial no", "क्र सं", "क्रसं"}
    )

    def labels(self) -> dict[str, str]:
        return {c.field: c.label for c in self.fields}

    def field_for(self, header: Any, overrides: dict[str, str] | None = None) -> str | None:
        key = header_key(header)
        if not key or key in self.ignored:
            return None
        if overrides and key in overrides:
            return overrides[key] or None
        if self.special and (found := self.special(key)):
            return found
        for column in self.fields:
            if key in column.exact:
                return column.field
        for column in self.fields:
            if any(word in key for word in column.words):
                return column.field
        return None

    def complete(self, found: set[str]) -> bool:
        has_any = not self.any_of or bool(found & set(self.any_of))
        return all(f in found for f in self.required) and has_any

    def describe(self) -> str:
        labels = self.labels()
        need = [labels[f] for f in self.required]
        if self.any_of:
            need.append(" or ".join(labels[f] for f in self.any_of))
        return ", ".join(need)


@dataclass
class Message:
    row: int
    message: str
    sheet: str = ""


@dataclass
class Located:
    """One sheet's header: where it is and which column holds which field."""

    table: Table
    header_index: int  # index of the last header row
    mapping: dict[int, str]  # column -> field
    headers: dict[int, str]  # column -> header text


class ColumnsNeeded(ValueError):
    """No header was recognised; ``headers`` is the best guess to map by hand."""

    def __init__(self, message: str, headers: list[str]):
        super().__init__(message)
        self.headers = headers


def _map(
    texts: dict[int, str], columns: Columns, overrides: dict[str, str] | None
) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for col, text in texts.items():
        name = columns.field_for(text, overrides)
        if name and name not in mapping.values():
            mapping[col] = name
    return mapping


def _texts(row: tuple[Any, ...]) -> dict[int, str]:
    return {c: cell_text(v) for c, v in enumerate(row) if cell_text(v)}


def _locate_in(table: Table, columns: Columns, overrides: dict[str, str] | None) -> Located | None:
    rows = table.rows
    for i in range(min(HEADER_SEARCH_ROWS, len(rows))):
        texts = _texts(rows[i])
        mapping = _map(texts, columns, overrides)
        best = Located(table, i, mapping, texts)
        if i + 1 < len(rows):
            # Two header rows, e.g. "Size" over "Height | Width": the lower row wins.
            combined = {**texts, **_texts(rows[i + 1])}
            two_rows = _map(combined, columns, overrides)
            if columns.complete(set(two_rows.values())) and len(two_rows) > len(mapping):
                best = Located(table, i + 1, two_rows, combined)
        if columns.complete(set(best.mapping.values())):
            return best
    return None


def _best_guess(tables: list[Table]) -> list[str]:
    """The row that looks most like a header, for mapping columns by hand."""
    best: list[str] = []
    for table in tables:
        for row in table.rows[:HEADER_SEARCH_ROWS]:
            words = [
                cell_text(v)
                for v in row
                if isinstance(v, str) and cell_text(v) and not to_number_like(v)
            ]
            if len(words) > len(best):
                best = words
    return list(dict.fromkeys(best))


def to_number_like(value: Any) -> bool:
    try:
        to_decimal(value, "")
    except ValueError:
        return False
    return True


def locate(
    tables: list[Table], columns: Columns, overrides: dict[str, str] | None = None
) -> list[Located]:
    """The header of every sheet that holds this kind of data."""
    found = [loc for t in tables if (loc := _locate_in(t, columns, overrides))]
    if not found:
        raise ColumnsNeeded(
            f"Could not tell which column is which. The sheet needs at least: "
            f"{columns.describe()}. Choose the columns below.",
            _best_guess(tables),
        )
    return found


def records(located: Located, columns: Columns) -> Iterator[tuple[int, dict[str, Any]]]:
    """``(row number, {field: value})`` for each non-blank row below the header.

    Rows that repeat the header (sheets printed with a header on every page)
    are left out.
    """
    header_keys = {header_key(located.headers[c]) for c in located.mapping}
    for number, values in enumerate(
        located.table.rows[located.header_index + 1 :], start=located.header_index + 2
    ):
        cells = {f: values[c] if c < len(values) else None for c, f in located.mapping.items()}
        texts = [cell_text(v) for v in cells.values()]
        if not any(texts):
            continue
        if sum(header_key(t) in header_keys for t in texts if t) >= 2:
            continue
        yield number, cells


@dataclass
class SheetInfo:
    """What the reader understood, shown to the person importing."""

    sheets: list[str] = field(default_factory=list)
    header_row: int = 1
    columns: dict[str, str] = field(default_factory=dict)  # field -> header text
    headers: list[str] = field(default_factory=list)  # every header of the first sheet
    needs_columns: bool = False


def describe(located: list[Located]) -> SheetInfo:
    first = located[0]
    return SheetInfo(
        sheets=[loc.table.name for loc in located if loc.table.name],
        header_row=first.header_index + 1,
        columns={f: first.headers[c] for c, f in first.mapping.items()},
        headers=list(dict.fromkeys(first.headers.values())),
    )
