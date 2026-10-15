from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(SimpleHistoryAdmin):
    list_display = ["name", "phone", "pan_no", "customer_type", "is_active"]
    list_filter = ["customer_type", "is_active"]
    search_fields = ["name", "phone", "pan_no"]
