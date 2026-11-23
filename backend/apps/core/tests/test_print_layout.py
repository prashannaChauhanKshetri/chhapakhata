"""Settings → Print layout: colour, text size, header, payment details, preview."""

import pytest

from apps.core.documents import base_context
from apps.core.models import ShopSettings

pytestmark = pytest.mark.django_db


def test_owner_sets_the_layout_and_sees_a_sample(api, owner, shop):
    body = {
        "print_color": "#7A1F1F",
        "print_text_size": "large",
        "print_header": "center",
        "payment_info": "NIC Asia Bank 1234567890\neSewa 9800000000",
        "phone": "9848029918 | 9867362776",
        "email": "shop@example.com",
    }
    response = api(owner).patch("/api/v1/settings/shop/", body, format="json")
    assert response.status_code == 200
    assert base_context()["accent"] == "#7A1F1F"
    preview = api(owner).get("/api/v1/settings/shop/preview/", {"size": "a5"})
    assert preview.status_code == 200 and preview["Content-Type"] == "application/pdf"


def test_a_colour_must_be_a_hex_code(api, owner, shop):
    bad = "red; } body { display: none"
    response = api(owner).patch("/api/v1/settings/shop/", {"print_color": bad}, format="json")
    assert response.status_code == 400
    assert ShopSettings.load().print_color == "#1D4E89"


def test_staff_cannot_preview_or_change_it(api, desk):
    assert api(desk).get("/api/v1/settings/shop/preview/").status_code == 403


def test_the_owner_can_switch_production_tracking_off(api, owner, desk, shop):
    assert api(owner).get("/api/v1/settings/shop/").json()["track_production"] is True
    response = api(owner).patch(
        "/api/v1/settings/shop/", {"track_production": False}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["track_production"] is False
    # Everyone sees it (the screens follow it); only the owner changes it.
    assert api(desk).get("/api/v1/settings/shop/").json()["track_production"] is False
    assert (
        api(desk).patch("/api/v1/settings/shop/", {"track_production": True}, format="json")
    ).status_code == 403
