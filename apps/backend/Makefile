POETRY ?= poetry

install:
	$(POETRY) install --no-root

migrate:
	$(POETRY) run python manage.py migrate

seed-roles:
	$(POETRY) run python manage.py seed_roles

dev:
	$(POETRY) run python manage.py runserver 0.0.0.0:8000

test:
	DJANGO_ENV=test $(POETRY) run python manage.py test

check:
	$(POETRY) run python manage.py check

shell:
	$(POETRY) run python manage.py shell
