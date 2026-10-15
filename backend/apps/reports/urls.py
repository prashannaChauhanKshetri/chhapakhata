from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("reports/", views.ReportListView.as_view(), name="report-list"),
    path("reports/<slug:slug>/", views.ReportView.as_view(), name="report"),
]
