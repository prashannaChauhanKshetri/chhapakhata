"""Base settings shared by every environment.

Environment-specific values come from environment variables (see `.env.example`).
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_DIR = BASE_DIR.parent

env = environ.Env()
# Load a local .env for development. In production, variables come from Docker Compose.
for candidate in (REPO_DIR / ".env", BASE_DIR / ".env"):
    if candidate.exists():
        environ.Env.read_env(candidate)
        break

SECRET_KEY = env("SECRET_KEY", default="insecure-development-key-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "drf_standardized_errors",
    "axes",
    "simple_history",
    "django_q",
    # Project apps
    "apps.core",
    "apps.accounts",
    "apps.customers",
    "apps.inventory",
    "apps.catalog",
    "apps.orders",
    "apps.production",
    "apps.billing",
    "apps.reports",
    "apps.system",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    # Axes must be last so it can intercept lockouts.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://localhost:5432/chhapakhata"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Sessions & cookies (same-origin SPA, session auth) ---
SESSION_COOKIE_AGE = int(timedelta(hours=12).total_seconds())
SESSION_SAVE_EVERY_REQUEST = True  # sliding expiry while staff are active
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it to send X-CSRFToken
SESSION_COOKIE_SECURE = env.bool("SECURE_COOKIES", default=False)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE

# --- Login lockout (django-axes) ---
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_LOCKOUT_CALLABLE = "apps.accounts.lockout.lockout_response"

# --- Internationalisation ---
LANGUAGE_CODE = "en"
TIME_ZONE = env("TIME_ZONE", default="Asia/Kathmandu")
USE_I18N = True
USE_TZ = True

# --- Static & media ---
STATIC_URL = "/static/"
STATIC_ROOT = Path(env.str("STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env.str("MEDIA_ROOT", default=str(BASE_DIR / "media")))
FONTS_DIR = BASE_DIR / "fonts"

# --- Django REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "apps.core.permissions.HasPerm",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_standardized_errors.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
    "COERCE_DECIMAL_TO_STRING": True,
    "DATETIME_FORMAT": "iso-8601",
    "DEFAULT_THROTTLE_RATES": {"login": "20/min"},
}

DRF_STANDARDIZED_ERRORS = {"ENABLE_IN_DEBUG_FOR_UNHANDLED_EXCEPTIONS": False}

SPECTACULAR_SETTINGS = {
    "TITLE": "ChhapaKhata API",
    "DESCRIPTION": "Print shop management: orders, production, stock, billing and ledger.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {
        "ValidationErrorEnum": "drf_standardized_errors.openapi_serializers.ValidationErrorEnum.choices",
        "ClientErrorEnum": "drf_standardized_errors.openapi_serializers.ClientErrorEnum.choices",
        "ServerErrorEnum": "drf_standardized_errors.openapi_serializers.ServerErrorEnum.choices",
        "ErrorCode401Enum": "drf_standardized_errors.openapi_serializers.ErrorCode401Enum.choices",
        "ErrorCode403Enum": "drf_standardized_errors.openapi_serializers.ErrorCode403Enum.choices",
        "ErrorCode404Enum": "drf_standardized_errors.openapi_serializers.ErrorCode404Enum.choices",
        "ErrorCode405Enum": "drf_standardized_errors.openapi_serializers.ErrorCode405Enum.choices",
        "ErrorCode406Enum": "drf_standardized_errors.openapi_serializers.ErrorCode406Enum.choices",
        "ErrorCode415Enum": "drf_standardized_errors.openapi_serializers.ErrorCode415Enum.choices",
        "ErrorCode429Enum": "drf_standardized_errors.openapi_serializers.ErrorCode429Enum.choices",
        "ErrorCode500Enum": "drf_standardized_errors.openapi_serializers.ErrorCode500Enum.choices",
        "JobStageEnum": "apps.production.models.Stage.choices",
        "OrderStatusEnum": "apps.orders.models.OrderStatus.choices",
        "InvoiceStatusEnum": "apps.billing.models.InvoiceStatus.choices",
        "PaymentStatusEnum": "apps.billing.models.PaymentStatus.choices",
        "RollStatusEnum": "apps.inventory.models.RollStatus.choices",
        "UnitEnum": "apps.catalog.models.LengthUnit.choices",
        "StockUnitEnum": "apps.inventory.models.StockUnit.choices",
    },
    "POSTPROCESSING_HOOKS": [
        "drf_standardized_errors.openapi_hooks.postprocess_schema_enums",
        "apps.core.schema.mark_response_fields_required",
    ],
}

# --- Background tasks (django-q2, database broker: no Redis needed) ---
Q_CLUSTER = {
    "name": "chhapakhata",
    "orm": "default",
    "workers": 1,
    "timeout": 1800,
    "retry": 3600,
    "max_attempts": 1,
    "catch_up": False,
    "save_limit": 200,
}

# --- Business configuration ---
MAX_ACTIVE_USERS = env.int("MAX_ACTIVE_USERS", default=5)
BACKUP_DIR = Path(env.str("BACKUP_DIR", default=str(BASE_DIR / "backups")))
BACKUP_HOUR = env.int("BACKUP_HOUR", default=21)
RCLONE_REMOTE = env("RCLONE_REMOTE", default="")
RCLONE_CONFIG = env("RCLONE_CONFIG", default="")

LOG_DIR = Path(env.str("LOG_DIR", default=str(BASE_DIR / "logs")))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
        "weasyprint": {"level": "ERROR"},
        "fontTools": {"level": "ERROR"},
    },
}
