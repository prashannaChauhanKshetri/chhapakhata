from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.include_root_view = False
router.register("staff", views.StaffViewSet, basename="staff")
router.register("staff-advances", views.StaffAdvanceViewSet, basename="staff-advance")
router.register("salary-payments", views.SalaryPaymentViewSet, basename="salary-payment")

urlpatterns = [
    path("attendance/", views.AttendanceView.as_view(), name="attendance"),
    path("attendance/month/", views.AttendanceMonthView.as_view(), name="attendance-month"),
    path("salary/", views.SalaryView.as_view(), name="salary"),
    path("salary/pay/", views.PaySalaryView.as_view(), name="salary-pay"),
    path("salary/months/", views.SalaryMonthsView.as_view(), name="salary-months"),
    *router.urls,
]
