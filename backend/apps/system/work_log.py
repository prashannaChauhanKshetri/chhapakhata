"""Import and export the shop's Excel work log.

Before ChhapaKhata the shop kept one sheet row per job::

    Date | Particular | Address | Items | Height | Width | Qty | SQFT | Rate | Amount |
    Details | Payment | Payment Mode | Discount | Balance

Importing turns those rows into delivered orders so customer balances, order
history and each customer's last rates carry over:

* rows with the same date and customer become one order (``source = import``);
* each order is charged to the customer ledger as "Work (imported)", without an
  invoice, so no invoice numbers are used;
* the Payment column becomes a receipt dated that day;
* unknown customers and items are created (items keep the sheet's rate).

Every row gets a fingerprint, so uploading the same sheet again (or a longer
version of it) only adds rows that are new. Rows exported from ChhapaKhata carry
their order number and are always skipped.

Export writes orders in the same layout, so the shop can keep using Excel.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, BinaryIO

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from apps.billing.models import (
    LedgerEntry,
    LedgerEntryType,
    Payment,
    PaymentMode,
    PaymentStatus,
    Wallet,
)
from apps.catalog.models import MediaType, PricingUnit
from apps.core.activity import log_activity
from apps.core.dates import bs_string, local_today
from apps.core.money import ZERO, fmt_qty, q2
from apps.core.sequences import DocType, next_number
from apps.customers.models import Customer
from apps.orders.models import (
    DiscountType,
    Order,
    OrderItem,
    OrderSource,
    OrderStatus,
    RateSource,
)
from apps.system import sheets
from apps.system.sheets import Column, Columns, Message

MAX_MESSAGES = 300
TOLERANCE = Decimal("1.00")  # rupees of rounding allowed between columns


def _payment_column(key: str) -> str | None:
    # "Payment Mode", "Payment Method", "Payment Type" (or a narrow column showing
    # just "Payment M") name the mode; any other payment column is the amount paid.
    first = key.split()[0]
    if first in ("payment", "paid", "received", "advance", "receipt", "भुक्तानी"):
        rest = key[len(first) :].strip()
        return "mode" if rest.startswith(("m", "type", "via")) else "paid"
    return None


COLUMNS = Columns(
    fields=[
        Column("order_no", "Order no.", ("order no", "order number"), ("order no", "order id")),
        Column("date", "Date", ("date", "miti", "date bs", "bs date"), ("date", "miti", "मिति")),
        Column("mode", "Payment mode", ("mode", "pay mode"), ("mode", "method")),
        Column("paid", "Payment", (), ("paid", "received", "receipt", "भुक्तानी", "प्राप्त")),
        Column(
            "balance",
            "Balance",
            ("balance", "due", "remaining", "balance due"),
            ("balance", "due", "remaining", "baki", "बाँकी", "बाकी"),
        ),
        Column("discount", "Discount", ("discount", "disc"), ("discount", "छुट")),
        Column("vat", "VAT", ("vat", "vat amount"), ("vat", "भ्याट")),
        Column("rate", "Rate", ("rate", "price"), ("rate", "price", "दर", "मूल्य")),
        Column(
            "sqft",
            "Sq ft",
            ("sqft", "sq ft", "sq", "area", "total sqft"),
            ("sqft", "sq ft", "sq feet", "square", "area", "वर्ग"),
        ),
        Column("size", "Size", ("size",), ("size", "dimension", "साइज")),
        Column(
            "height",
            "Height",
            ("height", "h", "length"),
            ("height", "length", "lambai", "लम्बाइ", "लम्बाई", "उचाइ"),
        ),
        Column("width", "Width", ("width", "w", "breadth"), ("width", "breadth", "चौडाइ", "चौडाई")),
        Column(
            "quantity",
            "Qty",
            ("qty", "quantity", "pcs", "nos"),
            ("qty", "quantity", "pcs", "piece", "nos", "संख्या", "परिमाण", "थान"),
        ),
        Column("unit", "Unit", ("unit",)),
        Column(
            "amount",
            "Amount",
            ("amount", "total", "total amount"),
            ("amount", "total", "रकम", "जम्मा", "कुल", "value"),
        ),
        Column(
            "phone",
            "Phone",
            ("phone", "mobile", "contact", "phone no", "mobile no"),
            ("phone", "mobile", "contact", "mob", "cell", "फोन", "मोबाइल"),
        ),
        Column(
            "address",
            "Address",
            ("address", "place", "location"),
            ("address", "place", "location", "city", "ठेगाना"),
        ),
        Column(
            "details",
            "Details",
            ("details", "detail", "description", "remarks", "remark", "particular details"),
            ("detail", "description", "remark", "note", "विवरण", "कैफियत"),
        ),
        Column(
            "item",
            "Items",
            ("items", "item", "work", "media", "material", "product"),
            ("item", "media", "material", "product", "work", "job", "print", "सामान", "काम"),
        ),
        Column(
            "customer",
            "Particular (customer)",
            ("particular", "particulars", "customer", "customer name", "party", "name"),
            ("customer", "party", "client", "name", "particular", "नाम", "ग्राहक"),
        ),
    ],
    required=("date", "customer"),
    any_of=("item", "amount"),
    special=_payment_column,
)

_TOTAL_LINES = {"total", "grand total", "sub total", "subtotal", "जम्मा", "कुल", "कुल जम्मा"}


def _is_total_line(text: str) -> bool:
    key = sheets.header_key(text)
    return key in _TOTAL_LINES or key.startswith(("total ", "grand total"))


# ---------- reading ----------


@dataclass
class SheetRow:
    row: int
    date: dt.date
    customer: str
    address: str
    phone: str
    item: str
    width: Decimal
    height: Decimal
    unit: str
    quantity: int
    pricing_unit: str
    sqft_per_piece: Decimal
    rate: Decimal
    amount: Decimal
    details: str
    paid: Decimal
    mode: str
    wallet: str
    discount: Decimal
    vat: Decimal
    sheet: str = ""
    fingerprint: str = ""


@dataclass
class ParsedSheet:
    info: sheets.SheetInfo = field(default_factory=sheets.SheetInfo)
    rows: list[SheetRow] = field(default_factory=list)
    errors: list[Message] = field(default_factory=list)
    warnings: list[Message] = field(default_factory=list)
    rows_read: int = 0
    already_in_system: int = 0


_cell_text = sheets.cell_text
_norm = sheets.norm
parse_date = sheets.parse_date


def _decimal(value: Any, label: str) -> Decimal:
    return sheets.to_decimal(value, label)


_WALLETS = {
    "esewa": Wallet.ESEWA,
    "e-sewa": Wallet.ESEWA,
    "e sewa": Wallet.ESEWA,
    "khalti": Wallet.KHALTI,
    "fonepay": Wallet.FONEPAY,
    "fone pay": Wallet.FONEPAY,
    "ime": Wallet.OTHER_QR,
    "prabhu": Wallet.OTHER_QR,
    "qr": Wallet.OTHER_QR,
    "wallet": Wallet.OTHER_QR,
}


def parse_mode(value: Any) -> tuple[str, str]:
    """Map a free-text payment mode to (mode, wallet). Blank means cash."""
    text = _norm(value)
    if not text or text in ("cash", "nagad", "nagat", "नगद"):
        return PaymentMode.CASH, ""
    for key, wallet in _WALLETS.items():
        if key in text:
            return PaymentMode.WALLET, wallet
    if "cheque" in text or "check" in text or "chq" in text or "चेक" in text:
        return PaymentMode.CHEQUE, ""
    if any(w in text for w in ("bank", "transfer", "online", "ips", "card", "pos", "बैंक")):
        return PaymentMode.BANK, ""
    raise ValueError(f"Payment mode '{value}' is not known. Use Cash, Bank, Cheque or a wallet.")


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def _fingerprint(row: SheetRow, occurrence: int) -> str:
    parts = [
        row.date.isoformat(),
        _norm(row.customer),
        _norm(row.item),
        fmt_qty(row.width),
        fmt_qty(row.height),
        str(row.quantity),
        fmt_qty(row.rate),
        fmt_qty(row.amount),
        _norm(row.details),
        str(occurrence),
    ]
    return hashlib.sha1("|".join(parts).encode(), usedforsecurity=False).hexdigest()


def read_sheet(content: bytes, name: str, columns: dict[str, str] | None = None) -> ParsedSheet:
    """Parse and check every row. Nothing is written to the database.

    ``columns`` maps header text to a field ("" to leave a column out) where the
    automatic guess was wrong. Raises ``sheets.ColumnsNeeded`` when no header
    can be found.
    """
    located = sheets.locate(sheets.read_tables(content, name), COLUMNS, columns)
    sheet = ParsedSheet(info=sheets.describe(located))
    existing_orders = set(Order.objects.values_list("order_no", flat=True))
    several = len(located) > 1
    for loc in located:
        label = loc.table.name if several else ""
        last: SheetRow | None = None
        for number, cells in sheets.records(loc, COLUMNS):
            sheet.rows_read += 1
            if _cell_text(cells.get("order_no")) in existing_orders:
                sheet.already_in_system += 1
                continue
            try:
                row = _parse_row(number, cells, last, sheet.warnings, label)
            except ValueError as exc:
                sheet.errors.append(Message(number, str(exc), label))
                continue
            if row is None:
                sheet.rows_read -= 1  # a totals or note line, not work
                continue
            last = row
            sheet.rows.append(row)

    seen: Counter[str] = Counter()
    for row in sheet.rows:
        base = _fingerprint(row, 0)
        row.fingerprint = _fingerprint(row, seen[base]) if seen[base] else base
        seen[base] += 1
    return sheet


_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*['\"]?\s*(?:x|×|\*|by)\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_LENGTH_UNITS = {
    "ft": "ft",
    "feet": "ft",
    "foot": "ft",
    "'": "ft",
    "in": "in",
    "inch": "in",
    "inches": "in",
    '"': "in",
    "cm": "cm",
}
# A Unit column sometimes names the selling unit instead of the size unit.
_SELLING_UNITS = {"sqft", "sq ft", "sft", "pcs", "pc", "piece", "pieces", "nos", "no", "set"}


def _size(text: str) -> tuple[Decimal, Decimal, str] | None:
    match = _SIZE.search(sheets.digits(text))
    if not match:
        return None
    lowered = text.lower()
    unit = "in" if ("inch" in lowered or '"' in text) else "cm" if "cm" in lowered else "ft"
    return Decimal(match.group(1)), Decimal(match.group(2)), unit


def _parse_row(
    number: int,
    cells: dict[str, Any],
    last: SheetRow | None,
    warnings: list[Message],
    sheet: str = "",
) -> SheetRow | None:
    def note(text: str) -> None:
        warnings.append(Message(number, text, sheet))

    customer = _cell_text(cells.get("customer"))
    item = _cell_text(cells.get("item"))
    details = _cell_text(cells.get("details"))
    if _is_total_line(customer) or _is_total_line(_cell_text(cells.get("date"))):
        return None
    amount = q2(_decimal(cells.get("amount"), "Amount"))
    if not customer and not item and not amount:
        return None  # a note or blank line

    if _cell_text(cells.get("date")):
        date = parse_date(cells.get("date"))
    elif last is not None:
        date = last.date
        note("No date; used the date from the row above.")
    else:
        raise ValueError("Date is empty.")
    if date > local_today():
        raise ValueError(f"Date {bs_string(date)} BS is in the future.")

    if not customer:
        if last is None or last.date != date:
            raise ValueError("Particular (customer name) is empty.")
        customer = last.customer  # merged cells: one name over several rows
        note(f"No customer; used {customer} from the row above.")
    if len(customer) > 150:
        raise ValueError("Particular is longer than 150 characters.")
    if not item:
        if details:
            item = details
            note(f"No item; used the details '{details[:40]}' as the item.")
        elif amount:
            item = "Printing work"
            note("No item; recorded as 'Printing work'.")
        else:
            raise ValueError("Items is empty; write what was made (e.g. Banner).")

    height = _decimal(cells.get("height"), "Height")
    width = _decimal(cells.get("width"), "Width")
    unit = _norm(cells.get("unit")).strip(".")
    if not (height or width) and (size := _size(_cell_text(cells.get("size")))):
        width, height, size_unit = size
        unit = unit or size_unit
    if height < 0 or width < 0:
        raise ValueError("Height and width cannot be negative.")
    quantity_raw = _decimal(cells.get("quantity"), "Qty") or Decimal("1")
    if quantity_raw != quantity_raw.to_integral_value() or quantity_raw < 1:
        raise ValueError(f"Qty must be a whole number of pieces, not {fmt_qty(quantity_raw)}.")
    quantity = int(quantity_raw)
    if not unit or unit in _SELLING_UNITS:
        unit = "ft"
    elif unit in _LENGTH_UNITS:
        unit = _LENGTH_UNITS[unit]
    else:
        note(f"Unit '{unit}' is not known; the size is read as feet.")
        unit = "ft"
    divisor = {"ft": Decimal("1"), "in": Decimal("144"), "cm": Decimal("929.0304")}[unit]
    sized = height > 0 and width > 0
    sqft_total = q2(_decimal(cells.get("sqft"), "SQFT"))
    if sqft_total <= 0 and sized:
        sqft_total = q2(height * width / divisor * quantity)
    rate = q2(_decimal(cells.get("rate"), "Rate"))
    if rate < 0 or amount < 0:
        raise ValueError("Rate and amount cannot be negative.")

    # Decide how the row was priced: by area, or per piece.
    if sqft_total > 0 and (not amount or not rate or _close(sqft_total * rate, amount)):
        pricing_unit = PricingUnit.SQFT
        if not rate and amount:
            rate = q2(amount / sqft_total)
        if not amount:
            amount = q2(sqft_total * rate)
    else:
        pricing_unit = PricingUnit.PIECE
        if not rate and amount:
            rate = q2(amount / quantity)
        if not amount:
            amount = q2(rate * quantity)
        if sqft_total > 0 and not _close(rate * quantity, amount):
            pricing_unit = PricingUnit.SQFT
            note(
                f"Amount {fmt_qty(amount)} is neither SQFT × Rate "
                f"({fmt_qty(q2(sqft_total * rate))}) nor Qty × Rate "
                f"({fmt_qty(q2(rate * quantity))}); the sheet's amount is kept.",
            )
        elif not _close(rate * quantity, amount):
            note(
                f"Amount {fmt_qty(amount)} is not Qty × Rate "
                f"({fmt_qty(q2(rate * quantity))}); the sheet's amount is kept.",
            )

    paid = q2(_decimal(cells.get("paid"), "Payment"))
    discount = q2(_decimal(cells.get("discount"), "Discount"))
    vat = q2(_decimal(cells.get("vat"), "VAT"))
    if paid < 0 or discount < 0 or vat < 0:
        raise ValueError("Payment, discount and VAT cannot be negative.")
    if discount > amount:
        raise ValueError("Discount is more than the amount.")
    mode, wallet = PaymentMode.CASH, ""
    if paid > 0:
        try:
            mode, wallet = parse_mode(cells.get("mode"))
        except ValueError:
            note(f"Payment mode '{_cell_text(cells.get('mode'))}' is not known; recorded as cash.")
    if _cell_text(cells.get("balance")):
        balance = q2(_decimal(cells.get("balance"), "Balance"))
        expected = q2(amount - discount + vat - paid)
        if not _close(balance, expected):
            note(
                f"Balance {fmt_qty(balance)} does not match Amount − Discount − Payment "
                f"({fmt_qty(expected)}); the ledger uses {fmt_qty(expected)}.",
            )

    return SheetRow(
        row=number,
        date=date,
        customer=customer,
        address=_cell_text(cells.get("address"))[:255],
        phone=re.sub(r"[^\d+]", "", _cell_text(cells.get("phone")))[:20],
        item=item[:80],
        width=q2(width),
        height=q2(height),
        unit=unit,
        quantity=quantity,
        pricing_unit=pricing_unit,
        sqft_per_piece=q2(sqft_total / quantity) if sqft_total else ZERO,
        rate=rate,
        amount=amount,
        details=details[:200],
        paid=paid,
        mode=mode,
        wallet=wallet,
        discount=discount,
        vat=vat,
        sheet=sheet,
    )


# ---------- importing ----------


@dataclass
class ImportResult:
    dry_run: bool
    file_name: str
    header_row: int
    columns: dict[str, str]
    rows_read: int
    sheets: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    needs_columns: bool = False
    problem: str = ""
    rows_imported: int = 0
    rows_skipped_duplicate: int = 0
    rows_skipped_error: int = 0
    rows_already_in_system: int = 0
    orders: int = 0
    payments: int = 0
    new_customers: list[str] = field(default_factory=list)
    matched_customers: int = 0
    new_items: list[dict[str, Any]] = field(default_factory=list)
    totals: dict[str, Decimal] = field(default_factory=dict)
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    errors: list[Message] = field(default_factory=list)
    warnings: list[Message] = field(default_factory=list)

    @property
    def can_import(self) -> bool:
        return self.rows_imported > 0


class _Rollback(Exception):
    pass


def import_work_log(
    file: BinaryIO,
    *,
    name: str,
    user: Any,
    dry_run: bool = True,
    skip_errors: bool = False,
    columns: dict[str, str] | None = None,
    request: Any = None,
) -> ImportResult:
    """Import a work-log sheet. With ``dry_run`` everything is checked, then rolled back.

    Rows with errors stop the import unless ``skip_errors`` is set, in which
    case only the valid rows are imported. ``columns`` corrects the column
    guesses (header text -> field). When no header is recognised the result
    has ``needs_columns`` set, with the sheet's headers to choose from.
    """
    try:
        sheet = read_sheet(file.read(), name, columns)
    except sheets.ColumnsNeeded as exc:
        return ImportResult(
            dry_run=True,
            file_name=name,
            header_row=0,
            columns={},
            rows_read=0,
            headers=exc.headers,
            needs_columns=True,
            problem=str(exc),
            totals=dict.fromkeys(("amount", "discount", "vat", "paid", "balance"), ZERO),
        )
    result = ImportResult(
        dry_run=dry_run,
        file_name=name,
        header_row=sheet.info.header_row,
        columns=sheet.info.columns,
        rows_read=sheet.rows_read,
        sheets=sheet.info.sheets,
        headers=sheet.info.headers,
        rows_skipped_error=len({(e.sheet, e.row) for e in sheet.errors}),
        rows_already_in_system=sheet.already_in_system,
        errors=sheet.errors[:MAX_MESSAGES],
        warnings=sheet.warnings[:MAX_MESSAGES],
    )
    blocked = bool(sheet.errors) and not skip_errors
    try:
        with transaction.atomic():
            _write(sheet, result, user)
            if dry_run or blocked:
                raise _Rollback
            log_activity(
                user,
                "work_log.imported",
                None,
                message=f"{name}: {result.rows_imported} rows, {result.orders} orders",
                metadata={"file": name, "rows": result.rows_imported, "orders": result.orders},
                request=request,
            )
    except _Rollback:
        pass
    if blocked and not dry_run:
        result.dry_run = True  # nothing was saved
    return result


def _import_note(file_name: str, sheet: str, first: int, last: int) -> str:
    where = f"{file_name}, sheet {sheet}" if sheet else file_name
    rows = f"rows {first}–{last}" if first != last else f"row {first}"
    return f"Imported from {where}, {rows}."


def _customer_finder():
    by_name: dict[str, list[Customer]] = defaultdict(list)
    for customer in Customer.objects.order_by("id"):
        by_name[_norm(customer.name)].append(customer)
    return by_name


def _write(sheet: ParsedSheet, result: ImportResult, user: Any) -> None:
    imported = set(
        OrderItem.objects.filter(import_ref__in=[r.fingerprint for r in sheet.rows]).values_list(
            "import_ref", flat=True
        )
    )
    rows = [r for r in sheet.rows if r.fingerprint not in imported]
    result.rows_skipped_duplicate = len(sheet.rows) - len(rows)
    if not rows:
        result.totals = dict.fromkeys(("amount", "discount", "vat", "paid", "balance"), ZERO)
        return

    customers = _customer_finder()
    customer_ids: set[int] = set()
    media = {_norm(m.name): m for m in MediaType.objects.all()}
    created_media: dict[str, MediaType] = {}

    groups: dict[tuple[dt.date, str], list[SheetRow]] = defaultdict(list)
    for row in rows:
        groups[(row.date, _norm(row.customer))].append(row)

    def customer_for(row: SheetRow) -> Customer:
        matches = customers.get(_norm(row.customer), [])
        if len(matches) > 1 and row.address:
            same_place = [c for c in matches if _norm(c.address) == _norm(row.address)]
            matches = same_place or matches
        if matches:
            if matches[0].pk not in customer_ids and matches[0].name not in result.new_customers:
                result.matched_customers += 1
            customer_ids.add(matches[0].pk)
            return matches[0]
        customer = Customer.objects.create(
            name=row.customer, address=row.address, phone=row.phone, created_by=user
        )
        customers[_norm(row.customer)].append(customer)
        customer_ids.add(customer.pk)
        result.new_customers.append(customer.name)
        return customer

    def media_for(row: SheetRow) -> MediaType:
        key = _norm(row.item)
        if key in media:
            return media[key]
        created = MediaType.objects.create(
            name=row.item,
            pricing_unit=row.pricing_unit,
            rate=row.rate,
            description="Added by the work-log import; check the rate.",
            sort_order=900,
        )
        media[key] = created_media[key] = created
        result.new_items.append(
            {"name": created.name, "pricing_unit": created.pricing_unit, "rate": created.rate}
        )
        return created

    ledger: list[LedgerEntry] = []
    totals = dict.fromkeys(("amount", "discount", "vat", "paid", "balance"), ZERO)
    for (date, _), group in sorted(groups.items(), key=lambda g: (g[0][0], g[1][0].row)):
        customer = customer_for(group[0])
        subtotal = q2(sum((r.amount for r in group), ZERO))
        discount = q2(sum((r.discount for r in group), ZERO))
        vat = q2(sum((r.vat for r in group), ZERO))
        paid = q2(sum((r.paid for r in group), ZERO))
        total = q2(subtotal - discount + vat)
        moment = timezone.make_aware(dt.datetime.combine(date, dt.time(12, 0)))
        first, last = group[0].row, group[-1].row
        order = Order.objects.create(
            order_no=next_number(DocType.ORDER).number,
            customer=customer,
            status=OrderStatus.DELIVERED,
            order_date=date,
            source=OrderSource.IMPORT,
            notes=_import_note(result.file_name, group[0].sheet, first, last),
            discount_type=DiscountType.AMOUNT if discount else DiscountType.NONE,
            discount_value=discount,
            subtotal=subtotal,
            discount_amount=discount,
            taxable_amount=q2(subtotal - discount),
            vat_rate=ZERO,
            vat_amount=vat,
            total=total,
            created_by=user,
            confirmed_at=moment,
            delivered_at=moment,
        )
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                line_no=line_no,
                media_type=media_for(row),
                media_name=row.item,
                description=row.details,
                pricing_unit=row.pricing_unit,
                width=row.width,
                height=row.height,
                unit=row.unit,
                quantity=row.quantity,
                width_ft=q2(row.width / _feet(row.unit)),
                height_ft=q2(row.height / _feet(row.unit)),
                sqft=row.sqft_per_piece,
                billable_sqft=row.sqft_per_piece,
                rate=row.rate,
                rate_source=RateSource.CUSTOM,
                card_rate=None,
                min_sqft=ZERO,
                base_amount=row.amount,
                addons_amount=ZERO,
                line_total=row.amount,
                import_ref=row.fingerprint,
            )
            for line_no, row in enumerate(group, start=1)
        )
        items = ", ".join(dict.fromkeys(r.item for r in group))
        if total > 0:
            ledger.append(
                LedgerEntry(
                    customer=customer,
                    entry_date=date,
                    entry_type=LedgerEntryType.IMPORTED_WORK,
                    debit=total,
                    order=order,
                    narration=f"{order.order_no} · {items}"[:255],
                    created_by=user,
                )
            )
        by_mode: dict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
        for row in group:
            if row.paid > 0:
                by_mode[(row.mode, row.wallet)] += row.paid
        for (mode, wallet), amount in by_mode.items():
            allocated = next_number(DocType.RECEIPT, date)
            payment = Payment.objects.create(
                receipt_no=allocated.number,
                fiscal_year=allocated.fiscal_year,
                sequence=allocated.sequence,
                customer=customer,
                order=order,
                amount=q2(amount),
                mode=mode,
                wallet=wallet,
                payment_date=date,
                notes="Imported from the work log",
                received_by=user,
                status=PaymentStatus.VALID,
            )
            ledger.append(
                LedgerEntry(
                    customer=customer,
                    entry_date=date,
                    entry_type=LedgerEntryType.PAYMENT,
                    credit=payment.amount,
                    payment=payment,
                    narration=f"Payment {payment.receipt_no} ({payment.mode_label}) "
                    f"for order {order.order_no}"[:255],
                    created_by=user,
                )
            )
            result.payments += 1
        result.orders += 1
        totals["amount"] += subtotal
        totals["discount"] += discount
        totals["vat"] += vat
        totals["paid"] += paid
        totals["balance"] += total - paid

    LedgerEntry.objects.bulk_create(ledger)
    result.rows_imported = len(rows)
    result.totals = {k: q2(v) for k, v in totals.items()}
    result.date_from = min(r.date for r in rows)
    result.date_to = max(r.date for r in rows)


def _feet(unit: str) -> Decimal:
    return {"ft": Decimal("1"), "in": Decimal("12"), "cm": Decimal("30.48")}[unit]


# ---------- exporting ----------

EXPORT_COLUMNS = [
    ("Date", 12),
    ("Particular", 28),
    ("Address", 16),
    ("Items", 20),
    ("Height", 8),
    ("Width", 8),
    ("Qty", 6),
    ("SQFT", 9),
    ("Rate", 9),
    ("Amount", 11),
    ("Details", 30),
    ("Payment", 11),
    ("Payment Mode", 13),
    ("Discount", 10),
    ("Balance", 11),
    ("Order No", 12),
    ("Status", 12),
]


def _bs_dotted(day: dt.date) -> str:
    return (bs_string(day) or "").replace("-", ".")


def _num(value: Decimal) -> int | float:
    value = q2(value)
    return int(value) if value == value.to_integral_value() else float(value)


def export_work_log(date_from: dt.date | None, date_to: dt.date) -> bytes:
    """Orders as work-log rows (one per item), in the shop's familiar Excel layout.

    An order's discount and payments are spread over its rows from the top, so
    each row's Balance is Amount − Discount − Payment and the column adds up to
    what is still due on those orders. VAT and round-off go on the last row.
    """
    orders = (
        Order.objects.filter(order_date__lte=date_to)
        .exclude(status__in=[OrderStatus.QUOTATION, OrderStatus.CANCELLED])
        .select_related("customer")
        .prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.prefetch_related("addons")),
            Prefetch("payments", queryset=Payment.objects.filter(status=PaymentStatus.VALID)),
        )
        .order_by("order_date", "id")
    )
    if date_from is not None:
        orders = orders.filter(order_date__gte=date_from)

    wb = Workbook()
    ws = wb.active
    ws.title = "Work_Details_export"
    header_font = Font(bold=True, color="0F172A")
    header_fill = PatternFill("solid", fgColor="E2E8F0")
    for col, (title, width) in enumerate(EXPORT_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "A2"

    for order in orders:
        items = list(order.items.all())
        if not items:
            continue
        payments = list(order.payments.all())
        paid_left = q2(sum((p.amount for p in payments), ZERO))
        discount_left = order.discount_amount
        modes = ", ".join(dict.fromkeys(p.mode_label for p in payments))
        extra = q2(order.vat_amount + order.round_off)
        for index, item in enumerate(items):
            amount = item.line_total
            if index == len(items) - 1:
                amount = q2(amount + extra)
            discount = min(discount_left, amount)
            discount_left -= discount
            paid = min(paid_left, amount - discount)
            if index == len(items) - 1:
                paid = paid_left  # any advance beyond the bill shows on the last row
            paid_left -= paid
            details = [item.description, *(a.name for a in item.addons.all())]
            if index == len(items) - 1 and extra:
                details.append(f"incl. VAT {fmt_qty(order.vat_amount)}")
            sqft = q2(item.sqft * item.quantity) if not item.is_per_piece else ZERO
            ws.append(
                [
                    _bs_dotted(order.order_date),
                    order.customer.name,
                    order.customer.address,
                    item.media_name,
                    _num(item.height) if item.has_size else None,
                    _num(item.width) if item.has_size else None,
                    item.quantity,
                    _num(sqft),
                    _num(item.rate),
                    _num(amount),
                    ", ".join(d for d in details if d),
                    _num(paid),
                    modes if paid else "",
                    _num(discount),
                    _num(amount - discount - paid),
                    order.order_no,
                    order.get_status_display(),
                ]
            )
    ws.auto_filter.ref = ws.dimensions
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def work_log_template() -> bytes:
    """An empty work log with the expected headers and two example rows."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Work_Details"
    headers = [c for c, _ in EXPORT_COLUMNS[:15]]
    ws.append(headers)
    today = _bs_dotted(local_today())
    ws.append(
        [
            today,
            "Example Customer",
            "Nepalgunj",
            "Star Flex",
            3,
            6,
            1,
            18,
            35,
            630,
            "Shop banner",
            300,
            "Cash",
            0,
            330,
        ]
    )
    ws.append(
        [
            today,
            "Example Customer",
            "Nepalgunj",
            "Normal Photo",
            None,
            None,
            4,
            0,
            160,
            640,
            "Passport size",
            0,
            "",
            0,
            640,
        ]
    )
    for col, (_, width) in enumerate(EXPORT_COLUMNS[:15], start=1):
        ws.cell(row=1, column=col).font = Font(bold=True)
        ws.column_dimensions[get_column_letter(col)].width = width
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
