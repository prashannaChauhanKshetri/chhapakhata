from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Order, OrderItem, OrderItemAddOn


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ["line_no", "media_name", "width", "height", "unit", "quantity", "rate", "line_total"]
    readonly_fields = fields
    can_delete = False


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = ["order_no", "customer", "status", "order_date", "total"]
    list_filter = ["status", "is_urgent"]
    search_fields = ["order_no", "customer__name", "customer__phone"]
    inlines = [OrderItemInline]

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(OrderItemAddOn)
