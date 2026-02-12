# Worker

Celery worker runtime for async tasks.

Run from this folder (after backend dependencies are installed with Poetry):

```bash
cd ../backend
poetry install --no-root
poetry run celery -A config.celery:app worker -l info
```
