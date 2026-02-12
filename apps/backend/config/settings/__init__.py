import os

_env = os.getenv("DJANGO_ENV", "development").lower()

if _env in {"development", "dev"}:
    from .dev import *  # noqa: F401,F403
elif _env in {"test", "testing", "staging", "production", "prod"}:
    if _env in {"test", "testing"}:
        from .test import *  # noqa: F401,F403
    else:
        from .prod import *  # noqa: F401,F403
else:
    raise RuntimeError(f"Unsupported DJANGO_ENV: {_env}")
