"""Rate limits, the visitor's real address behind the proxy, and upload limits."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, override_settings
from rest_framework.test import APIRequestFactory

from apps.core.client_ip import RealClientIPMiddleware
from apps.core.throttling import BackupThrottle, HeavyThrottle, is_heavy

pytestmark = pytest.mark.django_db

CADDY = "172.18.0.4"  # the proxy on the Docker network


# -- The visitor's address -------------------------------------------------------------


def _remote(meta: dict) -> str:
    request = RequestFactory().get("/", **meta)
    RealClientIPMiddleware(lambda r: r)(request)
    return request.META["REMOTE_ADDR"]


def test_the_address_given_by_the_proxy_is_used():
    assert _remote({"REMOTE_ADDR": CADDY, "HTTP_X_REAL_IP": "27.34.68.10"}) == "27.34.68.10"
    assert _remote({"REMOTE_ADDR": "127.0.0.1", "HTTP_X_REAL_IP": "2400:1a00::1"}) == "2400:1a00::1"


def test_nobody_outside_can_choose_their_own_address():
    # Straight to Django from the internet: the header is ignored.
    assert _remote({"REMOTE_ADDR": "27.34.68.10", "HTTP_X_REAL_IP": "1.2.3.4"}) == "27.34.68.10"
    # Rubbish in the header is ignored too.
    assert _remote({"REMOTE_ADDR": CADDY, "HTTP_X_REAL_IP": "1.2.3.4, 5.6.7.8"}) == CADDY


def _csrf_client() -> tuple[Client, str]:
    client = Client(enforce_csrf_checks=True)
    client.get("/api/v1/auth/csrf/")
    return client, client.cookies["csrftoken"].value


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
def test_a_lockout_holds_one_address_not_everyone(desk):
    """Behind Cloudflare everyone used to share an address: one attacker locked out all."""
    attacker, token = _csrf_client()
    for _ in range(3):
        attacker.post(
            "/api/v1/auth/login/",
            {"username": "desk", "password": "guess"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            REMOTE_ADDR=CADDY,
            HTTP_X_REAL_IP="45.12.1.1",
        )
    blocked = attacker.post(
        "/api/v1/auth/login/",
        {"username": "desk", "password": "Test@12345"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
        REMOTE_ADDR=CADDY,
        HTTP_X_REAL_IP="45.12.1.1",
    )
    assert blocked.status_code == 429
    # The real member of staff, from the shop's own address, still gets in.
    shop, token = _csrf_client()
    allowed = shop.post(
        "/api/v1/auth/login/",
        {"username": "desk", "password": "Test@12345"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
        REMOTE_ADDR=CADDY,
        HTTP_X_REAL_IP="27.34.68.10",
    )
    assert allowed.status_code == 200


# -- Rate limits -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "heavy"),
    [
        ("/api/v1/invoices/5/print/", True),
        ("/api/v1/payments/5/receipt/", True),
        ("/api/v1/salary-payments/5/slip/", True),
        ("/api/v1/orders/5/quotation-pdf/", True),
        ("/api/v1/system/export/", True),
        ("/api/v1/system/import/customers/", True),
        ("/api/v1/settings/shop/preview/", True),
        ("/api/v1/reports/daily-sales/?export=pdf", True),
        ("/api/v1/customers/5/statement/?export=xlsx", True),
        ("/api/v1/orders/price-preview/", False),  # every keystroke on the order form
        ("/api/v1/orders/", False),
        ("/api/v1/customers/5/statement/", False),
    ],
)
def test_what_counts_as_heavy(path, heavy):
    from rest_framework.request import Request

    assert is_heavy(Request(APIRequestFactory().get(path))) is heavy


def test_heavy_requests_are_limited_per_person(api, owner, shop, monkeypatch):
    monkeypatch.setattr(HeavyThrottle, "THROTTLE_RATES", {"heavy": "2/min"})
    client = api(owner)
    assert client.get("/api/v1/settings/shop/preview/").status_code == 200
    assert client.get("/api/v1/settings/shop/preview/").status_code == 200
    limited = client.get("/api/v1/settings/shop/preview/")
    assert limited.status_code == 429
    assert "Retry-After" in limited
    # Ordinary screens are not slowed down by it.
    assert client.get("/api/v1/customers/").status_code == 200


def test_password_changes_are_limited(api, desk):
    client = api(desk)
    for _ in range(5):
        client.post(
            "/api/v1/auth/change-password/",
            {"current_password": "wrong", "new_password": "Another@2083"},
            format="json",
        )
    response = client.post(
        "/api/v1/auth/change-password/",
        {"current_password": "wrong", "new_password": "Another@2083"},
        format="json",
    )
    assert response.status_code == 429


def test_backup_now_is_counted_per_person_on_post_only(owner):
    from rest_framework.request import Request

    throttle = BackupThrottle()
    get = Request(APIRequestFactory().get("/api/v1/system/backups/run/"))
    post = Request(APIRequestFactory().post("/api/v1/system/backups/run/"))
    get.user = post.user = owner
    assert throttle.get_cache_key(get, None) is None
    assert throttle.get_cache_key(post, None) == f"throttle_backup_user-{owner.pk}"


# -- Uploads -----------------------------------------------------------------------------


def test_a_logo_over_2_mb_is_refused(api, owner, shop):
    import io
    import os

    from PIL import Image

    # A real PNG of random noise (it does not compress), just over 2 MB.
    out = io.BytesIO()
    Image.frombytes("RGB", (1000, 800), os.urandom(1000 * 800 * 3)).save(out, "PNG")
    assert out.tell() > 2 * 1024 * 1024
    big = SimpleUploadedFile("logo.png", out.getvalue(), content_type="image/png")
    response = api(owner).patch("/api/v1/settings/shop/", {"logo": big}, format="multipart")
    assert response.status_code == 400
    assert "2 MB" in str(response.json())


# -- Dates beyond the Nepali calendar --------------------------------------------------


def test_a_date_beyond_the_nepali_calendar_is_a_clear_error(api, owner, shop):
    """2083 typed as an AD year used to crash the server (500)."""
    client = api(owner)
    worker = {"name": "Ram", "monthly_salary": "15000", "joined_on": "2083-01-01"}
    response = client.post("/api/v1/staff/", worker, format="json")
    assert response.status_code == 400
    assert "still to come" in str(response.json())
    for path in (
        "/api/v1/reports/daily-sales/?date=2083-01-01",
        "/api/v1/utils/date/?ad=2083-01-01",
    ):
        response = client.get(path)
        assert response.status_code == 400, path
        assert "outside the Nepali calendar" in str(response.json()), path
