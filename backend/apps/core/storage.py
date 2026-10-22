"""Storage for uploads that must never be publicly downloadable.

The shop's stamp and authorised signature are what make a bill look genuine,
so they live in ``MEDIA_ROOT/private/``. The web server (Caddy) and the
development server refuse that folder; the app hands the images out only to
signed-in users (``ShopImageView``), and PDFs read them straight from disk.
Keeping them inside ``MEDIA_ROOT`` means backups and restores include them.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

PRIVATE_DIR = "private"


def private_storage() -> FileSystemStorage:
    return FileSystemStorage(location=Path(settings.MEDIA_ROOT) / PRIVATE_DIR, base_url=None)
