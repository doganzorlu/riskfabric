import os

from .base import *  # noqa: F401,F403

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "riskfabric"),
        "USER": os.getenv("DB_USER", "riskfabric"),
        "PASSWORD": os.getenv("DB_PASSWORD", "riskfabric"),
        "HOST": os.getenv("DB_HOST", "mariadb"),
        "PORT": os.getenv("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}

# Keep test execution predictable and faster in CI
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
