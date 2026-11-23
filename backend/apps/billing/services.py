"""Invoices, payments and ledger postings.

Every money event writes exactly one append-only ledger row, so a customer's
balance is always ``sum(debit) - sum(credit)`` over their ledger.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import AddOnBasis
from apps.catalog.pricing import perimeter_ft
from apps.core.activity import log_activity
from apps.core.dates import bs_string, fiscal_year_for, fiscal_year_range, local_today
from apps.core.exceptions import BusinessError
from apps.core.models import ShopSettings
from apps.core.money import amount_in_words, fmt_qty, format_npr, q2
from apps.core.sequences import DocType, next_number
from apps.orders.models import Order, OrderSource, OrderStatus

from .models import (
    Invoice,
    InvoiceLine,
    InvoiceOrder,
    InvoiceStatus,
    LedgerEntry,
    LedgerEntryType,
    Payment,
    PaymentMode,
    PaymentStatus,
)

MIN_REASON_LENGTH = 5


def _require_reason(reason: str) -> str:
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON_LENGTH:
        raise BusinessError({"reason": ["Write a short reason (at least 5 characters)."]})
    return reason


def _addon_line(addon: Any, item: Any) -> dict[str, Any]:
    """Present an add-on as an invoice line whose quantity × rate equals its amount."""
    qty = item.quantity
    match addon.basis:
        case AddOnBasis.PER_PIECE:
            quantity = q2(addon.quantity * qty)
            return {
                "quantity": quantity,
                "unit": "pcs",
                "rate": addon.rate,
                "details": f"{fmt_qty(addon.quantity)} per piece × {qty}",
            }
        case AddOnBasis.PER_SQFT:
            return {
                "quantity": q2(item.sqft * qty),
                "unit": "sq ft",
                "rate": addon.rate,
                "details": "Charged on actual size",
            }
        case AddOnBasis.PER_RUNNING_FT:
            perimeter = perimeter_ft(item.width, item.height, item.unit)
            return {
                "quantity": q2(perimeter * qty),
                "unit": "rft",
                "rate": addon.rate,
                "details": f"Perimeter {perimeter} ft × {qty}",
            }
        case AddOnBasis.PERCENT:
            return {
                "quantity": Decimal("1"),
                "unit": "",
                "rate": addon.amount,
                "details": f"{fmt_qty(addon.rate)}% of print amount",
            }
        case _:
            return {
                "quantity": q2(addon.quantity),
                "unit": "nos",
                "rate": addon.rate,
                "details": "",
            }


@dataclass(frozen=True)
class BillTotals:
    add_vat: bool
    subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    round_off: Decimal
    total: Decimal


def default_add_vat(customer: Any, orders: list[Order]) -> bool:
    """Counter orders that agree keep their choice; otherwise the customer's setting."""
    counter = {o.vat_rate > 0 for o in orders if o.source != OrderSource.IMPORT}
    if len(counter) == 1 and all(o.source != OrderSource.IMPORT for o in orders):
        return counter.pop()
    return bool(customer.add_vat) and ShopSettings.load().is_vat_registered


def bill_totals(customer: Any, orders: list[Order], add_vat: bool | None = None) -> BillTotals:
    """Totals for a bill over ``orders``. VAT is worked out once, on the net amount.

    Each order counts at its amount before VAT (sub-total less discount), so VAT an
    order already showed is never taxed again.
    """
    shop = ShopSettings.load()
    explicit = add_vat is not None
    if add_vat is None:
        add_vat = default_add_vat(customer, orders)
    subtotal = q2(sum((o.subtotal for o in orders), Decimal("0")))
    discount = q2(sum((o.discount_amount for o in orders), Decimal("0")))
    taxable = q2(subtotal - discount)
    rate = Decimal("0")
    if add_vat:
        rates = {o.vat_rate for o in orders if o.vat_rate > 0}
        if len(rates) == 1:
            rate = rates.pop()
        elif shop.is_vat_registered:
            rate = shop.vat_rate
        elif explicit:
            raise BusinessError({"add_vat": ["The shop is not VAT-registered (Settings → Shop)."]})
    vat = q2(taxable * rate / 100)
    total = q2(taxable + vat)
    round_off = Decimal("0")
    if shop.round_total_to_rupee:
        rounded = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        round_off, total = q2(rounded - total), q2(rounded)
    return BillTotals(
        add_vat=vat > 0,
        subtotal=subtotal,
        discount_amount=discount,
        taxable_amount=taxable,
        vat_rate=q2(rate),
        vat_amount=vat,
        round_off=round_off,
        total=total,
    )


