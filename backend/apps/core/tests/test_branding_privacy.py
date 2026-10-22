"""The shop's stamp and signature are never publicly downloadable."""

import io
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from PIL import Image

from apps.core.models import ShopSettings
from apps.core.storage import PRIVATE_DIR

pytestmark = pytest.mark.django_db


def _png(name: str) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@pytest.fixture
def branded(api, owner, settings):
    response = api(owner).patch(
        "/api/v1/settings/shop/",
        {"stamp_image": _png("stamp.png"), "logo": _png("logo.png")},
        format="multipart",
    )
    assert response.status_code == 200, response.content
    return response.json()


def test_uploads_go_to_the_private_folder(branded, settings):
    shop = ShopSettings.load()
    assert f"/{PRIVATE_DIR}/" in shop.stamp_image.path
    assert shop.stamp_image.path.startswith(str(settings.MEDIA_ROOT))
    # The API never hands out a /media/ address for them.
    assert branded["stamp_image"].startswith("/api/v1/settings/shop/images/stamp_image/")
    assert branded["signature_image"] is None


def test_only_the_owner_can_fetch_the_stamp(branded, api, owner, desk, operator):
    url = "/api/v1/settings/shop/images/stamp_image/"
    response = api(owner).get(url)
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response["Cache-Control"].startswith("private")
    assert api(desk).get(url).status_code == 403
    assert api(operator).get(url).status_code == 403
    assert api().get(url).status_code == 403
    # The logo is for everyone signed in, not for strangers.
    assert api(operator).get("/api/v1/settings/shop/images/logo/").status_code == 200
    assert api().get("/api/v1/settings/shop/images/logo/").status_code == 403
    assert api(owner).get("/api/v1/settings/shop/images/password/").status_code == 404


@override_settings(DEBUG=True)
def test_development_server_does_not_serve_the_private_folder(branded, settings):
    from django.urls import clear_url_caches

    clear_url_caches()
    import importlib

    import config.urls

    importlib.reload(config.urls)
    shop = ShopSettings.load()
    client = Client(HTTP_HOST="localhost")
    public = Path(settings.MEDIA_ROOT) / "public-check.txt"
    public.write_text("ok")
    assert client.get("/media/public-check.txt").status_code == 200  # the route is live
    assert client.get(f"/media/{PRIVATE_DIR}/{shop.stamp_image.name}").status_code == 404
    importlib.reload(config.urls)  # back to the normal (non-debug) routes


def test_pdfs_still_include_the_stamp(branded):
    from apps.core.documents import _file_uri

    assert _file_uri(ShopSettings.load().stamp_image).startswith("file://")
