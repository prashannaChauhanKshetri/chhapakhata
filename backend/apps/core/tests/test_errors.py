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
