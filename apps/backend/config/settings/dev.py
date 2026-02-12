from pathlib import Path
import os

from .base import *  # noqa: F401,F403

DEBUG = True

_dev_db_engine = os.getenv("DEV_DB_ENGINE", "sqlite").lower()
_default_db_path = Path(BASE_DIR) / "data" / "dev.sqlite3"
_dev_db_path = Path(os.getenv("DEV_DB_PATH", str(_default_db_path)))

if _dev_db_engine != "sqlite":
    raise RuntimeError("Development environment must use SQLite. Set DEV_DB_ENGINE=sqlite")

# Ensure SQLite directory exists in local development.
_dev_db_path.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(_dev_db_path),
    }
}
