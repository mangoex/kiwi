---
name: restaurantos-development
description: Operationalizes the canonical RestaurantOS development process. Use for repository changes that must follow PRD, SDD, BDD, TDD, traceability, proportional risk, and targeted verification.
---

# RestaurantOS Development

Use the repository-root `AGENTS.md` as the sole process authority. This skill supplies routing and
commands; it must never broaden that file or replace domain specifications.

## Start

1. Read `README.md`, `git status`, and only the specifications relevant to the request.
2. Classify the change using the canonical R0..R3 definitions and preserve unrelated local work.
3. Identify the governing PRD requirements, SDD/ADR decisions, BDD scenarios, TDD cases, and domain
   invariants before editing.
4. Activate only artifacts whose content changes. Follow PRD -> SDD/ADR -> BDD -> TDD -> matrix when
   multiple authorities change; do not create ceremonial diffs.
5. For changed behavior or a bug, obtain a focused failing test for the expected reason before the
   implementation. R0 and covered refactors do not require a manufactured RED phase.

## Implement and verify

Make the smallest complete change that satisfies the contract. Always run affected tests and
`git diff --check`; add only the surface-specific gates required by `AGENTS.md`:

- Python/API: focused `python -m pytest ...`, then focused `python -m ruff check ...`; use `mypy`
  when typed backend code changes.
- Frontend: affected semantic test and `pnpm typecheck`; build only for packaging, routes,
  dependencies, or release.
- PostgreSQL, SQLite/gateway, E2E, visual QA, full local suite, canary, and independent audit activate
  only under the canonical risk rules. CI is authoritative only for suites it actually runs.
- Deployment, migration, configuration, and production data always retain separate authorization.

When specification IDs, mappings, or evidence states change, run
`python -m pytest tests/architecture/test_traceability.py -q`. A requirement may not be `Scaffold` or
`Implementado` without a real BDD scenario and TDD suite/case.

## Conditional review guidance

For R0 use documentation integrity only. For R1/R2 review the affected axes directly and report the
result in the normal closeout; do not create a separate artifact.

Read [references/review-and-observability.md](references/review-and-observability.md) only when the
change is R3, the user requests an audit/review, or changed production code performs I/O, retries,
queues, or external integration. Integrate its output into an already-required handoff, audit,
report, or closeout rather than producing parallel reports.

## Close

Report exact evidence, omitted gates, and residual risk. Never present an unexecuted or skipped gate
as passing, and keep financial, inventory, authorization, migration, offline, and destructive
safeguards fail-closed.
