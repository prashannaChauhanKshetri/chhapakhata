from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.include_root_view = False
router.register("system/backups", views.BackupRunViewSet, basename="backup")

urlpatterns = [
    path("system/export/", views.DataExportView.as_view(), name="data-export"),
    *router.urls,
]
