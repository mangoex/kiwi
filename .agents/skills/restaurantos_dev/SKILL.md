---
name: restaurantos-development
description: Helper skill for working safely in the RestaurantOS monorepo. It details documentation hierarchy (PRD, SDD, BDD, TDD), the traceability matrix, how to check consistency, and test commands.
---

# RestaurantOS Development Skill

This skill is designed to guide developers and agents on how to safely build, test, and maintain features in RestaurantOS.

## Monorepo Directory Structure

- `apps/`
  - [api](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/apps/api) - FastAPI backend service.
  - [worker](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/apps/worker) - Background processing worker.
  - [edge-gateway](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/apps/edge-gateway) - Local branch gateway (SQLite WAL).
  - [admin-web](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/apps/admin-web) - Corporate administration web client.
  - [pos-web](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/apps/pos-web) - Point of Sale web application.
  - [kds-web](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/apps/kds-web) - Kitchen Display System web application.
- `packages/`
  - [contracts](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/packages/contracts) - Shared JSON schemas and protocol definitions.
  - [domain-types](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/packages/domain-types) - Shared domain types and business interfaces.
  - [test-fixtures](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/packages/test-fixtures) - Test helpers and mock generators.
- `infra/`
  - [docker](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/infra/docker) - Docker Compose configurations for local development.
  - [easypanel](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/infra/easypanel) - Deployment templates.
- `docs/` - System specifications (PRD, SDD, BDD, TDD).
- `tests/` - Integration, E2E, and architectural checks.

## Governance Authority and Risk

`AGENTS.md` is the canonical process authority. This skill must not impose broader gates than that
file. Classify work before editing:

- `R0`: documentation/evidence only.
- `R1`: low-risk refactor or UI with no permission, persistence, or state change.
- `R2`: observable behavior, API, or non-critical domain change.
- `R3`: money, cash, inventory, production, permissions, sensitive data, offline, concurrency,
  migrations, external integrations, or hard-to-reverse work.

## Triggered Specification and Traceability

Contract changes follow this authority order, but update only the artifacts whose trigger applies:

1. **PRD**: scope, value, actor, permission, or functional/non-functional rule changed.
2. **SDD/ADR**: architecture, data model, state, formula, integration, or technical decision changed.
3. **BDD**: observable behavior or acceptance criterion changed.
4. **TDD**: verification strategy/coverage changed or a regression case is added.
5. **Traceability matrix**: IDs, relationships, coverage, or evidence status changed.

Do not edit an artifact merely to say it has no change. Plans, handoffs, and implementation reports
are optional unless delegation, multi-component sequencing, release, canary, or otherwise unrecorded
evidence makes them useful.

## Proportional Verification

Always run directly affected tests and `git diff --check`. Use the commands below only when their
surface is affected:

### 1. Python Backend Service (`apps/api` and `tests/`)
- Run specific tests: `python -m pytest tests/architecture/test_traceability.py`
- Run linting: `ruff check .`
- Run typechecking: `mypy .`
- Run all tests: `python -m pytest` only for cross-cutting R3 that focal tests cannot bound,
  unavailable/inconclusive CI, regression diagnosis, or an explicit request. CI is authoritative
  only for suites it actually runs; execute missing affected gates focally.

### 2. Frontend / TypeScript
- Type check: `pnpm typecheck`
- Lint check: `pnpm lint`
- Run tests: `pnpm test`

Additional gates:

- PostgreSQL only for persistence, migration, SQL, locking, concurrency, or dialect-sensitive work.
- SQLite/gateway only for offline, synchronization, gateway, or dual-engine compatibility.
- E2E only for cross-component or critical journeys.
- Visual QA only for changed UI states and relevant breakpoints.
- Independent Sol audit is mandatory for R3 or when explicitly requested; R0..R2 use focal review
  plus CI.
- A package authorization may cover edit/test/commit/merge/push. Production deploy, migration,
  configuration, and data actions remain a separate explicit authorization.

## Consistency Safeguards

- Never allow a requirement `PRD-FR-xxx` or `PRD-NFR-xxx` to have `Scaffold` or `Implementado` status in the traceability matrix without a matching BDD scenario (`BDD-SC-xxx`) and a TDD test suite (`TDD-TS-xxx` or `TDD-TC-xxx`).
- Run architecture/traceability tests when specification IDs, mappings, or statuses changed.
- Preserve exact evidence and never present an omitted gate as passing.
- Keep financial, inventory, authorization, migration, offline, and destructive-operation safeguards
  fail-closed even when the workflow is streamlined.
