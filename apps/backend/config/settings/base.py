import os
from pathlib import Path

from celery.schedules import crontab
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


# Core security/application settings
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "asset",
    "risk",
    "integration",
    "webui",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
    }
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("tr", "Turkce"),
]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "webui:login"
LOGIN_REDIRECT_URL = "webui:dashboard"
LOGOUT_REDIRECT_URL = "webui:login"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
}

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BEAT_SCHEDULE = {
    "purge-old-audit-events-daily": {
        "task": "core.tasks.purge_old_audit_events",
        "schedule": crontab(
            minute=int(os.getenv("AUDIT_RETENTION_SCHEDULE_MINUTE", "30")),
            hour=int(os.getenv("AUDIT_RETENTION_SCHEDULE_HOUR", "2")),
        ),
    },
    "send-scheduled-reports-hourly": {
        "task": "risk.tasks.send_scheduled_reports",
        "schedule": crontab(minute=0),
    },
}

AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "180"))

EAM_BASE_URL = os.getenv("EAM_BASE_URL", "")
EAM_CLIENT_ID = os.getenv("EAM_CLIENT_ID", "")
EAM_CLIENT_SECRET = os.getenv("EAM_CLIENT_SECRET", "")

_eam_default_plugin = "excel_bootstrap" if os.getenv("DJANGO_ENV", "development").lower() in {"development", "dev"} else "beam_web_service"
EAM_PLUGIN_NAME = os.getenv("EAM_PLUGIN_NAME", _eam_default_plugin)
EAM_PLUGIN_VERSION = os.getenv("EAM_PLUGIN_VERSION", "v1")
EAM_EXCEL_FILE_PATH = os.getenv("EAM_EXCEL_FILE_PATH", "")

# BEAM plugin runtime configuration
BEAM_LIVE_ENABLED = os.getenv("BEAM_LIVE_ENABLED", "false").lower() == "true"
BEAM_TIMEOUT_SECONDS = int(os.getenv("BEAM_TIMEOUT_SECONDS", "30"))
BEAM_ASSETS_ENDPOINT = os.getenv("BEAM_ASSETS_ENDPOINT", "/api/v1/assets")
BEAM_RISK_UPSERT_ENDPOINT = os.getenv("BEAM_RISK_UPSERT_ENDPOINT", "/api/v1/risks/upsert")
