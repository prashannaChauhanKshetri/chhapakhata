from django.contrib import admin

from .models import Purchase, PurchaseLine, Roll, StockItem, StockMovement, Supplier


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "unit", "on_hand", "low_stock_level", "is_active"]
    list_filter = ["kind", "is_active"]
    readonly_fields = ["on_hand"]


@admin.register(Roll)
class RollAdmin(admin.ModelAdmin):
    list_display = ["code", "stock_item", "width_ft", "length_ft", "remaining_sqft", "status"]
    list_filter = ["status", "stock_item"]
    readonly_fields = ["remaining_sqft", "total_sqft"]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "is_active"]


class PurchaseLineInline(admin.TabularInline):
    model = PurchaseLine
    extra = 0
    can_delete = False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ["purchase_no", "purchase_date", "supplier", "total_amount"]
    inlines = [PurchaseLineInline]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "stock_item",
        "roll",
        "movement_type",
        "quantity",
        "balance_after",
    ]
    list_filter = ["movement_type", "stock_item"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