def billable_orders(customer: Any, orders: Any, *, lock: bool = False) -> list[Order]:
    """The orders as they will be billed, oldest first. Raises if any cannot be billed."""
    ids = list(dict.fromkeys(o.pk if isinstance(o, Order) else int(o) for o in orders))
    if not ids:
        raise BusinessError({"orders": ["Choose at least one order."]})
    qs = Order.objects.filter(pk__in=ids)
    if lock:
        qs = qs.select_for_update()
    found = sorted(qs, key=lambda o: (o.order_date, o.pk))
    if len(found) != len(ids):
        raise BusinessError({"orders": ["An order was not found."]})
    problems = []
    for order in found:
        if order.customer_id != customer.pk:
            problems.append(f"{order.order_no} is another customer's order.")
        elif order.status == OrderStatus.QUOTATION:
            problems.append(f"{order.order_no} is a quotation; confirm it first.")
        elif order.status == OrderStatus.CANCELLED:
            problems.append(f"{order.order_no} is cancelled.")
    billed = (
        InvoiceOrder.objects.filter(order_id__in=ids, is_active=True)
        .select_related("invoice", "order")
        .order_by("order__order_no")
    )
    problems += [
        f"{link.order.order_no} is already on bill {link.invoice.invoice_no}." for link in billed
    ]
    if problems:
        raise BusinessError({"orders": problems})
    if sum((o.total for o in found), Decimal("0")) <= 0:
        raise BusinessError({"orders": ["These orders total zero; there is nothing to bill."]})
    return found


#: Ledger lines that keep an order's work on the account until it is billed.
ON_ACCOUNT_TYPES = (
    LedgerEntryType.IMPORTED_WORK,
    LedgerEntryType.ORDER_CHARGE,
    LedgerEntryType.WORK_BILLED,
)


def work_on_account(order: Order) -> Decimal:
    """What an order has charged to the account and not yet moved to a bill."""
    entries = order.ledger_entries.filter(entry_type__in=ON_ACCOUNT_TYPES)
    net = sum((e.debit - e.credit for e in entries), Decimal("0"))
    return q2(net)


def sync_order_charge(
    order: Order, user: Any, *, entry_date: dt.date | None = None, why: str = ""
) -> LedgerEntry | None:
    """Keep a confirmed order's total on the customer's account until it is billed.

    A confirmed order counts on the statement and in dues straight away; making a
    bill moves it onto the bill (see ``issue_bill``). Editing the order posts the
    difference, cancelling takes it off. Quotations and billed orders carry nothing
    here; imported work-log orders are charged by the import itself.
    """
    if order.source == OrderSource.IMPORT:
        return None
    billed = order.invoices.filter(status=InvoiceStatus.ISSUED).exists()
    counts = order.status not in (OrderStatus.QUOTATION, OrderStatus.CANCELLED) and not billed
    change = q2((order.total if counts else Decimal("0")) - work_on_account(order))
    if change == 0:
        return None
    return LedgerEntry.objects.create(
        customer_id=order.customer_id,
        entry_date=entry_date or local_today(),
        entry_type=LedgerEntryType.ORDER_CHARGE,
        debit=change if change > 0 else Decimal("0"),
        credit=-change if change < 0 else Decimal("0"),
        order=order,
        narration=(f"Order {order.order_no}" + (f": {why}" if why else ""))[:255],
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )


def _bill_lines(invoice: Invoice, orders: list[Order]) -> list[InvoiceLine]:
    several = len(orders) > 1
    line_no = 0
    lines = []
    for order in orders:
        for item in order.items.prefetch_related("addons").order_by("line_no"):
            line_no += 1
            # Size and pieces print in their own columns; Details holds the rest.
            notes = [order.order_no if several else "", item.description, item.finishing]
            if item.is_per_piece:
                quantity, unit = q2(Decimal(item.quantity)), "pcs"
            else:
                if item.min_applied:
                    notes.append(f"min. {fmt_qty(item.min_sqft)} sq ft each")
                quantity, unit = q2(item.billable_sqft * item.quantity), "sq ft"
            lines.append(
                InvoiceLine(
                    invoice=invoice,
                    line_no=line_no,
                    description=item.media_name[:200],
                    details=" · ".join(x for x in notes if x)[:200],
                    quantity=quantity,
                    unit=unit,
                    rate=item.rate,
                    amount=item.base_amount,
                    media_type_id=item.media_type_id,
                    sqft=q2(item.sqft * item.quantity),
                    billable_sqft=q2(item.billable_sqft * item.quantity),
                    width=item.width if item.has_size else None,
                    height=item.height if item.has_size else None,
                    size_unit=item.unit if item.has_size else "",
                    pieces=item.quantity,
                    per_piece=item.is_per_piece,
                )
            )
            for addon in item.addons.all():
                line_no += 1
                info = _addon_line(addon, item)
                lines.append(
                    InvoiceLine(
                        invoice=invoice,
                        line_no=line_no,
                        description=f"{addon.name} (item {item.line_no})"[:200],
                        details=info["details"][:200],
                        quantity=info["quantity"],
                        unit=info["unit"],
                        rate=info["rate"],
                        amount=addon.amount,
                    )
                )
    return lines


