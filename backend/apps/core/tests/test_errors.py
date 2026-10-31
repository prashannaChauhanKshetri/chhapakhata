import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db


@override_settings(DEBUG=False)
def test_unknown_api_address_answers_json():
    response = Client(HTTP_HOST="localhost").get("/api/v1/no-such-thing/")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


@override_settings(DEBUG=False)
def test_other_addresses_keep_the_html_page():
    response = Client(HTTP_HOST="localhost").get("/no-such-page/")
    assert response.status_code == 404
    assert response["Content-Type"].startswith("text/html")


def test_server_error_view_is_json_for_api(rf):
    from apps.core.views import server_error

    response = server_error(rf.get("/api/v1/orders/"))
    assert response.status_code == 500
    assert b'"server_error"' in response.content


@override_settings(ALLOWED_HOSTS=["chhapakhata.tech"])
def test_container_health_probe_works_whatever_the_allowed_hosts():
    # Docker's healthcheck: http://localhost:8000/api/v1/health/ from inside the container.
    probe = Client(HTTP_HOST="localhost:8000", REMOTE_ADDR="127.0.0.1")
    response = probe.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@override_settings(ALLOWED_HOSTS=["chhapakhata.tech"])
def test_outside_requests_still_need_an_allowed_host():
    stranger = Client(HTTP_HOST="evil.example", REMOTE_ADDR="203.0.113.9")
    assert stranger.get("/api/v1/health/").status_code == 400
    site = Client(HTTP_HOST="chhapakhata.tech", REMOTE_ADDR="203.0.113.9")
    assert site.get("/api/v1/health/").status_code == 200
