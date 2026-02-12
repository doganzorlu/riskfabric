SHELL := /bin/sh

COMPOSE_DIR := infra/docker
BACKEND_DIR := apps/backend

.PHONY: help infra-up infra-up-app infra-down infra-logs backend-install backend-check backend-migrate backend-seed-roles backend-test

help:
	@echo "Targets:"
	@echo "  infra-up           Start redis + mariadb"
	@echo "  infra-up-app       Start full docker stack (backend + worker + beat + deps)"
	@echo "  infra-down         Stop docker services"
	@echo "  infra-logs         Tail docker logs"
	@echo "  backend-install    Install backend dependencies"
	@echo "  backend-check      Run Django check"
	@echo "  backend-migrate    Run migrations"
	@echo "  backend-seed-roles Seed default roles"
	@echo "  backend-test       Run backend tests"

infra-up:
	cd $(COMPOSE_DIR) && cp -n .env.example .env || true
	cd $(COMPOSE_DIR) && docker compose up -d

infra-up-app:
	cd $(COMPOSE_DIR) && cp -n .env.example .env || true
	cd $(COMPOSE_DIR) && docker compose --profile app up -d --build

infra-down:
	cd $(COMPOSE_DIR) && docker compose --profile app down

infra-logs:
	cd $(COMPOSE_DIR) && docker compose logs -f

backend-install:
	cd $(BACKEND_DIR) && poetry install --no-root

backend-check:
	cd $(BACKEND_DIR) && POETRY_VIRTUALENVS_IN_PROJECT=true poetry run python manage.py check

backend-migrate:
	cd $(BACKEND_DIR) && POETRY_VIRTUALENVS_IN_PROJECT=true poetry run python manage.py migrate

backend-seed-roles:
	cd $(BACKEND_DIR) && POETRY_VIRTUALENVS_IN_PROJECT=true poetry run python manage.py seed_roles

backend-test:
	cd $(BACKEND_DIR) && POETRY_VIRTUALENVS_IN_PROJECT=true poetry run python manage.py test core webui risk integration
