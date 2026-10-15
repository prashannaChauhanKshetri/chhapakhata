from django.contrib import admin

from .models import BackupRun


@admin.register(BackupRun)
class BackupRunAdmin(admin.ModelAdmin):
    list_display = ["started_at", "status", "trigger", "size_bytes", "offsite_status"]
    list_filter = ["status", "offsite_status"]
