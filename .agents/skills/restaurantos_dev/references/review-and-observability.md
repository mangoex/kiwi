# Conditional review and observability

Use this reference only under the routing conditions in the parent skill. `AGENTS.md` remains
authoritative.

## One proportional review

Review only axes touched by the change:

- Correctness: contract, edge cases, error paths, tests, state and arithmetic.
- Maintainability: clarity, local conventions, unnecessary complexity and quality-gate weakening.
- Architecture: boundaries, domain placement, data ownership and external adapters.
- Security: trust boundaries, authorization, validation, secrets, privacy and auditability.
- Performance/operation: measured cost, concurrency, retries, failure recovery and production use.

For R3, include relevant historical integrity, idempotency, reversibility, compensation and
PostgreSQL/SQLite checks inside those axes. Do not create one checklist or report per axis, and omit
irrelevant axes without adding `not applicable` entries.

## Adversarial R3 claims

For each non-trivial claim not guaranteed by compiler or types, record:

```text
Claim:
Evidence:
Disproof attempted:
Result:
Residual risk:
```

Try a concrete counterexample: replay, conflicting scope, boundary amount, injected failure,
concurrent winner, stale state, partial write, downgrade with history, or incompatible database
behavior. A passing happy path is not evidence for these properties.

## Operational questions

When changed production code performs I/O, retries, queues, or an external integration, write two to
four questions an operator must be able to answer. Map every proposed log, metric, trace, or alert to
at least one question; signals without a question are noise.

Prefer questions about success rate, stable failure reasons, latency, backlog/retry growth,
idempotent replay, branch scope, and recovery. Keep sensitive values redacted and avoid unbounded
labels. Record the result only in an artifact already activated by the change or in the normal
closeout.
