from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import ActivityLog, DocumentSequence, ShopSettings


@admin.register(ShopSettings)
class ShopSettingsAdmin(SimpleHistoryAdmin):
    list_display = ["name", "is_vat_registered", "vat_rate", "default_min_sqft", "updated_at"]


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ["doc_type", "fiscal_year", "last_number"]
    readonly_fields = ["doc_type", "fiscal_year", "last_number"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "target_label", "message"]
    list_filter = ["action"]
    search_fields = ["target_label", "message"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
