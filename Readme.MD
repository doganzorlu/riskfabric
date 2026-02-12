# RiskFabric - Developer Guide

## 1. Overview

RiskFabric is an asset-centric risk management platform designed for EAM integration and standalone operation.

Key principles:

- Asset-first risk lifecycle
- Dependency-aware impact analysis
- API-first implementation
- English-first product language with Turkish localization support

See:

- `docs/project-design.md`
- `docs/eam-asset-configuration-model.md`
- `docs/engineering-standards.md`

## 2. Official Tech Stack

- Backend API: `Django` + `Django REST Framework`
- Async/Integration Jobs: `Celery` + `Redis`
- Database: `SQLite` (development), `MariaDB` (test/staging/production)
- API Contracts: `OpenAPI`
- Web UI (MVP): `Django templates` + `HTMX` + `Alpine.js` + `Chart.js`
- Mobile (phase 2+): `Flutter` consuming the same DRF APIs

## 3. Target Architecture

Baseline architecture:

- Django API service
- Django web app
- Celery worker (sync jobs)
- SQLite (development)
- MariaDB (test/staging/production)
- Redis
- Object storage (attachments)

Deployment model:

- Dev: Docker Compose
- Test/Prod: Kubernetes + managed DB/Redis/object storage

## 4. Repository Bootstrap Plan

Recommended top-level layout:

- `apps/backend`
- `apps/web`
- `apps/worker`
- `apps/mobile` (future)
- `packages/contracts`
- `infra/docker`
- `infra/k8s`
- `infra/terraform`
- `docs`

## 5. Local Developer Setup

### 5.1 Prerequisites

- Git
- Docker + Docker Compose
- Python 3.12+
- `Poetry` for dependency and virtual environment management
- MariaDB client tools (for test/prod troubleshooting)
- Make (optional but recommended)

### 5.2 Environment Files

Create `.env` files per app from `.env.example` templates.

Minimum shared variables:

- `APP_ENV=development`
- `DJANGO_DEBUG=true`
- `DJANGO_SECRET_KEY=change-me`
- `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`
- `DEV_DB_ENGINE=sqlite`
- `DEV_DB_PATH=/app/data/dev.sqlite3`
- `DB_HOST=mariadb`
- `DB_PORT=3306`
- `DB_NAME=riskfabric`
- `DB_USER=riskfabric`
- `DB_PASSWORD=riskfabric`
- `REDIS_URL=redis://redis:6379/0`
- `CELERY_BROKER_URL=redis://redis:6379/1`
- `CELERY_RESULT_BACKEND=redis://redis:6379/2`
- `EAM_BASE_URL=http://eam.local`
- `EAM_CLIENT_ID=...`
- `EAM_CLIENT_SECRET=...`

### 5.3 Run Locally (planned standard)

```bash
# start dependencies only (redis + mariadb)
cd infra/docker
cp .env.example .env
docker compose up -d

# optional: run full app stack in containers (backend + worker + beat + dependencies)
docker compose --profile app up -d --build

# backend env + deps
cd ../../apps/backend
poetry install --no-root

# run migrations
poetry run python manage.py migrate

# seed default role groups
poetry run python manage.py seed_roles

# start backend/web
poetry run python manage.py runserver

# start worker (new terminal)
cd ../backend
poetry run celery -A config.celery:app worker -l info

# start scheduler (new terminal)
poetry run celery -A config.celery:app beat -l info
```

Docker Compose configuration values are sourced from `infra/docker/.env`.

## 6. Database and Migrations

Rules:

- Development uses SQLite for speed and zero-setup local runs.
- Test/staging/production use MariaDB and are the source of truth for release validation.
- Never modify applied migration files.
- Create forward-only migrations.
- Provide rollback plan in release notes.
- Every schema change must include index and constraint review.

Core constraints:

- Avoid SQLite-specific SQL patterns in Django ORM migrations/queries; keep MariaDB compatibility as the primary target.

- Risk requires asset linkage.
- Asset codes are unique by integration source.
- Parent references and dependency references are validated.

## 7. EAM Integration Development

### 7.1 Inbound Sync

- Pull asset classes, assets, dependencies, and dictionaries from EAM.
- Normalize and validate against canonical model.
- Upsert with idempotency and audit logs.

### 7.2 Outbound Sync

- Push risk state, score updates, and treatment results.
- Include source and correlation metadata.
- Use retry + dead-letter patterns for resilience.

### 7.3 Contract Management

- OpenAPI contract required for all integration endpoints.
- Contract tests must run in CI.

## 8. Localization and Language

- Default UI language: English.
- Turkish is secondary localization.
- No Turkish source-code identifiers.
- No hardcoded UI strings; use translation keys.

Recommended structure:

- `apps/web/locale/en/LC_MESSAGES`
- `apps/web/locale/tr/LC_MESSAGES`

## 9. Quality and Testing

Required test layers:

- Unit tests for domain rules
- Integration tests for API and DB
- Contract tests for EAM integration
- End-to-end smoke tests

Minimum CI checks:

- lint
- test
- migration validation
- OpenAPI validation
- i18n key completeness check

## 10. DevOps and Environments

### 10.1 Environments

- `dev`: shared internal development
- `test`: QA and integration validation
- `staging`: pre-production release candidate
- `prod`: production

### 10.2 CI/CD Pipeline (target)

1. PR opened
2. Lint + unit/integration tests
3. Build artifacts and image scan
4. Contract and migration checks
5. Deploy to `test`
6. Manual approval gate
7. Deploy to `staging`
8. Production rollout (canary/rolling)

