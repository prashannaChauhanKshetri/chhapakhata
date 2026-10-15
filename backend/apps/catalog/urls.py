from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.include_root_view = False
router.register("media-types", views.MediaTypeViewSet, basename="media-type")
router.register("addons", views.AddOnViewSet, basename="addon")

urlpatterns = router.urls