def orders_label(numbers: list[str]) -> str:
    if len(numbers) <= 3:
        return ", ".join(numbers)
    return f"{numbers[0]} to {numbers[-1]} ({len(numbers)} orders)"


@transaction.atomic
def issue_bill(
    *,
    customer: Any,
    orders: Any,
    user: Any,
    add_vat: bool | None = None,
    vat_note: str = "",
    notes: str = "",
    request: Any = None,
) -> Invoice:
    """Issue one tax invoice, dated today, for one or more of a customer's orders.

    ``add_vat`` None follows the orders (or the customer's setting). Work-log orders
    were charged to the account when imported: that charge moves onto the bill, so
    the account goes up only by the VAT.
    """
    from apps.customers.models import Customer

    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    found = billable_orders(customer, orders, lock=True)
    totals = bill_totals(customer, found, add_vat)
    today = local_today()
    allocated = next_number(DocType.INVOICE, today)
    invoice = Invoice.objects.create(
        invoice_no=allocated.number,
        fiscal_year=allocated.fiscal_year,
        sequence=allocated.sequence,
        order=found[0],
        customer=customer,
        customer_name=customer.name,
        customer_address=customer.address,
        customer_phone=customer.phone,
        customer_pan=customer.pan_no,
        invoice_date=today,
        invoice_date_bs=bs_string(today) or "",
        is_vat_invoice=totals.add_vat,
        subtotal=totals.subtotal,
        discount_amount=totals.discount_amount,
        taxable_amount=totals.taxable_amount,
        vat_rate=totals.vat_rate,
        vat_amount=totals.vat_amount,
        round_off=totals.round_off,
        total=totals.total,
        amount_in_words=amount_in_words(totals.total),
        notes=notes,
        vat_note="" if totals.add_vat else (vat_note or "").strip()[:255],
        issued_by=user,
    )
    InvoiceOrder.objects.bulk_create(InvoiceOrder(invoice=invoice, order=o) for o in found)
    InvoiceLine.objects.bulk_create(_bill_lines(invoice, found))

    numbers = [o.order_no for o in found]
    LedgerEntry.objects.create(
        customer=customer,
        entry_date=today,
        entry_type=LedgerEntryType.INVOICE,
        debit=invoice.total,
        invoice=invoice,
        narration=f"Invoice {invoice.invoice_no} for {orders_label(numbers)}"[:255],
        created_by=user,
    )
    for order in found:
        on_account = work_on_account(order)
        if on_account > 0:
            LedgerEntry.objects.create(
                customer=customer,
                entry_date=today,
                entry_type=LedgerEntryType.WORK_BILLED,
                credit=on_account,
                invoice=invoice,
                order=order,
                narration=f"{order.order_no} moved to bill {invoice.invoice_no}"[:255],
                created_by=user,
            )
    log_activity(
        user,
        "invoice.issued",
        invoice,
        message=f"Total {invoice.total} for {orders_label(numbers)}"
        + ("" if totals.add_vat else " (no VAT)"),
        request=request,
    )
    return invoice


def issue_invoice(
    *,
    order: Order,
    user: Any,
    notes: str = "",
    add_vat: bool | None = None,
    vat_note: str = "",
    request: Any = None,
) -> Invoice:
    """Issue the tax invoice for one confirmed order, dated today."""
    return issue_bill(
        customer=order.customer,
        orders=[order],
        user=user,
        add_vat=add_vat,
        vat_note=vat_note,
        notes=notes,
        request=request,
    )


