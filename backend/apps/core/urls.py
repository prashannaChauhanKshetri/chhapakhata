from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register("activity", views.ActivityLogViewSet, basename="activity")

urlpatterns = [
    path("settings/shop/", views.ShopSettingsView.as_view(), name="shop-settings"),
    path("utils/date/", views.DateConversionView.as_view(), name="date-conversion"),
    path("utils/periods/", views.PeriodsView.as_view(), name="periods"),
    path("health/", views.HealthView.as_view(), name="health"),
    *router.urls,
]
