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

## Specification and Traceability Hierarchy

Every modification must update documentation in this sequence:

1. **Requirements (PRD)**: Located in [docs/01-PRD.md](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/docs/01-PRD.md). Document the functional/non-functional requirement.
2. **System Design (SDD)**: Located in [docs/02-SDD.md](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/docs/02-SDD.md). Design components, database changes, or architecture changes.
3. **Behavior (BDD)**: Documented using Gherkin syntax in [docs/03-BDD.md](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/docs/03-BDD.md) (or feature-specific `docs/03-BDD-*.md` files).
4. **Verification (TDD)**: Documented in [docs/04-TDD.md](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/docs/04-TDD.md) (or feature-specific `docs/04-TDD-*.md` files) explaining the verification strategy.
5. **Traceability Matrix**: Enlist the mapping in [docs/05-matriz-trazabilidad.md](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/docs/05-matriz-trazabilidad.md).

## Verification Commands

Run the following checks to ensure code validity:

### 1. Python Backend Service (`apps/api` and `tests/`)
- Run all tests: `python -m pytest`
- Run specific tests: `python -m pytest tests/architecture/test_traceability.py`
- Run linting: `ruff check .`
- Run typechecking: `mypy .`

### 2. Frontend / TypeScript
- Type check: `pnpm typecheck`
- Lint check: `pnpm lint`
- Run tests: `pnpm test`

## Consistency Safeguards

- Never allow a requirement `PRD-FR-xxx` or `PRD-NFR-xxx` to have `Scaffold` or `Implementado` status in the traceability matrix without a matching BDD scenario (`BDD-SC-xxx`) and a TDD test suite (`TDD-TS-xxx` or `TDD-TC-xxx`).
- Ensure the architecture rules and file integrity check tests pass before proposing any commits.