@transaction.atomic
def cancel_invoice(*, invoice: Invoice, user: Any, reason: str, request: Any = None) -> Invoice:
    """Cancel (never delete) an invoice. The number stays used; the ledger is reversed.

    Its orders can be billed again, and their work goes back on the account.
    """
    reason = _require_reason(reason)
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == InvoiceStatus.CANCELLED:
        raise BusinessError("This invoice is already cancelled.")
    invoice.status = InvoiceStatus.CANCELLED
    invoice.cancel_reason = reason
    invoice.cancelled_at = timezone.now()
    invoice.cancelled_by = user
    invoice.save(update_fields=["status", "cancel_reason", "cancelled_at", "cancelled_by"])
    invoice.order_links.update(is_active=False)
    today = local_today()
    LedgerEntry.objects.create(
        customer_id=invoice.customer_id,
        entry_date=today,
        entry_type=LedgerEntryType.INVOICE_CANCEL,
        credit=invoice.total,
        invoice=invoice,
        narration=f"Invoice {invoice.invoice_no} cancelled: {reason}"[:255],
        created_by=user,
    )
    moved = invoice.ledger_entries.filter(entry_type=LedgerEntryType.WORK_BILLED).select_related(
        "order"
    )
    for entry in moved:
        LedgerEntry.objects.create(
            customer_id=invoice.customer_id,
            entry_date=today,
            entry_type=(
                LedgerEntryType.IMPORTED_WORK
                if entry.order.source == OrderSource.IMPORT
                else LedgerEntryType.ORDER_CHARGE
            ),
            debit=entry.credit,
            invoice=invoice,
            order=entry.order,
            narration=f"{entry.order.order_no} back on the account: bill "
            f"{invoice.invoice_no} cancelled"[:255],
            created_by=user,
        )
    # Bills made before confirmed orders counted on the account moved nothing; their
    # orders go back on the account here (for newer bills this changes nothing).
    for order in invoice.orders.all():
        sync_order_charge(order, user, why=f"bill {invoice.invoice_no} cancelled")
    log_activity(user, "invoice.cancelled", invoice, message=reason, request=request)
    return invoice


@transaction.atomic
def record_invoice_print(*, invoice: Invoice, user: Any, size: str, request: Any = None) -> int:
    """Count a print. Returns the new print count (1 = original, 2+ = copies)."""
    Invoice.objects.filter(pk=invoice.pk).update(
        print_count=F("print_count") + 1, last_printed_at=timezone.now()
    )
    invoice.refresh_from_db(fields=["print_count", "last_printed_at"])
    action = "invoice.printed" if invoice.print_count == 1 else "invoice.reprinted"
    log_activity(
        user,
        action,
        invoice,
        message=f"Print #{invoice.print_count} ({size})",
        request=request,
    )
    return invoice.print_count


REPEAT_WINDOW = dt.timedelta(minutes=2)


def _validate_mode(data: dict[str, Any]) -> None:
    mode = data.get("mode")
    errors: dict[str, list[str]] = {}
    if mode == PaymentMode.CHEQUE:
        if not data.get("cheque_no"):
            errors["cheque_no"] = ["Enter the cheque number."]
        if not data.get("bank_name"):
            errors["bank_name"] = ["Enter the bank name."]
        if not data.get("cheque_date"):
            errors["cheque_date"] = ["Enter the cheque date."]
    elif mode == PaymentMode.BANK:
        if not data.get("bank_name"):
            errors["bank_name"] = ["Enter the bank name."]
    elif mode == PaymentMode.WALLET:
        if not data.get("wallet"):
            errors["wallet"] = ["Choose the wallet or QR app."]
    elif mode != PaymentMode.CASH:
        errors["mode"] = ["Choose a payment mode."]
    if errors:
        raise BusinessError(errors)


