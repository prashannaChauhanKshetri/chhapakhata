from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "get_full_name", "role", "is_active", "last_login"]
    list_filter = ["role", "is_active"]
    fieldsets = (
        *BaseUserAdmin.fieldsets,
        ("Shop role", {"fields": ("role", "phone", "max_discount_percent")}),
    )
