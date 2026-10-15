from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.include_root_view = False
router.register("stock-items", views.StockItemViewSet, basename="stock-item")
router.register("rolls", views.RollViewSet, basename="roll")
router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("purchases", views.PurchaseViewSet, basename="purchase")
router.register("stock-movements", views.StockMovementViewSet, basename="stock-movement")

urlpatterns = router.urls