@transaction.atomic
def receive_payment(
    *,
    user: Any,
    customer: Any,
    amount: Decimal | str,
    mode: str,
    order: Order | None = None,
    wallet: str = "",
    bank_name: str = "",
    reference_no: str = "",
    cheque_no: str = "",
    cheque_date: dt.date | None = None,
    payment_date: dt.date | None = None,
    notes: str = "",
    allow_repeat: bool = False,
    request: Any = None,
) -> Payment:
    """Record money received, against an order (advance or settlement) or on account.

    The same payment saved again by the same person within two minutes (a
    double click, or a retry on a slow connection) is refused unless
    ``allow_repeat`` says it really is a second payment.
    """
    value = q2(amount)
    if value <= 0:
        raise BusinessError({"amount": ["Amount must be above zero."]})
    today = local_today()
    payment_date = payment_date or today
    if payment_date > today:
        raise BusinessError({"payment_date": ["A payment cannot be dated in the future."]})
    _validate_mode(
        {
            "mode": mode,
            "wallet": wallet,
            "bank_name": bank_name,
            "cheque_no": cheque_no,
            "cheque_date": cheque_date,
        }
    )

    if not allow_repeat:
        just_saved = (
            Payment.objects.filter(
                customer=customer,
                order=order,
                amount=value,
                mode=mode,
                payment_date=payment_date,
                received_by=user,
                status=PaymentStatus.VALID,
                created_at__gte=timezone.now() - REPEAT_WINDOW,
            )
            .order_by("-id")
            .first()
        )
        if just_saved is not None:
            raise BusinessError(
                {
                    "repeat": [
                        f"This payment was saved a moment ago as {just_saved.receipt_no}. "
                        "Save it again only if the customer paid twice."
                    ]
                }
            )

    is_advance = False
    if order is not None:
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.customer_id != customer.pk:
            raise BusinessError({"order": ["This order belongs to a different customer."]})
        if order.status == OrderStatus.QUOTATION:
            raise BusinessError({"order": ["Confirm the quotation before taking an advance."]})
        if order.status == OrderStatus.CANCELLED:
            raise BusinessError({"order": ["This order is cancelled."]})
        is_advance = not order.invoices.filter(status=InvoiceStatus.ISSUED).exists()

    allocated = next_number(DocType.RECEIPT, payment_date)
    payment = Payment.objects.create(
        receipt_no=allocated.number,
        fiscal_year=allocated.fiscal_year,
        sequence=allocated.sequence,
        customer=customer,
        order=order,
        amount=value,
        mode=mode,
        wallet=wallet if mode == PaymentMode.WALLET else "",
        bank_name=bank_name if mode in (PaymentMode.BANK, PaymentMode.CHEQUE) else "",
        reference_no=reference_no,
        cheque_no=cheque_no if mode == PaymentMode.CHEQUE else "",
        cheque_date=cheque_date if mode == PaymentMode.CHEQUE else None,
        payment_date=payment_date,
        is_advance=is_advance,
        notes=notes,
        received_by=user,
    )
    target = f" for order {order.order_no}" if order is not None else " on account"
    LedgerEntry.objects.create(
        customer=customer,
        entry_date=payment_date,
        entry_type=LedgerEntryType.PAYMENT,
        credit=value,
        payment=payment,
        narration=f"Payment {payment.receipt_no} ({payment.mode_label}){target}"[:255],
        created_by=user,
    )
    log_activity(
        user,
        "payment.received",
        payment,
        message=f"{value} by {payment.mode_label}{target}",
        request=request,
    )
    return payment


def find_recorded_payment(
    *,
    customer: Any,
    payment_date: dt.date,
    amount: Decimal,
    exclude: Any = (),
    only_entered: bool = False,
) -> Payment | None:
    """A valid payment already on record for this customer, day and amount.

    Imports use it so a payment that arrived another way (an order slip, the
    work log, typed in) is not recorded a second time. ``exclude`` holds
    payments already matched to another row; ``only_entered`` leaves out
    payments that came from a payments sheet.
    """
    found = Payment.objects.filter(
        customer=customer, payment_date=payment_date, amount=q2(amount), status=PaymentStatus.VALID
    ).exclude(pk__in=list(exclude))
    if only_entered:
        found = found.filter(import_ref="")
    return found.order_by("id").first()


def duplicate_sheet_payments() -> list[tuple[Payment, Payment]]:
    """Payments-sheet receipts that repeat a payment recorded another way.

    Each earlier payment matches at most one sheet receipt, so two real payments
    of the same amount on the same day are never both called duplicates.
    """
    pairs: list[tuple[Payment, Payment]] = []
    used: set[int] = set()
    sheet = Payment.objects.filter(status=PaymentStatus.VALID).exclude(import_ref="")
    left: list[Payment] = []
    for payment in sheet.select_related("customer").order_by("payment_date", "id"):
        original = find_recorded_payment(
            customer=payment.customer,
            payment_date=payment.payment_date,
            amount=payment.amount,
            exclude=used,
            only_entered=True,
        )
        if original is not None:
            used.add(original.pk)
            pairs.append((payment, original))
        else:
            left.append(payment)

    # The same day's total split differently (500 + 450 recorded, 950 in the sheet).
    by_day: dict[tuple[int, dt.date], list[Payment]] = {}
    for payment in left:
        by_day.setdefault((payment.customer_id, payment.payment_date), []).append(payment)
    for (customer_id, day), copies in by_day.items():
        entered = list(
            Payment.objects.filter(
                customer_id=customer_id,
                payment_date=day,
                status=PaymentStatus.VALID,
                import_ref="",
            )
            .exclude(pk__in=used)
            .order_by("id")
        )
        if entered and sum(p.amount for p in entered) == sum(p.amount for p in copies):
            used.update(p.pk for p in entered)
            pairs.extend((copy, entered[0]) for copy in copies)
    return pairs


