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

import csv
import datetime as dt
import hashlib
import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, BinaryIO

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from openpyxl import Workbook, load_workbook
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
from apps.core.dates import bs_string, from_bs, local_today
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

MAX_MESSAGES = 300
TOLERANCE = Decimal("1.00")  # rupees of rounding allowed between columns

# Header text (normalised) -> field. Checked in order; the first match wins.
_HEADERS: list[tuple[str, tuple[str, ...]]] = [
    ("date", ("date", "miti", "date bs", "date (bs)", "bs date")),
    ("customer", ("particular", "particulars", "customer", "customer name", "party", "name")),
    ("address", ("address", "place", "location")),
    ("phone", ("phone", "mobile", "contact", "phone no", "mobile no")),
    ("item", ("items", "item", "work", "media", "material", "product")),
    ("height", ("height", "h", "length")),
    ("width", ("width", "w", "breadth")),
    ("quantity", ("qty", "quantity", "pcs", "nos")),
    ("sqft", ("sqft", "sq ft", "sq.ft", "sq. ft", "area", "total sqft")),
    ("unit", ("unit",)),
    ("rate", ("rate", "price")),
    ("amount", ("amount", "total", "total amount")),
    ("details", ("details", "detail", "description", "remarks", "remark", "particular details")),
    ("discount", ("discount", "disc")),
    ("vat", ("vat", "vat amount")),
    ("balance", ("balance", "due", "remaining", "balance due")),
    ("order_no", ("order no", "order", "order number")),
]
REQUIRED = ("date", "customer", "item")


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _field_for(header: str) -> str | None:
    h = _norm(header)
    if not h:
        return None
    if h.startswith("payment") or h.startswith("paid") or h in ("received", "advance"):
        # "Payment Mode", "Payment Method", "Payment Type" (or a narrow column showing
        # just "Payment M") name the mode; any other payment column is the amount paid.
        rest = h.removeprefix("payment").strip(" .:-")
        return "mode" if rest.startswith(("m", "type", "via")) else "paid"
    if h in ("mode", "pay mode", "payment mode"):
        return "mode"
    for name, aliases in _HEADERS:
        if h in aliases:
            return name
    return None


# ---------- reading ----------


@dataclass
class Message:
    row: int
    message: str


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
    fingerprint: str = ""


@dataclass
class ParsedSheet:
    rows: list[SheetRow] = field(default_factory=list)
    errors: list[Message] = field(default_factory=list)
    warnings: list[Message] = field(default_factory=list)
    columns: dict[str, str] = field(default_factory=dict)
    header_row: int = 1
    rows_read: int = 0
    already_in_system: int = 0


def _raw_rows(content: bytes, name: str) -> list[tuple[Any, ...]]:
    if Path(name).suffix.lower() == ".csv":
        text = content.decode("utf-8-sig", errors="replace")
        return [tuple(r) for r in csv.reader(io.StringIO(text))]
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises several unrelated types for bad files
        raise ValueError("This is not an Excel (.xlsx) or CSV file.") from exc
    ws = wb.active
    return [tuple(r) for r in ws.iter_rows(values_only=True)]


def _find_header(rows: list[tuple[Any, ...]]) -> tuple[int, dict[int, str]]:
    for index, row in enumerate(rows[:15]):
        mapping: dict[int, str] = {}
        for col, value in enumerate(row):
            name = _field_for(value)
            if name and name not in mapping.values():
                mapping[col] = name
        if all(f in mapping.values() for f in REQUIRED):
            return index, mapping
    raise ValueError(
        "Could not find the header row. The sheet needs at least the columns "
        "Date, Particular (customer) and Items."
    )


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return re.sub(r"\s+", " ", str(value)).strip()


def _decimal(value: Any, label: str) -> Decimal:
    if value in (None, ""):
        return ZERO
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    cleaned = str(value).replace(",", "").replace("Rs.", "").replace("Rs", "").strip()
    if cleaned in ("", "-"):
        return ZERO
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a number, not '{value}'.") from exc


_DATE_RE = re.compile(r"^\s*(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*$")


