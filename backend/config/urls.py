from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.permissions import IsOwnerForDocs

api_v1 = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.customers.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.orders.urls")),
    path("", include("apps.production.urls")),
    path("", include("apps.inventory.urls")),
    path("", include("apps.billing.urls")),
    path("", include("apps.reports.urls")),
    path("", include("apps.system.urls")),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[IsOwnerForDocs]),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[IsOwnerForDocs]),
        name="swagger-ui",
    ),
]

if settings.DEBUG:
    # Development only (Caddy serves media in production). Never the private folder.
    urlpatterns += [
        re_path(
            r"^media/(?!private/)(?P<path>.+)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        )
    ]

# API clients always get JSON errors, even for addresses no view handles.
handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
