"""Production settings for the in-shop server (behind Caddy)."""

from .base import *  # noqa: F403
from .base import LOG_DIR, env

DEBUG = False
SECRET_KEY = env("SECRET_KEY")  # required: no default in production

# Caddy terminates TLS and forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Caddy redirects HTTP to HTTPS itself (W008). HSTS stays off on purpose (W004):
# the shop runs on a private certificate, and the documented plain-HTTP fallback
# must keep working if a device cannot trust it; HSTS would lock those devices out.
SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008"]

LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "app.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "standard",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
        "weasyprint": {"level": "ERROR"},
        "fontTools": {"level": "ERROR"},
    },
}