def record_imported_payment(
    *,
    user: Any,
    customer: Any,
    amount: Decimal,
    mode: str,
    payment_date: dt.date,
    wallet: str = "",
    reference_no: str = "",
    notes: str = "",
    import_ref: str = "",
) -> Payment:
    """A payment received earlier and recorded from a sheet, on account.

    Like ``receive_payment`` (receipt number in the payment's fiscal year,
    ledger credit), but old records rarely kept cheque numbers or bank
    names, so those are not required.
    """
    value = q2(amount)
    if value <= 0:
        raise BusinessError({"amount": ["Amount must be above zero."]})
    if payment_date > local_today():
        raise BusinessError({"payment_date": ["A payment cannot be dated in the future."]})
    allocated = next_number(DocType.RECEIPT, payment_date)
    payment = Payment.objects.create(
        receipt_no=allocated.number,
        fiscal_year=allocated.fiscal_year,
        sequence=allocated.sequence,
        customer=customer,
        amount=value,
        mode=mode,
        wallet=wallet if mode == PaymentMode.WALLET else "",
        reference_no=reference_no[:60],
        payment_date=payment_date,
        notes=notes[:255],
        received_by=user,
        import_ref=import_ref,
    )
    LedgerEntry.objects.create(
        customer=customer,
        entry_date=payment_date,
        entry_type=LedgerEntryType.PAYMENT,
        credit=value,
        payment=payment,
        narration=f"Payment {payment.receipt_no} ({payment.mode_label}) on account"[:255],
        created_by=user,
    )
    return payment


@transaction.atomic
def void_payment(
    *,
    payment: Payment,
    user: Any,
    reason: str,
    request: Any = None,
    reverse_on: dt.date | None = None,
) -> Payment:
    """Void a payment entered by mistake or a bounced cheque. The ledger is reversed.

    The reversal is dated today (a cheque bounces later) unless ``reverse_on``
    says otherwise, e.g. the payment's own date for a payment that never happened.
    """
    reason = _require_reason(reason)
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == PaymentStatus.VOID:
        raise BusinessError("This payment is already void.")
    payment.status = PaymentStatus.VOID
    payment.void_reason = reason
    payment.voided_at = timezone.now()
    payment.voided_by = user
    payment.save(update_fields=["status", "void_reason", "voided_at", "voided_by"])
    LedgerEntry.objects.create(
        customer_id=payment.customer_id,
        entry_date=reverse_on or local_today(),
        entry_type=LedgerEntryType.PAYMENT_VOID,
        debit=payment.amount,
        payment=payment,
        narration=f"Payment {payment.receipt_no} voided: {reason}"[:255],
        created_by=user,
    )
    log_activity(user, "payment.voided", payment, message=reason, request=request)
    return payment


_KEEP: Any = object()  # "not given": keep the payment's current value


