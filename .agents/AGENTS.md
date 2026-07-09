# Permanent Instructions for Codex / Antigravity in RestaurantOS

## Mission

Build and maintain RestaurantOS respecting the PRD + SDD + BDD + TDD framework. Code is NOT the single source of truth; specifications and tests govern system behavior.

## Mandatory Order of Work

For any user request, bug fix, or feature enhancement:
1. Read [README.md](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/README.md).
2. Read the relevant specification files in [docs/](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/docs/).
3. Identify affected functional/non-functional requirements (`PRD-FR-xxx`, `PRD-NFR-xxx`).
4. Identify existing BDD scenarios (`BDD-SC-xxx`).
5. Identify existing TDD test suites/cases (`TDD-TS-xxx`, `TDD-TC-xxx`).
6. Propose documentation changes (PRD, SDD, BDD, TDD) BEFORE modifying any production code.
7. Update the traceability matrix in [docs/05-matriz-trazabilidad.md](file:///c:/Users/Miguel%20Gonzalez/Downloads/Kiwi/docs/05-matriz-trazabilidad.md).
8. Implement the smallest possible code change that satisfies the criteria.
9. Run all affected unit, integration, contract, and end-to-end tests.
10. Report which requirement, BDD scenario, and TDD test was added/modified.

## Prohibitions

- Do not invent business logic.
- Do not change states, formulas, permissions, or workflow transitions without updating the specifications first.
- Do not remove audit trails for simplicity.
- Do not edit historical balances, stock, payments, or transaction history directly in database tables.
- Do not introduce critical dependencies without an approved Architecture Decision Record (ADR).
- Do not couple the core domain to external providers (e.g., CONTPAQi, Google Maps, Rappi, Uber Eats, DiDi, WhatsApp).
- Do not implement external providers without an adapter interface.
- Do not use MongoDB as the primary transactional data store (PostgreSQL is required).
- Do not treat offline mode as a simple cache (use WAL, inbox/outbox, checkpoints, and reconciliation).
- Do not perform destructive database updates without a clear migration path and reversibility plan.
- Do not build all modules in a single "big bang" release.

## Domain Principles

- PostgreSQL is the central cloud source of truth.
- SQLite WAL is the local branch operational source of truth when disconnected.
- Inventory is derived from a ledger of movements, not directly editable fields.
- Cash movements and payments are immutable; corrections must be made via compensation records.
- Recipes and subrecipes are versioned.
- Orders use explicit events and state machine transitions.
- Each branch belongs to a legal entity (razón social) and has a single warehouse.
- Each branch produces its own items locally (no centralized kitchen initially).
- Inventory reservation occurs upon order acceptance, and is confirmed as consumption upon preparation.
- Cancellations post-production must generate authorized waste (merma) or recovery records.
- External integrations must be idempotent.
- The system must retain the original payload of external requests for auditing.
- All sensitive operations must generate audit logs.

## Development Rules

- Monorepo structure must be maintained.
- TypeScript strict mode in all frontend applications.
- Python strictly typed (mypy) in all backend services.
- Versioned APIs (`/v1/...`).
- Mandatory database migrations (Alembic for FastAPI).
- Border validation (Pydantic/JSON Schema) and domain validation.
- State machines model workflow transitions.
- Explicit business errors rather than generic server exceptions.
- Idempotency keys on sync commands and external webhooks.
- Inbox/Outbox patterns for local-cloud synchronization.
- Deterministic tests with reproducible fixtures.
- Timestamps stored in UTC, converted to local time in the client.
- Currency represented in integer cents (lowest unit) or exact decimal type, never as float.
- Quantities and conversions handled with `Decimal`.
- Do not mix domain logic directly in HTTP controller code.

## Verification / CI Commands

Always verify changes by running the appropriate command:
- Python Backend Tests: `python -m pytest`
- Python Lint & Formatting: `ruff check .`
- Python Type Checking: `mypy .`
- Frontend Type Checking: `pnpm typecheck`
- Frontend Linting: `pnpm lint`

## Definition of Done (Criterio de terminado)

A task is not complete unless:
- The PRD requirement is updated.
- The BDD scenarios are updated.
- Automated tests are added/updated and passing.
- Database migration script is generated (if database schema changed).
- Audit trails are implemented.
- Logging and error handling are added.
- Operation/deployment documentation is updated.
- The traceability matrix is updated.
