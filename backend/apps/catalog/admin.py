from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import AddOn, MediaType


@admin.register(MediaType)
class MediaTypeAdmin(SimpleHistoryAdmin):
    list_display = [
        "name",
        "pricing_unit",
        "rate",
        "min_sqft",
        "material",
        "is_active",
        "sort_order",
    ]
    list_editable = ["sort_order"]


@admin.register(AddOn)
class AddOnAdmin(SimpleHistoryAdmin):
    list_display = ["name", "basis", "rate", "default_quantity", "is_active"]
