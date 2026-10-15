"""Read-only admin views. Billing records change only through services."""

from django.contrib import admin

from .models import Invoice, InvoiceLine, LedgerEntry, Payment


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    can_delete = False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(ReadOnlyAdmin):
    list_display = ["invoice_no", "invoice_date", "customer_name", "total", "status", "print_count"]
    list_filter = ["status", "fiscal_year"]
    search_fields = ["invoice_no", "customer_name"]
    inlines = [InvoiceLineInline]


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAdmin):
    list_display = ["receipt_no", "payment_date", "customer", "amount", "mode", "status"]
    list_filter = ["mode", "status"]
    search_fields = ["receipt_no", "customer__name"]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(ReadOnlyAdmin):
    list_display = ["entry_date", "customer", "entry_type", "debit", "credit", "narration"]
    list_filter = ["entry_type"]
    search_fields = ["customer__name", "narration"]