@transaction.atomic
def correct_payment(
    *,
    payment: Payment,
    user: Any,
    reason: str,
    customer: Any = _KEEP,
    order: Any = _KEEP,
    amount: Any = _KEEP,
    mode: Any = _KEEP,
    wallet: Any = _KEEP,
    bank_name: Any = _KEEP,
    reference_no: Any = _KEEP,
    cheque_no: Any = _KEEP,
    cheque_date: Any = _KEEP,
    payment_date: Any = _KEEP,
    notes: Any = _KEEP,
    request: Any = None,
) -> Payment:
    """Fix a payment entered wrongly: void it and record the corrected one, together.

    Nothing is overwritten. The wrong receipt stays on record as void ("Corrected
    by RCT-…"), reversed on its own date so that period's statement is right, and
    the corrected receipt gets a new number. Cheque and bank details are not
    required, since imported old payments rarely had them.
    """
    reason = _require_reason(reason)
    old = Payment.objects.select_for_update().get(pk=payment.pk)
    if old.status == PaymentStatus.VOID:
        raise BusinessError("This payment is void; it cannot be corrected.")

    def pick(value: Any, current: Any) -> Any:
        return current if value is _KEEP else value

    new_customer = pick(customer, old.customer)
    new_order = pick(order, old.order if new_customer.pk == old.customer_id else None)
    new = {
        "amount": q2(pick(amount, old.amount)),
        "mode": pick(mode, old.mode),
        "wallet": pick(wallet, old.wallet) or "",
        "bank_name": pick(bank_name, old.bank_name) or "",
        "reference_no": pick(reference_no, old.reference_no) or "",
        "cheque_no": pick(cheque_no, old.cheque_no) or "",
        "cheque_date": pick(cheque_date, old.cheque_date),
        "payment_date": pick(payment_date, old.payment_date) or old.payment_date,
        "notes": pick(notes, old.notes) or "",
    }
    unchanged = (
        new_customer.pk == old.customer_id
        and getattr(new_order, "pk", None) == old.order_id
        and all(new[k] == (getattr(old, k) or ("" if k != "cheque_date" else None)) for k in new)
    )
    if unchanged:
        raise BusinessError("Nothing was changed.")
    if new["amount"] <= 0:
        raise BusinessError({"amount": ["Amount must be above zero."]})
    if new["payment_date"] > local_today():
        raise BusinessError({"payment_date": ["A payment cannot be dated in the future."]})
    if new["mode"] not in PaymentMode.values:
        raise BusinessError({"mode": ["Choose a payment mode."]})
    if new["mode"] == PaymentMode.WALLET and not new["wallet"]:
        raise BusinessError({"wallet": ["Choose the wallet or QR app."]})
    is_advance = False
    if new_order is not None:
        new_order = Order.objects.select_for_update().get(pk=new_order.pk)
        if new_order.customer_id != new_customer.pk:
            raise BusinessError({"order": ["This order belongs to a different customer."]})
        is_advance = not new_order.invoices.filter(status=InvoiceStatus.ISSUED).exists()

    allocated = next_number(DocType.RECEIPT, new["payment_date"])
    mode_ = new["mode"]
    corrected = Payment.objects.create(
        receipt_no=allocated.number,
        fiscal_year=allocated.fiscal_year,
        sequence=allocated.sequence,
        customer=new_customer,
        order=new_order,
        amount=new["amount"],
        mode=mode_,
        wallet=new["wallet"] if mode_ == PaymentMode.WALLET else "",
        bank_name=new["bank_name"] if mode_ in (PaymentMode.BANK, PaymentMode.CHEQUE) else "",
        reference_no=new["reference_no"][:60],
        cheque_no=new["cheque_no"] if mode_ == PaymentMode.CHEQUE else "",
        cheque_date=new["cheque_date"] if mode_ == PaymentMode.CHEQUE else None,
        payment_date=new["payment_date"],
        is_advance=is_advance,
        notes=new["notes"][:255],
        received_by=old.received_by,  # who took the money; the corrector is in the log
    )
    target = f" for order {new_order.order_no}" if new_order is not None else " on account"
    LedgerEntry.objects.create(
        customer=new_customer,
        entry_date=corrected.payment_date,
        entry_type=LedgerEntryType.PAYMENT,
        credit=corrected.amount,
        payment=corrected,
        narration=f"Payment {corrected.receipt_no} ({corrected.mode_label}){target}, "
        f"corrects {old.receipt_no}"[:255],
        created_by=user,
    )

    old.status = PaymentStatus.VOID
    old.void_reason = f"Corrected by {corrected.receipt_no}: {reason}"[:255]
    old.voided_at = timezone.now()
    old.voided_by = user
    old.save(update_fields=["status", "void_reason", "voided_at", "voided_by"])
    LedgerEntry.objects.create(
        customer_id=old.customer_id,
        entry_date=old.payment_date,  # undo it where it was, so that period is right
        entry_type=LedgerEntryType.PAYMENT_VOID,
        debit=old.amount,
        payment=old,
        narration=f"Payment {old.receipt_no} corrected by {corrected.receipt_no}: {reason}"[:255],
        created_by=user,
    )
    log_activity(
        user,
        "payment.corrected",
        corrected,
        message=f"{old.receipt_no} → {corrected.receipt_no}: {reason}"[:255],
        metadata={"from": old.pk, "to": corrected.pk},
        request=request,
    )
    return corrected


@transaction.atomic
def post_opening_balance(
    *, customer: Any, amount: Decimal | str, user: Any, as_of: dt.date | None = None
) -> LedgerEntry | None:
    """Carry a customer's existing due (positive) or advance (negative) into the system."""
    value = q2(amount)
    if value == 0:
        return None
    if customer.ledger_entries.filter(entry_type=LedgerEntryType.OPENING).exists():
        raise BusinessError({"opening_balance": ["This customer already has an opening balance."]})
    return LedgerEntry.objects.create(
        customer=customer,
        entry_date=as_of or local_today(),
        entry_type=LedgerEntryType.OPENING,
        debit=value if value > 0 else Decimal("0"),
        credit=-value if value < 0 else Decimal("0"),
        narration="Opening balance",
        created_by=user,
    )


