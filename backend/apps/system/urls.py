from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.include_root_view = False
router.register("system/backups", views.BackupRunViewSet, basename="backup")

urlpatterns = [
    path("system/export/", views.DataExportView.as_view(), name="data-export"),
    path("system/work-log/import/", views.WorkLogImportView.as_view(), name="work-log-import"),
    path("system/work-log/export/", views.WorkLogExportView.as_view(), name="work-log-export"),
    path(
        "system/work-log/template/", views.WorkLogTemplateView.as_view(), name="work-log-template"
    ),
    *router.urls,
]
