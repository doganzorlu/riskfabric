# Engineering Standards

## 1. Language and Localization

- Primary language for product and engineering assets: English.
- Secondary language: Turkish via localization resources only.
- No Turkish identifiers in code.

Allowed Turkish content locations:

- `locale/tr/*`
- translation database entries
- documentation sections explicitly marked as localized content

Disallowed locations for Turkish strings:

- hardcoded UI components
- API field names
- database schema identifiers
- source code identifiers and constants

## 2. Naming Rules

- Use `snake_case` for database objects and JSON fields.
- Use `snake_case` for Python variables/functions/modules.
- Use `PascalCase` for Python classes.
- Use clear domain names (asset, risk, treatment, review, control).

## 3. API Standards

- Versioned endpoints under `/api/v1`.
- OpenAPI spec required for all public/internal APIs.
- Idempotency key required for integration writes.
- Correlation ID required across service calls.

## 4. Platform Standards

- Backend: Django + Django REST Framework.
- Background processing: Celery + Redis.
- Data store strategy: SQLite in development, MariaDB in test/staging/production.
- Mobile client standard: Flutter consuming DRF APIs.

## 5. Security Standards

- OAuth2/JWT for API authentication.
- RBAC authorization checks at endpoint and service layers.
- Structured audit logging for all critical mutations.
- Secrets must be injected from secure secret stores.

## 6. Quality Gates

Mandatory CI gates:

- lint
- test
- static analysis
- OpenAPI validation
- migration checks
- i18n key consistency checks

## 7. Definition of Done (Engineering)

A story is done only if:

- acceptance criteria pass
- automated tests are added/updated
- OpenAPI/docs are updated
- audit log impact is defined
- i18n keys are added for EN and TR

