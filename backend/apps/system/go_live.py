"""Go-live imports from the shop's own sheets: customers with their opening
balances (the ledger), the rate card and opening stock.

Each import reads the file with the forgiving reader in ``sheets.py``, checks
every row, and saves nothing unless asked (``dry_run=False``) and every row is
fine (or ``skip_errors`` is set). Rows that would count money or stock twice,
such as a customer who already has transactions or an item that already has
opening stock, are skipped with a note instead.
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import io
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from apps.billing.models import LedgerEntry, Payment
from apps.billing.services import (
    find_recorded_payment,
    opening_entries,
    previous_year_end,
    record_imported_payment,
    set_opening_balance,
)
from apps.catalog.models import AddOn, AddOnBasis, MediaType, PricingUnit
from apps.core.activity import log_activity
from apps.core.dates import bs_string, local_today
from apps.core.exceptions import BusinessError
from apps.core.money import ZERO, fmt_qty, q2
from apps.customers.models import Customer, CustomerType
from apps.inventory.models import DEFAULT_UNIT, MovementType, StockItem, StockKind, StockUnit
from apps.inventory.services import RollSpec, add_opening_stock

from . import sheets
from .sheets import Column, Columns, Message, cell_text, norm, to_decimal
from .work_log import parse_mode

MAX_MESSAGES = 300

Note = Callable[[str], None]


@dataclass
class TableImportResult:
    kind: str
    dry_run: bool
    file_name: str
    sheets: list[str] = field(default_factory=list)
    header_row: int = 0
    columns: dict[str, str] = field(default_factory=dict)
    headers: list[str] = field(default_factory=list)
    needs_columns: bool = False
    problem: str = ""
    rows_read: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    rows_skipped_error: int = 0
    errors: list[Message] = field(default_factory=list)
    warnings: list[Message] = field(default_factory=list)
    summary: dict[str, str] = field(default_factory=dict)

    @property
    def can_import(self) -> bool:
        return self.created + self.updated > 0


@dataclass
class Kind:
    key: str
    title: str
    columns: Columns
    handle: Callable[[dict[str, Any], Note, dict[str, Any]], str | None]
    template: list[list[Any]]
    # The "as on" date when none is given: last year's closing for balances.
    default_as_of: Callable[[], dt.date] = previous_year_end


class _Rollback(Exception):
    pass


def _message(exc: Exception) -> str:
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            return "; ".join(f"{k}: {' '.join(v)}" for k, v in exc.message_dict.items())
        return "; ".join(exc.messages)
    if isinstance(exc, BusinessError):
        detail = exc.detail
        if isinstance(detail, dict):
            return "; ".join(" ".join(str(m) for m in v) for v in detail.values())
        return str(detail)
    return str(exc)


def run_import(
    kind: str,
    content: bytes,
    *,
    name: str,
    user: Any,
    dry_run: bool = True,
    skip_errors: bool = False,
    columns: dict[str, str] | None = None,
    as_of: dt.date | None = None,
    request: Any = None,
) -> TableImportResult:
    spec = KINDS[kind]
    result = TableImportResult(kind=kind, dry_run=dry_run, file_name=name)
    try:
        located = sheets.locate(sheets.read_tables(content, name), spec.columns, columns)
    except sheets.ColumnsNeeded as exc:
        result.dry_run, result.needs_columns = True, True
        result.headers, result.problem = exc.headers, str(exc)
        return result
    info = sheets.describe(located)
    result.sheets, result.header_row = info.sheets, info.header_row
    result.columns, result.headers = info.columns, info.headers
    context: dict[str, Any] = {
        "user": user,
        "as_of": as_of or spec.default_as_of(),
        "file": name,
        "seen": set(),
        "totals": {},
    }
    errors: list[Message] = []
    warnings: list[Message] = []

    try:
        with transaction.atomic():
            several = len(located) > 1
            for loc in located:
                label = loc.table.name if several else ""
                context["sheet"] = loc.table.name
                for number, cells in sheets.records(loc, spec.columns):

                    def note(text: str, number: int = number, label: str = label) -> None:
                        warnings.append(Message(number, text, label))

                    try:
                        with transaction.atomic():  # a failed row leaves nothing behind
                            outcome = spec.handle(cells, note, context)
                    except (ValueError, BusinessError, DjangoValidationError) as exc:
                        result.rows_read += 1
                        errors.append(Message(number, _message(exc), label))
                        continue
                    if outcome is None:
                        continue  # a blank, note or totals line
                    result.rows_read += 1
                    setattr(result, outcome, getattr(result, outcome) + 1)
            result.summary = {k: fmt_qty(v) for k, v in context["totals"].items()}
            blocked = bool(errors) and not skip_errors
            if dry_run or blocked:
                raise _Rollback
            log_activity(
                user,
                f"import.{kind}",
                None,
                message=f"{name}: {result.created} added, {result.updated} updated",
                metadata={"file": name, "created": result.created, "updated": result.updated},
                request=request,
            )
    except _Rollback:
        result.dry_run = True
    result.rows_skipped_error = len({(e.sheet, e.row) for e in errors})
    result.errors, result.warnings = errors[:MAX_MESSAGES], warnings[:MAX_MESSAGES]
    return result


def _add(context: dict[str, Any], key: str, amount: Decimal) -> None:
    context["totals"][key] = context["totals"].get(key, ZERO) + amount


def _is_total_line(text: str) -> bool:
    key = sheets.header_key(text)
    return key in {"total", "grand total", "sub total", "जम्मा", "कुल"} or key.startswith("total ")


# ---------- customers and opening balances (the ledger) ----------

CUSTOMER_COLUMNS = Columns(
    fields=[
        Column(
            "alt_phone",
            "Second phone",
            ("alt phone", "alternate phone", "phone 2", "mobile 2", "other phone"),
            ("alt", "alternate", "secondary"),
        ),
        Column(
            "phone",
            "Phone",
            ("phone", "mobile", "contact", "phone no", "mobile no", "contact no"),
            ("phone", "mobile", "contact", "mob", "cell", "फोन", "मोबाइल"),
        ),
        Column(
            "pan_no",
            "PAN / VAT no.",
            ("pan", "vat", "pan no", "vat no", "pan vat", "pan vat no", "pan number"),
            ("pan", "vat no", "vat number", "प्यान"),
        ),
        Column("drcr", "Dr / Cr", ("dr cr", "drcr", "cr dr"), ()),
        Column(
            "credit",
            "Advance (credit)",
            ("credit", "cr", "advance", "advance paid", "deposit"),
            ("credit", "advance", "deposit", "पेश्की", "दिनुपर्ने"),
        ),
        Column(
            "balance",
            "Opening balance (due)",
            (
                "opening balance",
                "balance",
                "opening",
                "due",
                "dues",
                "debit",
                "dr",
                "previous balance",
                "old balance",
                "outstanding",
                "closing balance",
            ),
            ("balance", "due", "debit", "outstanding", "receivable", "baki", "बाँकी", "बाकी"),
        ),
        Column(
            "address",
            "Address",
            ("address", "place", "location"),
            ("address", "place", "location", "city", "ठेगाना"),
        ),
        Column(
            "customer_type",
            "Type",
            ("type", "customer type", "kind", "category"),
            ("type", "category"),
        ),
        Column("notes", "Notes", ("notes", "note", "remarks"), ("note", "remark", "कैफियत")),
        Column(
            "name",
            "Name",
            ("name", "customer", "customer name", "party", "party name", "particular", "client"),
            ("customer", "party", "client", "name", "particular", "account", "नाम", "ग्राहक"),
        ),
    ],
    required=("name",),
)

_PHONE = re.compile(r"\+?\d[\d\- ]{5,}\d")


def _phones(*texts: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        for match in _PHONE.findall(sheets.digits(text)):
            number = re.sub(r"[^\d+]", "", match)[:20]
            if number not in found:
                found.append(number)
    return found


def _customer_type(text: str) -> str:
    key = norm(text)
    business = ("b", "business", "company", "firm", "org", "organisation", "organization")
    if key.startswith(business) or key in ("pvt", "office", "institution", "संस्था"):
        return CustomerType.BUSINESS
    return CustomerType.INDIVIDUAL


def _customer_row(cells: dict[str, Any], note: Note, context: dict[str, Any]) -> str | None:
    name = " ".join(cell_text(cells.get("name")).split())
    if _is_total_line(name):
        return None
    if not name:
        if any(cell_text(v) for v in cells.values()):
            raise ValueError("Name is empty.")
        return None
    if len(name) > 150:
        raise ValueError("Name is longer than 150 characters.")
    phones = _phones(cell_text(cells.get("phone")), cell_text(cells.get("alt_phone")))
    phone, alt_phone = [*phones, "", ""][:2]

    pan = re.sub(r"\D", "", sheets.digits(cell_text(cells.get("pan_no"))))
    if pan and len(pan) != 9:
        note(f"PAN '{cell_text(cells.get('pan_no'))}' is not 9 digits; left out.")
        pan = ""

    balance = to_decimal(cells.get("balance"), "Opening balance")
    advance = to_decimal(cells.get("credit"), "Advance")
    if norm(cells.get("drcr")).startswith("cr"):
        balance = -abs(balance)
    opening = q2(balance - abs(advance))

    key = (name.lower(), phone)
    if key in context["seen"]:
        note(f"{name} appears again in the file; this row is skipped.")
        return "skipped"
    context["seen"].add(key)

    existing = Customer.objects.filter(name__iexact=name)
    if phone:
        existing = existing.filter(phone=phone)
    customer = existing.order_by("id").first()
    if customer is not None:
        current = opening_entries(customer)
        if current.exists():
            # A corrected ledger sheet: bring the opening balance to the sheet's figure.
            old = q2(sum((e.debit - e.credit for e in current), ZERO))
            if old == opening:
                return "skipped"
            set_opening_balance(
                customer=customer,
                amount=opening,
                user=context["user"],
                reason=f"corrected by the import of {context['file']}",
            )
            note(f"{name}: opening balance changed from {fmt_qty(old)} to {fmt_qty(opening)}.")
            _add(context, "opening_corrected", Decimal(1))
            return "updated"
        if not opening:
            return "skipped"
        if LedgerEntry.objects.filter(customer=customer).exists():
            note(
                f"{name} already has entries in the ledger (such as imported work), so the "
                f"opening balance {fmt_qty(opening)} was not added; it would count twice. "
                "Use Opening balance on the customer if it is really needed."
            )
            return "skipped"
        set_opening_balance(
            customer=customer, amount=opening, user=context["user"], as_of=context["as_of"]
        )
        _add(context, "opening_due" if opening > 0 else "opening_advance", abs(opening))
        return "updated"

    customer = Customer(
        name=name,
        phone=phone,
        alt_phone=alt_phone,
        address=cell_text(cells.get("address"))[:255],
        pan_no=pan,
        customer_type=_customer_type(cell_text(cells.get("customer_type"))),
        notes=cell_text(cells.get("notes")),
        created_by=context["user"],
    )
    customer.full_clean()
    customer.save()
    if opening:
        set_opening_balance(
            customer=customer, amount=opening, user=context["user"], as_of=context["as_of"]
        )
        _add(context, "opening_due" if opening > 0 else "opening_advance", abs(opening))
    return "created"


# ---------- rate card ----------

RATE_CARD_COLUMNS = Columns(
    fields=[
        Column("kind", "Media or add-on", ("kind", "type", "category"), ()),
        Column(
            "material",
            "Stock item used",
            ("material", "stock item", "stock", "linked stock"),
            ("stock item",),
        ),
        Column(
            "min_sqft",
            "Minimum sq ft",
            ("min sqft", "minimum sqft", "min sq ft", "minimum sq ft", "min", "minimum"),
            ("min", "minimum"),
        ),
        Column("rate", "Rate", ("rate", "price"), ("rate", "price", "charge", "दर", "मूल्य")),
        Column(
            "pricing_unit",
            "Per (sq ft / piece)",
            ("unit", "per", "pricing unit", "rate per", "uom"),
            ("per", "unit"),
        ),
        Column("basis", "Add-on basis", ("basis", "charged", "charge type"), ("basis",)),
        Column(
            "default_quantity",
            "Default quantity",
            ("default quantity", "default qty", "qty", "quantity"),
            ("default", "qty", "quantity"),
        ),
        Column("active", "Active", ("active", "status", "in use"), ("active", "status")),
        Column(
            "name",
            "Name",
            ("name", "item", "items", "item name", "media", "product", "particular", "particulars"),
            ("item", "media", "name", "product", "particular", "service", "सामान"),
        ),
    ],
    required=("name", "rate"),
)

_BASIS_WORDS = [
    (AddOnBasis.PERCENT, ("%", "percent")),
    (AddOnBasis.PER_RUNNING_FT, ("running", "rft", "r ft", "perimeter")),
    (AddOnBasis.PER_SQFT, ("sqft", "sq ft", "sft", "area")),
    (AddOnBasis.PER_PIECE, ("piece", "pcs", "each", "unit", "nos")),
    (AddOnBasis.FIXED, ("fixed", "flat", "lump", "line")),
]


def _basis(text: str) -> str | None:
    key = norm(text).replace("_", " ")
    for value, words in _BASIS_WORDS:
        if key == value.replace("_", " ") or any(w in key for w in words):
            return value
    return None


def _per_piece(*texts: str) -> bool | None:
    joined = " ".join(norm(t) for t in texts)
    if any(w in joined for w in ("sqft", "sq ft", "sft", "square", "sq.ft")):
        return False
    if re.search(r"\b(?:pcs?|pieces?|each|nos|set|unit)\b", joined):
        return True
    return None


def _rate_card_row(cells: dict[str, Any], note: Note, context: dict[str, Any]) -> str | None:
    name = " ".join(cell_text(cells.get("name")).split())
    if _is_total_line(name):
        return None
    if not name:
        if any(cell_text(v) for v in cells.values()):
            raise ValueError("Name is empty.")
        return None
    if len(name) > 80:
        raise ValueError("Name is longer than 80 characters.")
    rate_text = cell_text(cells.get("rate"))
    if not rate_text:
        raise ValueError("Rate is empty.")
    rate = q2(to_decimal(cells.get("rate"), "Rate"))
    if rate < 0:
        raise ValueError("Rate cannot be negative.")
    kind_text = norm(cells.get("kind"))
    basis_text = cell_text(cells.get("basis"))
    is_addon = kind_text.startswith(("add", "extra", "finish", "service")) or (
        not kind_text and bool(basis_text)
    )
    active = sheets.to_bool(cells.get("active"))
    order = context.setdefault("order", 0)
    context["order"] = order + 1
    existing_name = {"name__iexact": name}

    if is_addon:
        basis = _basis(basis_text) or _basis(rate_text)
        if basis is None:
            basis = AddOnBasis.FIXED
            note(f"No basis for add-on {name}; charged as a fixed amount per item line.")
        quantity = to_decimal(cells.get("default_quantity"), "Default quantity") or Decimal("1")
        addon = AddOn.objects.filter(**existing_name).first()
        values = {
            "basis": basis,
            "rate": rate,
            "default_quantity": quantity,
            "is_active": active,
            "sort_order": order,
        }
        if addon is None:
            AddOn.objects.create(name=name, **values)
            return "created"
        for key, value in values.items():
            setattr(addon, key, value)
        addon.save()
        return "updated"

    per_piece = _per_piece(cell_text(cells.get("pricing_unit")), rate_text)
    material = None
    if material_name := cell_text(cells.get("material")):
        material = StockItem.objects.filter(name__iexact=material_name).first()
        if material is None:
            note(f"Stock item '{material_name}' was not found; {name} is not linked to stock.")
    min_text = cell_text(cells.get("min_sqft"))
    values = {
        "pricing_unit": PricingUnit.PIECE if per_piece else PricingUnit.SQFT,
        "rate": rate,
        "min_sqft": q2(to_decimal(min_text, "Minimum sq ft")) if min_text else None,
        "is_active": active,
        "sort_order": order,
    }
    media = MediaType.objects.filter(**existing_name).first()
    if media is None:
        MediaType.objects.create(name=name, material=material, **values)
        return "created"
    for key, value in values.items():
        setattr(media, key, value)
    if material is not None:
        media.material = material
    media.save()
    return "updated"


# ---------- opening stock ----------

STOCK_COLUMNS = Columns(
    fields=[
        Column(
            "roll_count",
            "Number of rolls",
            ("rolls", "roll count", "no of rolls", "number of rolls", "roll qty"),
            ("rolls", "roll count"),
        ),
        Column(
            "roll_width_ft",
            "Roll width (ft)",
            ("roll width", "width", "roll width ft"),
            ("width", "चौडाइ"),
        ),
        Column(
            "roll_length_ft",
            "Roll length (ft)",
            ("roll length", "length", "roll length ft"),
            ("length", "लम्बाइ"),
        ),
        Column(
            "remaining_sqft",
            "Sq ft left on the roll",
            ("remaining", "remaining sqft", "sqft left", "left"),
            ("remaining", "left"),
        ),
        Column(
            "low_stock_level",
            "Low-stock level",
            ("low stock", "low stock level", "reorder level", "minimum", "min"),
            ("low", "reorder", "minimum"),
        ),
        Column(
            "quantity",
            "Quantity",
            (
                "qty",
                "quantity",
                "stock",
                "balance",
                "on hand",
                "opening",
                "opening stock",
                "closing stock",
                "closing",
            ),
            ("qty", "quantity", "balance", "on hand", "opening", "closing", "परिमाण"),
        ),
        Column("unit", "Unit", ("unit", "uom"), ()),
        Column("kind", "Kind", ("kind", "type", "category"), ()),
        Column(
            "item",
            "Item",
            ("item", "items", "name", "stock item", "material", "particular", "product"),
            ("item", "material", "name", "product", "particular", "सामान"),
        ),
    ],
    required=("item",),
    any_of=("quantity", "roll_width_ft"),
)

_KIND_WORDS = [
    (StockKind.ROLL_MEDIA, ("roll", "flex", "vinyl", "media", "sticker", "canvas", "backlit")),
    (StockKind.INK, ("ink",)),
    (StockKind.EYELETS, ("eyelet", "ring")),
    (StockKind.FRAME, ("frame", "pipe", "patti")),
    (StockKind.STANDEE, ("standee", "stand")),
]
_UNIT_WORDS = [
    (StockUnit.SQFT, ("sqft", "sq ft", "sft")),
    (StockUnit.RUNNING_FT, ("rft", "running", "r ft")),
    (StockUnit.LITRE, ("litre", "liter", "ltr", "l")),
    (StockUnit.BOX, ("box", "packet", "pkt")),
    (StockUnit.PIECE, ("pcs", "piece", "nos", "no", "set")),
]


def _kind(text: str) -> StockKind | None:
    key = norm(text)
    if key in StockKind.values:
        return StockKind(key)
    for kind, words in _KIND_WORDS:
        if any(w in key for w in words):
            return kind
    return None


def _unit(text: str) -> str | None:
    key = norm(text).strip(".")
    for unit, words in _UNIT_WORDS:
        if key == unit or key in words or any(w in key for w in words if len(w) > 2):
            return unit
    return None


def _stock_row(cells: dict[str, Any], note: Note, context: dict[str, Any]) -> str | None:
    name = " ".join(cell_text(cells.get("item")).split())
    if _is_total_line(name):
        return None
    if not name:
        if any(cell_text(v) for v in cells.values()):
            raise ValueError("Item is empty.")
        return None
    width = to_decimal(cells.get("roll_width_ft"), "Roll width")
    length = to_decimal(cells.get("roll_length_ft"), "Roll length")
    has_roll = width > 0 and length > 0
    kind = _kind(cell_text(cells.get("kind"))) or (
        StockKind.ROLL_MEDIA if has_roll else _kind(name) or StockKind.OTHER
    )
    item = StockItem.objects.filter(name__iexact=name).first()
    created = item is None
    if item is None:
        unit = _unit(cell_text(cells.get("unit"))) or DEFAULT_UNIT[kind]
        if kind == StockKind.ROLL_MEDIA:
            unit = StockUnit.SQFT
        item = StockItem.objects.create(
            name=name,
            kind=kind,
            unit=unit,
            low_stock_level=to_decimal(cells.get("low_stock_level"), "Low-stock level"),
        )
    elif (
        item.pk not in context["seen"]
        and item.movements.filter(movement_type=MovementType.OPENING).exists()
    ):
        note(f"{name} already has opening stock; this row is skipped.")
        return "skipped"
    context["seen"].add(item.pk)

    if item.is_roll_media:
        if not has_roll:
            raise ValueError(f"{name} is a roll; give its width and length in feet.")
        count = int(to_decimal(cells.get("roll_count"), "Number of rolls") or 1)
        remaining_text = cell_text(cells.get("remaining_sqft"))
        remaining = to_decimal(remaining_text, "Sq ft left") if remaining_text else None
        if remaining is not None and count > 1:
            note("Sq ft left applies to one roll; the other rolls are counted as full.")
        rolls = [RollSpec(width, length, remaining if i == 0 else None) for i in range(count)]
        add_opening_stock(user=context["user"], stock_item=item, rolls=rolls)
        _add(context, "rolls", Decimal(count))
    else:
        quantity = to_decimal(cells.get("quantity"), "Quantity")
        if quantity <= 0:
            note(f"No quantity for {name}; the item is added without stock.")
        else:
            add_opening_stock(user=context["user"], stock_item=item, quantity=quantity)
    return "created" if created else "updated"


# ---------- payments received ----------

PAYMENT_COLUMNS = Columns(
    fields=[
        Column(
            "reference",
            "Reference / cheque no.",
            ("reference", "ref", "ref no", "transaction no", "transaction id", "cheque no"),
            ("reference", "transaction", "txn", "cheque no", "voucher"),
        ),
        Column("date", "Date", ("date", "miti", "date bs", "bs date"), ("date", "miti", "मिति")),
        Column("mode", "Mode", ("mode", "payment mode", "method", "via"), ("mode", "method")),
        Column(
            "remark",
            "Remark",
            ("remark", "remarks", "note", "notes", "narration", "details", "description"),
            ("remark", "note", "narration", "detail", "description", "कैफियत"),
        ),
        Column(
            "phone",
            "Phone",
            ("phone", "mobile", "contact"),
            ("phone", "mobile", "contact", "mob", "फोन"),
        ),
        Column(
            "amount",
            "Amount",
            ("amount", "received", "paid", "credit", "cr", "payment", "rs"),
            ("amount", "received", "paid", "credit", "payment", "रकम"),
        ),
        Column(
            "customer",
            "Customer",
            ("customer", "customer name", "party", "party name", "name", "particular"),
            ("customer", "party", "client", "name", "particular", "account", "नाम", "ग्राहक"),
        ),
    ],
    required=("customer", "amount"),
)


def _customer_index(context: dict[str, Any]) -> dict[str, list[Customer]]:
    if "customers" not in context:
        index: dict[str, list[Customer]] = {}
        for customer in Customer.objects.order_by("id"):
            index.setdefault(norm(customer.name), []).append(customer)
        context["customers"] = index
    return context["customers"]


def _find_customer(name: str, phone: str, context: dict[str, Any]) -> Customer:
    index = _customer_index(context)
    matches = index.get(norm(name), [])
    if phone and len(matches) > 1:
        by_phone = [c for c in matches if c.phone == phone]
        if len(by_phone) == 1:
            return by_phone[0]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"{len(matches)} customers are named '{name}'; add a Phone column to tell them apart."
        )
    close = difflib.get_close_matches(norm(name), list(index), n=3, cutoff=0.75)
    names = [index[c][0].name for c in close]
    hint = f" Did you mean {' or '.join(repr(n) for n in names)}?" if names else ""
    raise ValueError(
        f"Customer '{name}' is not in the system.{hint} "
        "Fix the name in the sheet, or add the customer first."
    )


def _payment_row(cells: dict[str, Any], note: Note, context: dict[str, Any]) -> str | None:
    name = " ".join(cell_text(cells.get("customer")).split())
    if _is_total_line(name) or _is_total_line(cell_text(cells.get("date"))):
        return None
    amount_text = cell_text(cells.get("amount"))
    if not name and not amount_text:
        return None
    if not name:
        raise ValueError("Customer is empty.")
    amount = q2(to_decimal(cells.get("amount"), "Amount"))
    if amount < 0:
        raise ValueError("Amount is negative; refunds are not imported.")
    if amount == 0:
        return None

    # Dates: the cell, else the row above (merged cells), else the form's date.
    last_dates: dict[str, dt.date] = context.setdefault("last_dates", {})
    sheet = context.get("sheet", "")
    if cell_text(cells.get("date")):
        date = sheets.parse_date(cells.get("date"))
    elif sheet in last_dates:
        date = last_dates[sheet]
        note("No date; used the date from the row above.")
    else:
        date = context["as_of"]
        note(f"No date; recorded on {bs_string(date)} BS (the date chosen for undated rows).")
    if date > local_today():
        raise ValueError(f"Date {bs_string(date)} BS is in the future.")
    last_dates[sheet] = date

    phone = (re.findall(r"\d{7,}", sheets.digits(cell_text(cells.get("phone")))) or [""])[0]
    customer = _find_customer(name, phone, context)

    remark = cell_text(cells.get("remark"))
    mode_text = cell_text(cells.get("mode"))
    if sheets.is_filler(mode_text):
        mode_text = ""  # "—" or "N/A": the remark says how it was paid
    mode, wallet = "cash", ""
    try:
        mode, wallet = parse_mode(mode_text or remark)
    except ValueError:
        if mode_text:
            note(f"Payment mode '{mode_text}' is not known; recorded as cash.")

    # The same row uploaded again (or in a longer sheet) is recognised by its fingerprint.
    key = "|".join([date.isoformat(), norm(customer.name), str(amount), norm(remark)])
    occurrences = context.setdefault("occurrences", {})
    occurrences[key] = occurrences.get(key, 0) + 1
    fingerprint = hashlib.sha1(
        f"{key}|{occurrences[key]}".encode(), usedforsecurity=False
    ).hexdigest()
    if Payment.objects.filter(import_ref=fingerprint).exists():
        return "skipped"
    # Recorded another way already (order slip, work log, typed in)? Not twice.
    matched: set[int] = context.setdefault("matched", set())
    earlier = find_recorded_payment(
        customer=customer, payment_date=date, amount=amount, exclude=matched, only_entered=True
    )
    if earlier is not None:
        matched.add(earlier.pk)
        note(
            f"{customer.name} {fmt_qty(amount)} on {bs_string(date)} BS is already recorded as "
            f"{earlier.receipt_no}; not added again."
        )
        _add(context, "already_recorded", Decimal(1))
        return "skipped"

    record_imported_payment(
        user=context["user"],
        customer=customer,
        amount=amount,
        mode=mode,
        wallet=wallet,
        payment_date=date,
        reference_no=cell_text(cells.get("reference")),
        notes=remark or f"Imported from {context['file']}",
        import_ref=fingerprint,
    )
    _add(context, "amount", amount)
    _add(context, f"by_{mode}", amount)
    return "created"


# ---------- kinds and templates ----------

KINDS: dict[str, Kind] = {
    "customers": Kind(
        "customers",
        "Customers and opening balances",
        CUSTOMER_COLUMNS,
        _customer_row,
        [
            ["Name", "Phone", "Address", "PAN / VAT no.", "Type", "Opening balance", "Notes"],
            [
                "Nepalgunj Medical Hall",
                "9858020001",
                "Dhamboji, Nepalgunj",
                "301234567",
                "Business",
                4500,
                "",
            ],
            [
                "Ramesh Gupta",
                "9848030006",
                "Nepalgunj-4",
                "",
                "Individual",
                -500,
                "Advance (negative)",
            ],
        ],
    ),
    "rate-card": Kind(
        "rate-card",
        "Rate card",
        RATE_CARD_COLUMNS,
        _rate_card_row,
        [
            [
                "Kind",
                "Name",
                "Rate",
                "Per",
                "Minimum sq ft",
                "Material",
                "Basis",
                "Default quantity",
                "Active",
            ],
            ["Media", "Star Flex", 35, "sq ft", "", "Star Flex", "", "", "Yes"],
            ["Media", "Photo print A4", 60, "piece", "", "", "", "", "Yes"],
            ["Add-on", "Eyelets", 5, "", "", "", "Per piece", 8, "Yes"],
        ],
    ),
    "payments": Kind(
        "payments",
        "Payments received",
        PAYMENT_COLUMNS,
        _payment_row,
        [
            ["Date", "Customer", "Amount", "Mode", "Remark"],
            ["2083.04.01", "Aayan Digital", 820, "", "Bill payment"],
            ["2083.04.02", "Rara IT Hub", 5300, "QR", "QR: Om Trade"],
            ["", "Digital Nepal", "36,000", "Cash", "Undated: uses the date chosen when uploading"],
        ],
        default_as_of=local_today,
    ),
    "opening-stock": Kind(
        "opening-stock",
        "Opening stock",
        STOCK_COLUMNS,
        _stock_row,
        [
            [
                "Item",
                "Kind",
                "Quantity",
                "Unit",
                "Roll width (ft)",
                "Roll length (ft)",
                "Rolls",
                "Sq ft left",
                "Low-stock level",
            ],
            ["Star Flex", "Roll media", "", "", 10, 164, 2, "", 400],
            ["Eco-solvent ink (cyan)", "Ink", 4, "litre", "", "", "", "", 1],
        ],
    ),
}


def template(kind: str) -> bytes:
    """A blank sheet with the usual columns and two example rows."""
    rows = KINDS[kind].template
    wb = Workbook()
    ws = wb.active
    ws.title = KINDS[kind].title[:31]
    for row in rows:
        ws.append(row)
    fill = PatternFill("solid", fgColor="E2E8F0")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = fill
    for col, header in enumerate(rows[0], start=1):
        ws.column_dimensions[ws.cell(1, col).column_letter].width = max(12, len(str(header)) + 4)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def run_from_command(command: Any, kind: str, path: str, *, user: Any, **options: Any) -> None:
    """Shared body of the import_* management commands: report, and fail on errors."""
    from pathlib import Path

    from django.core.management.base import CommandError

    file = Path(path)
    if not file.exists():
        raise CommandError(f"No file '{path}'.")
    result = run_import(kind, file.read_bytes(), name=file.name, user=user, **options)
    if result.needs_columns:
        raise CommandError(f"{result.problem} Headers seen: {', '.join(result.headers)}")
    for message in result.warnings:
        where = f"{message.sheet} " if message.sheet else ""
        command.stdout.write(f"note {where}row {message.row}: {message.message}")
    for message in result.errors:
        where = f"{message.sheet} " if message.sheet else ""
        command.stderr.write(f"{where}row {message.row}: {message.message}")
    if result.errors:
        raise CommandError(f"{len(result.errors)} row(s) have problems; nothing was saved.")
    summary = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in result.summary.items())
    command.stdout.write(
        command.style.SUCCESS(
            f"{'Dry run (nothing saved): ' if result.dry_run else ''}"
            f"{result.created} added, {result.updated} updated, {result.skipped} skipped"
            f"{f'; {summary}' if summary else ''}."
        )
    )
