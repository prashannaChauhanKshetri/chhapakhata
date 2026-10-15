from django.contrib import admin

from .models import Job, JobStageEvent


class JobStageEventInline(admin.TabularInline):
    model = JobStageEvent
    extra = 0
    readonly_fields = ["from_stage", "to_stage", "note", "created_by", "created_at"]
    can_delete = False


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["job_no", "order", "stage", "deadline", "operator", "material_recorded"]
    list_filter = ["stage", "priority"]
    search_fields = ["job_no", "order__order_no"]
    inlines = [JobStageEventInline]
