# RiskFabric Project Design

## 1. Purpose

RiskFabric is an EAM-integrated risk management platform. It can run:

- As an embedded EAM risk module.
- As a standalone risk management application.

The target capability baseline is feature parity with the core SimpleRisk model, adapted to an asset-first enterprise asset management context.

## 2. Core Product Principles

- Asset-first model: every risk must be linked to at least one asset.
- No orphan risks: risks cannot exist without asset references.
- Dependency-aware analysis: asset relationships drive impact propagation.
- API-first architecture: all functions are available through versioned REST APIs.
- Integration reliability: idempotent sync, retry policies, and audit logs are mandatory.

## 3. Functional Scope

### 3.1 Core Risk Management

- Risk register and lifecycle management.
- Inherent and residual scoring.
- Risk treatment planning (mitigate, accept, transfer, avoid).
- Ownership, due dates, status workflow.
- Review and approval workflow.
- Historical score tracking and change audit.

### 3.2 Asset-Centric Capabilities

- Asset classes with attributes.
- Assets with structured metadata.
- Asset dependency graph (parent-child and operational dependency).
- Risk context based on asset criticality and dependency path.

### 3.3 Governance and Reporting

- Controls and control mappings.
- Governance/compliance test mappings (phased rollout).
- Dashboards and trend reports.
- Asset-based heatmaps and dependency impact reports.

## 4. Integration Model with EAM

### 4.1 Inbound from EAM

- Asset classes and attribute definitions.
- Assets and asset hierarchy/dependency data.
- Organizational context (business unit, cost center, section).
- Master dictionaries (asset type, status, group).

### 4.2 Outbound to EAM

- Risk upsert events per asset.
- Risk score updates and state transitions.
- Treatment plan updates (owner, due date, progress).
- Review results and closure metadata.

### 4.3 Integration Controls

- OAuth2/JWT for service authentication.
- Idempotency key support for write endpoints.
- Correlation ID support for end-to-end tracing.
- Retry with dead-letter queue for failed sync.

## 5. Technical Architecture

Initial architecture is a modular monolith with clear service boundaries, implemented in Django:

- Asset app
- Risk app
- Treatment/Review app
- Integration app
- Governance/Compliance app (phase-driven)
- Reporting app
- Auth/RBAC/Audit app

Recommended runtime components:

- Django + Django REST Framework
- Celery + Redis for async integration workloads
- SQLite (local development)
- MariaDB (test/staging/production primary relational store)
- Object storage for attachments

UI and client strategy:

- Web MVP via Django templates + HTMX + Alpine.js + Chart.js
- Flutter mobile client in later phase via the same REST APIs

## 6. Security and Compliance Requirements

- RBAC with fine-grained permissions.
- Mandatory audit trail for all critical actions.
- Data validation and quarantine flow for integration quality issues.
- Secure secret management and rotated integration credentials.

## 7. Delivery Plan (Target)

- Phase 0: Discovery and contracts (2 weeks)
- Phase 1: Asset + risk MVP (6 weeks)
- Phase 2: Treatment/review + outbound EAM sync (4 weeks)
- Phase 3: Governance/compliance + hardening (3 weeks)
- Phase 4: Pilot go-live and hypercare (2 weeks)

Total estimate: 17 weeks.
