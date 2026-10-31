"""Invoices, payments and the customer ledger.

Rules that follow Nepal IRD billing practice:

* Invoices are never deleted. They are cancelled with a reason and stay
  viewable and printable.
* Invoice numbers run in order and restart each fiscal year.
* Every print after the first is marked "Copy of Original" with the count.
* Invoices show both BS (Miti) and AD dates and snapshot the buyer's details.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.dates import local_today
from apps.tenancy.models import BusinessOwned

MONEY = {"max_digits": 12, "decimal_places": 2, "default": Decimal("0.00")}


class InvoiceStatus(models.TextChoices):
    ISSUED = "issued", "Issued"
    CANCELLED = "cancelled", "Cancelled"


class Invoice(BusinessOwned):
    invoice_no = models.CharField(max_length=40)
    fiscal_year = models.CharField(max_length=7, db_index=True)
    sequence = models.PositiveIntegerField()
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="invoices")
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="invoices"
    )

    # Buyer snapshot, so later edits to the customer never change an issued bill.
    customer_name = models.CharField(max_length=150)
    customer_address = models.CharField(max_length=255, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_pan = models.CharField(max_length=9, blank=True)

    invoice_date = models.DateField(default=local_today, db_index=True)
    invoice_date_bs = models.CharField(max_length=10)
    is_vat_invoice = models.BooleanField(default=False)

    subtotal = models.DecimalField(**MONEY)
    discount_amount = models.DecimalField(**MONEY)
    taxable_amount = models.DecimalField(**MONEY)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    vat_amount = models.DecimalField(**MONEY)
    round_off = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)
    amount_in_words = models.CharField(max_length=255)
    notes = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=10, choices=InvoiceStatus.choices, default=InvoiceStatus.ISSUED, db_index=True
    )
    cancel_reason = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    print_count = models.PositiveIntegerField(default=0)
    last_printed_at = models.DateTimeField(null=True, blank=True)

    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="invoices_issued"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-invoice_date", "-sequence"]
        constraints = [
            models.UniqueConstraint(fields=["business", "invoice_no"], name="uniq_invoice_no"),
            models.UniqueConstraint(
                fields=["business", "fiscal_year", "sequence"], name="uniq_invoice_fy_seq"
            ),
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(status="issued"),
                name="one_issued_invoice_per_order",
            ),
        ]

    def __str__(self) -> str:
        return self.invoice_no

    @property
    def is_cancelled(self) -> bool:
        return self.status == InvoiceStatus.CANCELLED


class InvoiceLine(BusinessOwned):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=200)
    details = models.CharField(max_length=200, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit = models.CharField(max_length=12)
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(**MONEY)
    # Reporting fields (material vs sales, sales by media)
    media_type = models.ForeignKey(
        "catalog.MediaType", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    sqft = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    billable_sqft = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    class Meta:
        ordering = ["invoice", "line_no"]

    def __str__(self) -> str:
        return f"{self.invoice.invoice_no} #{self.line_no}"


class PaymentMode(models.TextChoices):
    CASH = "cash", "Cash"
    BANK = "bank", "Bank transfer"
    CHEQUE = "cheque", "Cheque"
    WALLET = "wallet", "QR / Wallet"


class Wallet(models.TextChoices):
    ESEWA = "esewa", "eSewa"
    KHALTI = "khalti", "Khalti"
    FONEPAY = "fonepay", "Fonepay"
    OTHER_QR = "other_qr", "Other QR"


class PaymentStatus(models.TextChoices):
    VALID = "valid", "Valid"
    VOID = "void", "Void"


class Payment(BusinessOwned):
    receipt_no = models.CharField(max_length=40)
    fiscal_year = models.CharField(max_length=7)
    sequence = models.PositiveIntegerField()
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="payments"
    )
    order = models.ForeignKey(
        "orders.Order", null=True, blank=True, on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    mode = models.CharField(max_length=10, choices=PaymentMode.choices)
    wallet = models.CharField(max_length=10, choices=Wallet.choices, blank=True)
    bank_name = models.CharField(max_length=80, blank=True)
    reference_no = models.CharField("Reference / transaction no.", max_length=60, blank=True)
    cheque_no = models.CharField(max_length=30, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    payment_date = models.DateField(default=local_today, db_index=True)
    is_advance = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.VALID, db_index=True
    )
    void_reason = models.CharField(max_length=255, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["business", "receipt_no"], name="uniq_receipt_no"),
            models.UniqueConstraint(
                fields=["business", "fiscal_year", "sequence"], name="uniq_receipt_fy_seq"
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="payment_amount_positive"
            ),
        ]

    def __str__(self) -> str:
        return self.receipt_no

    @property
    def mode_label(self) -> str:
        if self.mode == PaymentMode.WALLET and self.wallet:
            return self.get_wallet_display()
        return self.get_mode_display()


class LedgerEntryType(models.TextChoices):
    OPENING = "opening", "Opening balance"
    INVOICE = "invoice", "Invoice"
    INVOICE_CANCEL = "invoice_cancel", "Invoice cancelled"
    PAYMENT = "payment", "Payment received"
    PAYMENT_VOID = "payment_void", "Payment voided"
    ADJUSTMENT = "adjustment", "Adjustment"
    IMPORTED_WORK = "imported_work", "Work (imported)"


class LedgerEntry(BusinessOwned):
    """Append-only customer ledger. Balance = sum(debit) - sum(credit); positive means due."""

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="ledger_entries"
    )
    entry_date = models.DateField(default=local_today)
    entry_type = models.CharField(max_length=20, choices=LedgerEntryType.choices)
    debit = models.DecimalField(**MONEY)
    credit = models.DecimalField(**MONEY)
    invoice = models.ForeignKey(
        Invoice, null=True, blank=True, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    payment = models.ForeignKey(
        Payment, null=True, blank=True, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
        help_text="Set for work charged without an invoice (imported history).",
    )
    narration = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["entry_date", "id"]
        indexes = [
            models.Index(fields=["customer", "entry_date", "id"], name="ledger_customer_date"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name="ledger_amounts_non_negative",
            ),
        ]
        verbose_name_plural = "ledger entries"

    def __str__(self) -> str:
        return f"{self.entry_date} {self.get_entry_type_display()} {self.debit or -self.credit}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("Ledger entries cannot be edited. Post an adjustment instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Ledger entries cannot be deleted. Post an adjustment instead.")
