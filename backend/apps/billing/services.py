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
from apps.core.dates import bs_string, local_today
from apps.core.exceptions import BusinessError
from apps.core.money import amount_in_words, fmt_qty, q2
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
        details = f"{item.size_label} × {item.quantity} pcs"
        if item.min_applied:
            details += f" (min. {fmt_qty(item.min_sqft)} sq ft each)"
        lines.append(
            InvoiceLine(
                invoice=invoice,
                line_no=line_no,
                description=description[:200],
                details=details[:200],
                quantity=q2(item.billable_sqft * item.quantity),
                unit="sq ft",
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


@transaction.atomic
def void_payment(*, payment: Payment, user: Any, reason: str, request: Any = None) -> Payment:
    """Void a payment entered by mistake or a bounced cheque. The ledger is reversed."""
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
        entry_date=local_today(),
        entry_type=LedgerEntryType.PAYMENT_VOID,
        debit=payment.amount,
        payment=payment,
        narration=f"Payment {payment.receipt_no} voided: {reason}"[:255],
        created_by=user,
    )
    log_activity(user, "payment.voided", payment, message=reason, request=request)
    return payment


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