def previous_year_end(today: dt.date | None = None) -> dt.date:
    """Last day of the previous fiscal year (end of Asar), where carried-in balances sit.

    A balance dated there is this year's opening balance on every statement,
    not a new charge inside the year.
    """
    start, _ = fiscal_year_range(fiscal_year_for(today or local_today()))
    return start - dt.timedelta(days=1)


def opening_date(customer: Any) -> dt.date | None:
    """The day the customer's opening balance is dated, if they have one.

    Everything on or before that day is already inside the opening balance.
    """
    first = opening_entries(customer).first()
    return first.entry_date if first is not None else None


def opening_entries(customer: Any):
    return customer.ledger_entries.filter(entry_type=LedgerEntryType.OPENING).order_by(
        "entry_date", "id"
    )


def _signed(amount: Decimal) -> str:
    if amount == 0:
        return "nil"
    side = "due" if amount > 0 else "advance"
    return f"{format_npr(abs(amount))} {side}"


@transaction.atomic
def set_opening_balance(
    *,
    customer: Any,
    amount: Decimal | str,
    user: Any,
    as_of: dt.date | None = None,
    reason: str = "",
    request: Any = None,
) -> LedgerEntry:
    """Set or correct the balance a customer carried in from the previous year.

    Positive means the customer owes the shop; negative is an advance. The
    ledger stays append-only: the first time posts the opening entry (dated
    at the end of the previous fiscal year unless ``as_of`` says otherwise);
    a correction posts the difference on the same date, with a reason, so
    the history of every change stays visible.
    """
    customer = type(customer).objects.select_for_update().get(pk=customer.pk)
    target = q2(amount)
    if as_of is not None and as_of > local_today():
        raise BusinessError({"as_of": ["The date cannot be in the future."]})
    entries = list(opening_entries(customer))
    current = q2(sum((e.debit - e.credit for e in entries), Decimal("0")))
    if entries:
        reason = _require_reason(reason)
        if target == current:
            raise BusinessError({"amount": [f"The opening balance is already {_signed(current)}."]})
        if as_of is not None and as_of != entries[0].entry_date:
            raise BusinessError(
                {"as_of": ["A correction keeps the date of the first opening balance."]}
            )
        entry_date = entries[0].entry_date
        change = f"from {_signed(current)} to {_signed(target)}"
        narration = f"Opening balance changed {change}: {reason}"
    else:
        if target == 0:
            raise BusinessError({"amount": ["Enter the amount carried in from last year."]})
        entry_date = as_of or previous_year_end()
        reason = (reason or "").strip()
        narration = f"Opening balance: {reason}" if reason else "Opening balance"
    difference = target - current
    entry = LedgerEntry.objects.create(
        customer=customer,
        entry_date=entry_date,
        entry_type=LedgerEntryType.OPENING,
        debit=difference if difference > 0 else Decimal("0"),
        credit=-difference if difference < 0 else Decimal("0"),
        narration=narration[:255],
        created_by=user,
    )
    log_activity(
        user,
        "ledger.opening_changed" if entries else "ledger.opening_set",
        customer,
        message=f"{_signed(current)} → {_signed(target)}"[:255],
        metadata={"from": str(current), "to": str(target), "date": entry_date.isoformat()},
        request=request,
    )
    return entry


@transaction.atomic
def post_adjustment(
    *, customer: Any, amount: Decimal | str, narration: str, user: Any, request: Any = None
) -> LedgerEntry:
    """Owner-only correction. Positive increases what the customer owes."""
    value = q2(amount)
    if value == 0:
        raise BusinessError({"amount": ["Enter a non-zero amount."]})
    narration = _require_reason(narration)
    just_posted = LedgerEntry.objects.filter(
        customer=customer,
        entry_type=LedgerEntryType.ADJUSTMENT,
        debit=value if value > 0 else Decimal("0"),
        credit=-value if value < 0 else Decimal("0"),
        narration=narration[:255],
        created_by=user,
        created_at__gte=timezone.now() - REPEAT_WINDOW,
    ).exists()
    if just_posted:
        raise BusinessError("This adjustment was saved a moment ago; it was not posted twice.")
    entry = LedgerEntry.objects.create(
        customer=customer,
        entry_date=local_today(),
        entry_type=LedgerEntryType.ADJUSTMENT,
        debit=value if value > 0 else Decimal("0"),
        credit=-value if value < 0 else Decimal("0"),
        narration=narration[:255],
        created_by=user,
    )
    log_activity(
        user, "ledger.adjusted", customer, message=f"{value}: {narration}", request=request
    )
    return entry
