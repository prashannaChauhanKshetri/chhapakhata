"""Test settings: fast hashing, isolated media and backup folders."""

import tempfile
from pathlib import Path

from .base import *  # noqa: F403
from .base import env

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES = {
    "default": env.db(
        "TEST_DATABASE_URL",
        default=env("DATABASE_URL", default="postgres://localhost:5432/chhapakhata"),
    )
}

_tmp = Path(tempfile.gettempdir()) / "chhapakhata-tests"
MEDIA_ROOT = _tmp / "media"
BACKUP_DIR = _tmp / "backups"
AXES_ENABLED = False
Q_CLUSTER = {"name": "test", "orm": "default", "sync": True, "timeout": 60, "retry": 120}