### 10.3 Operational Essentials

- Centralized logs
- Metrics and traces
- Alerting for sync failures and queue backlogs
- Runbooks for incident handling and rollback

## 11. Security Baseline

- OAuth2/JWT for service authentication
- RBAC authorization model
- Audit logs for all critical changes
- Secret management via vault or cloud secret manager
- Regular dependency and container image scanning

## 12. Documentation Discipline

When changing behavior, update:

- `docs/project-design.md`
- `docs/eam-asset-configuration-model.md`
- `docs/engineering-standards.md`
- OpenAPI specs and migration docs
- `packages/contracts/beam-web-service-v1.openapi.yaml`
- `docs/integration/beam-plugin-contract.md`
- `docs/integration/beam-mock-server.md`


## 13. Web UI Quick Start

After running migrations, create users:

```bash
cd apps/backend
poetry run python manage.py createsuperuser
poetry run python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); User.objects.filter(username='demo').exists() or User.objects.create_user('demo', password='demo12345')"
```

Use:

- User portal: `http://127.0.0.1:8000/`
- Login page: `http://127.0.0.1:8000/login/`
- Admin panel: `http://127.0.0.1:8000/admin/`

User portal pages:

- Dashboard
- Work Queue (overdue treatments + upcoming reviews)
: HTMX filters for owner, treatment status, reviewer, and review window
- Audit Log (admin only, web/API audit records with filters)
- Assets (includes location metadata imported from Excel)
- Risks (create + list)
- Risk Detail (scoring history, treatments, reviews)
- Location Risks (filter by business unit/cost center/section)
- Location Tree (business unit -> cost center -> section -> asset with risk counters)
- EAM Sync

## 14. Risk Lifecycle Features

Implemented SimpleRisk-style lifecycle capabilities:

- Scoring methods (`RiskScoringMethod`) with configurable weights
- Score history snapshots (`RiskScoringSnapshot`)
- Risk treatments/mitigations (`RiskTreatment`)
- Periodic reviews (`RiskReview`)

Risk context is persisted directly on each risk record:

- `business_unit`
- `cost_center`
- `section`
- `asset_type`

These values are automatically synced from `primary_asset`.

### API Endpoints

- `GET/POST /api/v1/risk-scoring-methods/`
- `GET /api/v1/risk-scoring-snapshots/`
- `GET/POST /api/v1/risk-treatments/`
- `GET/POST /api/v1/risk-reviews/`
- `POST /api/v1/risks/{id}/recalculate/`
- `GET/POST /api/v1/assessments/`
- `GET/POST /api/v1/vulnerabilities/`
- `GET/POST /api/v1/governance-programs/`
- `GET/POST /api/v1/compliance-frameworks/`
- `GET/POST /api/v1/compliance-requirements/`
- `GET/POST /api/v1/control-test-plans/`
- `GET/POST /api/v1/control-test-runs/`

### API Query Parameters

All list endpoints support:

- `page` pagination (default page size: 25)
- `search` full-text search over viewset `search_fields`
- `ordering` for sortable fields (e.g., `?ordering=-created_at`)

### GUI

From the `Risks` page you can now:

- create risks with scoring method selection
- apply a scoring method to an existing risk
- add treatment/mitigation records
- add review decisions
- update risk status inline (HTMX)
- enforce status transitions (`open -> in_progress/closed`, `in_progress -> open/closed`, `closed -> open`)

From the `Risk Detail` page you can now:

- update treatment progress/status inline (HTMX)
- track scoring snapshot history
- review treatment/review timeline in one place

### Role-Based Access (Web UI)

- `risk_admin`: full access (risk operations + EAM sync)
- `risk_owner`: risk/treatment/scoring/status operations
- `risk_reviewer`: review operations
- superuser: full access

### Role-Based Access (API)

- Read endpoints: authenticated users
- `risk_admin` or `risk_owner`: write access for risks, treatments, risk recalculate
- `risk_admin` or `risk_reviewer`: write access for reviews
- `risk_admin`: write access for scoring method definitions
- `risk_admin`: EAM sync execution (`POST /api/v1/integration/eam/sync`)

### Audit Trail

- Audit model: `core.AuditEvent`
- Logged actions include web and API operations for:
  - risk create/update/delete/status/scoring
  - treatment create/update
  - review create
  - EAM sync execution (success/failed/denied)
- Audit UI: `/audit-log/` (admin only), with CSV export at `/audit-log/export/`
- Retention command: `poetry run python manage.py purge_audit_events --days 180`
- Scheduled retention task: `core.tasks.purge_old_audit_events` (Celery Beat, daily)
- Retention env vars:
  - `AUDIT_RETENTION_DAYS` (default `180`)
  - `AUDIT_RETENTION_SCHEDULE_HOUR` (default `2`)
  - `AUDIT_RETENTION_SCHEDULE_MINUTE` (default `30`)

## 15. Internationalization (EN/TR)

Interface now supports English and Turkish.

- Default language: `en`
- Supported languages: `en`, `tr`
- Language switch endpoint: `/i18n/setlang/`
- Turkish translations are located at:
  - `apps/backend/locale/tr/LC_MESSAGES/django.po`
  - `apps/backend/locale/tr/LC_MESSAGES/django.mo`

If you change translation strings, recompile:

```bash
cd apps/backend
poetry run python manage.py compilemessages -l tr
```
