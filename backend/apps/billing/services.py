"""Invoices, payments and ledger postings.

Every money event writes exactly one append-only ledger row, so a customer's
balance is always ``sum(debit) - sum(credit)`` over their ledger.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import AddOnBasis
from apps.catalog.pricing import perimeter_ft
from apps.core.activity import log_activity
from apps.core.dates import bs_string, fiscal_year_for, fiscal_year_range, local_today
from apps.core.exceptions import BusinessError
from apps.core.money import amount_in_words, fmt_qty, format_npr, q2
from apps.core.sequences import DocType, next_number
from apps.orders.models import Order, OrderStatus

from .models import (
    Invoice,
    InvoiceLine,
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


@transaction.atomic
def issue_invoice(*, order: Order, user: Any, notes: str = "", request: Any = None) -> Invoice:
    """Issue the tax invoice for a confirmed order, dated today."""
    order = Order.objects.select_for_update().select_related("customer").get(pk=order.pk)
    if order.status == OrderStatus.QUOTATION:
        raise BusinessError("Confirm the order before issuing an invoice.")
    if order.status == OrderStatus.CANCELLED:
        raise BusinessError("A cancelled order cannot be invoiced.")
    existing = order.invoices.filter(status=InvoiceStatus.ISSUED).first()
    if existing is not None:
        raise BusinessError(f"This order already has invoice {existing.invoice_no}.")
    if order.total <= 0:
        raise BusinessError("The order total is zero; there is nothing to invoice.")

    today = local_today()
    allocated = next_number(DocType.INVOICE, today)
    customer = order.customer
    invoice = Invoice.objects.create(
        invoice_no=allocated.number,
        fiscal_year=allocated.fiscal_year,
        sequence=allocated.sequence,
        order=order,
        customer=customer,
        customer_name=customer.name,
        customer_address=customer.address,
        customer_phone=customer.phone,
        customer_pan=customer.pan_no,
        invoice_date=today,
        invoice_date_bs=bs_string(today) or "",
        is_vat_invoice=order.vat_rate > 0,
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        taxable_amount=order.taxable_amount,
        vat_rate=order.vat_rate,
        vat_amount=order.vat_amount,
        round_off=order.round_off,
        total=order.total,
        amount_in_words=amount_in_words(order.total),
        notes=notes,
        issued_by=user,
    )

    line_no = 0
    lines = []
    for item in order.items.prefetch_related("addons").order_by("line_no"):
        line_no += 1
        description = item.media_name + (f" – {item.description}" if item.description else "")
        if item.is_per_piece:
            details = item.size_label
            quantity, unit = q2(Decimal(item.quantity)), "pcs"
        else:
            details = f"{item.size_label} × {item.quantity} pcs"
            if item.min_applied:
                details += f" (min. {fmt_qty(item.min_sqft)} sq ft each)"
            quantity, unit = q2(item.billable_sqft * item.quantity), "sq ft"
        lines.append(
            InvoiceLine(
                invoice=invoice,
                line_no=line_no,
                description=description[:200],
                details=details[:200],
                quantity=quantity,
                unit=unit,
                rate=item.rate,
                amount=item.base_amount,
                media_type_id=item.media_type_id,
                sqft=q2(item.sqft * item.quantity),
                billable_sqft=q2(item.billable_sqft * item.quantity),
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
    InvoiceLine.objects.bulk_create(lines)

    LedgerEntry.objects.create(
        customer=customer,
        entry_date=today,
        entry_type=LedgerEntryType.INVOICE,
        debit=invoice.total,
        invoice=invoice,
        narration=f"Invoice {invoice.invoice_no} for order {order.order_no}",
        created_by=user,
    )
    log_activity(user, "invoice.issued", invoice, message=f"Total {invoice.total}", request=request)
    return invoice


@transaction.atomic
def cancel_invoice(*, invoice: Invoice, user: Any, reason: str, request: Any = None) -> Invoice:
    """Cancel (never delete) an invoice. The number stays used; the ledger is reversed."""
    reason = _require_reason(reason)
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == InvoiceStatus.CANCELLED:
        raise BusinessError("This invoice is already cancelled.")
    invoice.status = InvoiceStatus.CANCELLED
    invoice.cancel_reason = reason
    invoice.cancelled_at = timezone.now()
    invoice.cancelled_by = user
    invoice.save(update_fields=["status", "cancel_reason", "cancelled_at", "cancelled_by"])
    LedgerEntry.objects.create(
        customer_id=invoice.customer_id,
        entry_date=local_today(),
        entry_type=LedgerEntryType.INVOICE_CANCEL,
        credit=invoice.total,
        invoice=invoice,
        narration=f"Invoice {invoice.invoice_no} cancelled: {reason}"[:255],
        created_by=user,
    )
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
    request: Any = None,
) -> Payment:
    """Record money received, against an order (advance or settlement) or on account."""
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