def parse_date(value: Any) -> dt.date:
    """Read a BS date like ``2083.04.01`` (or an AD date / Excel date cell)."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = _cell_text(value)
    match = _DATE_RE.match(text)
    if not match:
        raise ValueError(f"Date '{text}' is not in the form YYYY.MM.DD.")
    year, month, day = (int(p) for p in match.groups())
    try:
        if year >= 2050:  # Bikram Sambat (AD 2050 is far in the future)
            return from_bs(year, month, day)
        return dt.date(year, month, day)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Date '{text}' does not exist.") from exc


_WALLETS = {
    "esewa": Wallet.ESEWA,
    "e-sewa": Wallet.ESEWA,
    "e sewa": Wallet.ESEWA,
    "khalti": Wallet.KHALTI,
    "fonepay": Wallet.FONEPAY,
    "fone pay": Wallet.FONEPAY,
    "qr": Wallet.OTHER_QR,
    "wallet": Wallet.OTHER_QR,
}


def parse_mode(value: Any) -> tuple[str, str]:
    """Map a free-text payment mode to (mode, wallet). Blank means cash."""
    text = _norm(value)
    if not text or text in ("cash", "nagad"):
        return PaymentMode.CASH, ""
    for key, wallet in _WALLETS.items():
        if key in text:
            return PaymentMode.WALLET, wallet
    if "cheque" in text or "check" in text or "chq" in text:
        return PaymentMode.CHEQUE, ""
    if "bank" in text or "transfer" in text or "online" in text or "mobile banking" in text:
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


def read_sheet(content: bytes, name: str) -> ParsedSheet:
    """Parse and check every row. Nothing is written to the database."""
    raw = _raw_rows(content, name)
    header_index, mapping = _find_header(raw)
    sheet = ParsedSheet(header_row=header_index + 1)
    headers = raw[header_index]
    sheet.columns = {f: _cell_text(headers[c]) for c, f in mapping.items()}
    existing_orders = set(Order.objects.values_list("order_no", flat=True))

    last_date: dt.date | None = None
    for offset, values in enumerate(raw[header_index + 1 :], start=header_index + 2):
        cells = {f: values[c] if c < len(values) else None for c, f in mapping.items()}
        if all(_cell_text(v) == "" for v in cells.values()):
            continue
        sheet.rows_read += 1
        if _cell_text(cells.get("order_no")) in existing_orders:
            sheet.already_in_system += 1
            continue
        try:
            row = _parse_row(offset, cells, last_date, sheet.warnings)
        except ValueError as exc:
            sheet.errors.append(Message(offset, str(exc)))
            continue
        if row is None:
            sheet.rows_read -= 1  # a totals or note line, not work
            continue
        last_date = row.date
        sheet.rows.append(row)

    seen: Counter[str] = Counter()
    for row in sheet.rows:
        base = _fingerprint(row, 0)
        row.fingerprint = _fingerprint(row, seen[base]) if seen[base] else base
        seen[base] += 1
    return sheet


def _parse_row(
    number: int, cells: dict[str, Any], last_date: dt.date | None, warnings: list[Message]
) -> SheetRow | None:
    customer = _cell_text(cells.get("customer"))
    item = _cell_text(cells.get("item"))
    amount = q2(_decimal(cells.get("amount"), "Amount"))
    if not customer and not item:
        return None  # e.g. a "Total" line at the bottom of the sheet
    if not customer:
        raise ValueError("Particular (customer name) is empty.")
    if not item:
        raise ValueError("Items is empty; write what was made (e.g. Banner).")
    if len(customer) > 150:
        raise ValueError("Particular is longer than 150 characters.")

    if _cell_text(cells.get("date")):
        date = parse_date(cells.get("date"))
    elif last_date is not None:
        date = last_date
        warnings.append(Message(number, "No date; used the date from the row above."))
    else:
        raise ValueError("Date is empty.")
    if date > local_today():
        raise ValueError(f"Date {bs_string(date)} BS is in the future.")

    height = _decimal(cells.get("height"), "Height")
    width = _decimal(cells.get("width"), "Width")
    if height < 0 or width < 0:
        raise ValueError("Height and width cannot be negative.")
    quantity_raw = _decimal(cells.get("quantity"), "Qty") or Decimal("1")
    if quantity_raw != quantity_raw.to_integral_value() or quantity_raw < 1:
        raise ValueError(f"Qty must be a whole number of pieces, not {fmt_qty(quantity_raw)}.")
    quantity = int(quantity_raw)
    unit = _norm(cells.get("unit")) or "ft"
    unit = {"feet": "ft", "foot": "ft", "inch": "in", "inches": "in"}.get(unit, unit)
    if unit not in ("ft", "in", "cm"):
        raise ValueError(f"Unit '{unit}' is not known. Use ft, in or cm.")
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
            warnings.append(
                Message(
                    number,
                    f"Amount {fmt_qty(amount)} is neither SQFT × Rate "
                    f"({fmt_qty(q2(sqft_total * rate))}) nor Qty × Rate "
                    f"({fmt_qty(q2(rate * quantity))}); the sheet's amount is kept.",
                )
            )
        elif not _close(rate * quantity, amount):
            warnings.append(
                Message(
                    number,
                    f"Amount {fmt_qty(amount)} is not Qty × Rate "
                    f"({fmt_qty(q2(rate * quantity))}); the sheet's amount is kept.",
                )
            )

    paid = q2(_decimal(cells.get("paid"), "Payment"))
    discount = q2(_decimal(cells.get("discount"), "Discount"))
    vat = q2(_decimal(cells.get("vat"), "VAT"))
    if paid < 0 or discount < 0 or vat < 0:
        raise ValueError("Payment, discount and VAT cannot be negative.")
    if discount > amount:
        raise ValueError("Discount is more than the amount.")
    mode, wallet = parse_mode(cells.get("mode")) if paid > 0 else (PaymentMode.CASH, "")
    if _cell_text(cells.get("balance")):
        balance = q2(_decimal(cells.get("balance"), "Balance"))
        expected = q2(amount - discount + vat - paid)
        if not _close(balance, expected):
            warnings.append(
                Message(
                    number,
                    f"Balance {fmt_qty(balance)} does not match Amount − Discount − Payment "
                    f"({fmt_qty(expected)}); the ledger uses {fmt_qty(expected)}.",
                )
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
        details=_cell_text(cells.get("details"))[:200],
        paid=paid,
        mode=mode,
        wallet=wallet,
        discount=discount,
        vat=vat,
    )


# ---------- importing ----------


@dataclass
class ImportResult:
    dry_run: bool
    file_name: str
    header_row: int
    columns: dict[str, str]
    rows_read: int
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
    request: Any = None,
) -> ImportResult:
    """Import a work-log sheet. With ``dry_run`` everything is checked, then rolled back.

    Rows with errors stop the import unless ``skip_errors`` is set, in which
    case only the valid rows are imported.
    """
    sheet = read_sheet(file.read(), name)
    result = ImportResult(
        dry_run=dry_run,
        file_name=name,
        header_row=sheet.header_row,
        columns=sheet.columns,
        rows_read=sheet.rows_read,
        rows_skipped_error=len({e.row for e in sheet.errors}),
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
            notes=f"Imported from {result.file_name}, row{'s' if first != last else ''} "
            f"{first}{f'–{last}' if first != last else ''}.",
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
