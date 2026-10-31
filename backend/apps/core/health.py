"""Health check shared by the API endpoint and the container's own probe."""

from __future__ import annotations

from django.db import connection
from django.http import JsonResponse

HEALTH_PATH = "/api/v1/health/"
LOOPBACK = {"127.0.0.1", "::1"}


def health_status() -> tuple[dict[str, str], int]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    body = {"status": "ok" if db_status == "ok" else "degraded", "database": db_status}
    return body, 200 if db_status == "ok" else 503


class LocalHealthCheckMiddleware:
    """Answer the container's own health probe before host validation.

    Docker's healthcheck and the install script call
    ``http://localhost:8000/api/v1/health/`` from inside the container, which
    is not one of the site's ``ALLOWED_HOSTS``. Only loopback requests are
    answered here; anything arriving through Caddy goes through the normal
    middleware (and host checks) to the same check in ``HealthView``.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH and request.META.get("REMOTE_ADDR") in LOOPBACK:
            body, status = health_status()
            return JsonResponse(body, status=status)
        return self.get_response(request)
