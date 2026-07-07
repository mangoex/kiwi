# Matriz de trazabilidad

Estado permitido: `Propuesto`, `Disenado`, `Scaffold`, `Probado`, `Implementado`.

## Requisitos funcionales

| Requisito | Diseno | Escenario BDD | Suite TDD | Estado |
|---|---|---|---|---|
| PRD-FR-001 | Organization module | BDD-SC-025 | TDD-TS-014 | Scaffold |
| PRD-FR-002 | Organization module | BDD-SC-025 | TDD-TS-014 | Scaffold |
| PRD-FR-003 | Organization module | BDD-SC-025 | TDD-TS-014 | Scaffold |
| PRD-FR-004 | Inventory module | Pendiente | TDD-TS-002 | Disenado |
| PRD-FR-005 | RBAC scoped authorization | BDD-SC-021, BDD-SC-025 | TDD-TS-012, TDD-TS-014 | Scaffold |
| PRD-FR-006 | Devices, registers, stations, printers | BDD-SC-018 | TDD-TS-011 | Disenado |
| PRD-FR-007 | Audit events append-only | BDD-SC-007, BDD-SC-012, BDD-SC-021, BDD-SC-025 | TDD-TS-012, TDD-TS-014 | Scaffold |
| PRD-FR-008 | Configuration inheritance | Pendiente | TDD-TS-012 | Propuesto |
| PRD-FR-010 | Catalog module | Pendiente | TDD-TS-006 | Disenado |
| PRD-FR-011 | Station-aware products | BDD-SC-004 | TDD-TS-006 | Disenado |
| PRD-FR-012 | Shared menu by channel | Pendiente | TDD-TS-009 | Disenado |
| PRD-FR-013 | Sale schedules | Pendiente | TDD-TS-009 | Propuesto |
| PRD-FR-014 | Branch stockouts | Pendiente | TDD-TS-006 | Propuesto |
| PRD-FR-015 | Price versioning | Pendiente | TDD-TS-003 | Disenado |
| PRD-FR-016 | External product mappings | BDD-SC-013 | TDD-TS-009 | Disenado |
| PRD-FR-020 | Orders module | BDD-SC-001 | TDD-TS-003 | Disenado |
| PRD-FR-021 | Channel adapters | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-022 | Integration idempotency | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-023 | Original payload retention | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-024 | Customer/address/channel data | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-025 | Order totals and payments | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-026 | Historical catalog snapshots | TDD-TC-004 | TDD-TS-003 | Disenado |
| PRD-FR-027 | Order events/state machine | BDD-SC-001 | TDD-TS-003 | Disenado |
| PRD-FR-028 | Cancellation rules | BDD-SC-006, BDD-SC-007 | TDD-TS-003 | Disenado |
| PRD-FR-029 | Notes by order/product/station | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-030 | Offline-safe folios | BDD-SC-001, BDD-SC-002 | TDD-TS-004 | Disenado |
| PRD-FR-040 | Production tasks | BDD-SC-004 | TDD-TS-006 | Disenado |
| PRD-FR-041 | Station model | BDD-SC-004 | TDD-TS-006 | Disenado |
| PRD-FR-042 | Timing, priority and delays | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-043 | Production state machine | BDD-SC-004 | TDD-TS-006 | Disenado |
| PRD-FR-044 | Authorized reopen/reprint | BDD-SC-018 | TDD-TS-011 | Disenado |
| PRD-FR-045 | Incidents and stockouts | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-046 | Print service | BDD-SC-018 | TDD-TS-011 | Disenado |
| PRD-FR-047 | Printer routing | BDD-SC-018 | TDD-TS-011 | Disenado |
| PRD-FR-048 | Print audit trail | BDD-SC-018 | TDD-TS-011 | Disenado |
| PRD-FR-050 | Cash shifts | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-051 | Opening cash fund | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-052 | Cash movements | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-053 | Payment methods | BDD-SC-012 | TDD-TS-005 | Disenado |
| PRD-FR-054 | Immutable payments | BDD-SC-012 | TDD-TS-005 | Disenado |
| PRD-FR-055 | Partial close | BDD-SC-011 | TDD-TS-005 | Propuesto |
| PRD-FR-056 | Cash count differences | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-057 | Final close | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-058 | Reopen evidence and audit | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-059 | Driver cash settlement | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-060 | Inventory ledger | BDD-SC-005 | TDD-TS-002 | Disenado |
| PRD-FR-061 | Units by process | BDD-SC-005 | TDD-TS-002 | Disenado |
| PRD-FR-062 | Exact conversions | BDD-SC-005 | TDD-TS-002 | Disenado |
| PRD-FR-063 | Inventory reservation | BDD-SC-005 | TDD-TS-002 | Disenado |
| PRD-FR-064 | Consumption | BDD-SC-005 | TDD-TS-002 | Disenado |
| PRD-FR-065 | Release reservation | BDD-SC-006 | TDD-TS-002 | Disenado |
| PRD-FR-066 | Post-production cancellation | BDD-SC-007 | TDD-TS-002 | Disenado |
| PRD-FR-067 | Lots and expirations | BDD-SC-010 | TDD-TS-002 | Disenado |
| PRD-FR-068 | Counts and authorized adjustments | BDD-SC-021 | TDD-TS-002 | Disenado |
| PRD-FR-069 | Transfers | BDD-SC-015 | TDD-TS-002 | Disenado |
| PRD-FR-070 | Kardex and theoretical stock | BDD-SC-005 | TDD-TS-002 | Disenado |
| PRD-FR-080 | Recursive recipes | BDD-SC-008 | TDD-TS-001 | Disenado |
| PRD-FR-081 | Cycle detection | BDD-SC-009 | TDD-TS-001 | Disenado |
| PRD-FR-082 | Recipe versioning | TDD-TC-004 | TDD-TS-001 | Disenado |
| PRD-FR-083 | Yield | BDD-SC-010 | TDD-TS-001 | Disenado |
| PRD-FR-084 | Planned and real waste | BDD-SC-010 | TDD-TS-001 | Disenado |
| PRD-FR-085 | Batch production | BDD-SC-010 | TDD-TS-006 | Disenado |
| PRD-FR-086 | Lot traceability | BDD-SC-010 | TDD-TS-002 | Disenado |
| PRD-FR-087 | Real batch cost | BDD-SC-010 | TDD-TS-001 | Disenado |
| PRD-FR-088 | Theoretical product cost | BDD-SC-008 | TDD-TS-001 | Disenado |
| PRD-FR-089 | Weighted average cost | BDD-SC-005 | TDD-TS-001 | Disenado |
| PRD-FR-090 | Standard cost | BDD-SC-008 | TDD-TS-001 | Disenado |
| PRD-FR-100 | Direct receipts | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-101 | Supplier presentation and lot | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-102 | XML import | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-103 | XML duplicate | BDD-SC-014 | TDD-TS-007 | Disenado |
| PRD-FR-104 | Supplier mappings | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-105 | Accounts payable | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-106 | AP payments and balances | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-107 | XML evidence retention | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-120 | Delivery zones | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-121 | Geocoding | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-122 | Distance and ETA | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-123 | Route optimization | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-124 | Multi-order driver routes | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-125 | Delivery windows | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-126 | Manual route override | BDD-SC-017 | TDD-TS-008 | Disenado |
| PRD-FR-127 | Manual dispatch fallback | BDD-SC-017 | TDD-TS-008 | Disenado |
| PRD-FR-128 | Delivery state registration | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-129 | Driver settlement | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-140 | Versioned APIs | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-141 | Idempotent webhooks | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-142 | Integration health/errors | BDD-SC-023 | TDD-TS-009 | Disenado |
| PRD-FR-143 | Safe retries | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-144 | Pause branch in channels | BDD-SC-023 | TDD-TS-009 | Disenado |
| PRD-FR-145 | Chatbot system queries | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-146 | Chatbot no invention | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-147 | External adapters | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-160 | Individual export | BDD-SC-019 | TDD-TS-010 | Disenado |
| PRD-FR-161 | Global export | BDD-SC-019 | TDD-TS-010 | Disenado |
| PRD-FR-162 | Legal entity separation | BDD-SC-019 | TDD-TS-010 | Disenado |
| PRD-FR-163 | Export canonical data | BDD-SC-019 | TDD-TS-010 | Disenado |
| PRD-FR-164 | Export deduplication | BDD-SC-019 | TDD-TS-010 | Disenado |
| PRD-FR-165 | Re-export | BDD-SC-020 | TDD-TS-010 | Disenado |
| PRD-FR-166 | CONTPAQi adapters | BDD-SC-020 | TDD-TS-010 | Disenado |
| PRD-FR-167 | Export history and reconciliation | BDD-SC-020 | TDD-TS-010 | Disenado |
| PRD-FR-180 | Edge gateway | BDD-SC-001 | TDD-TS-004 | Disenado |
| PRD-FR-181 | Local coordination | BDD-SC-001 | TDD-TS-004 | Disenado |
| PRD-FR-182 | Two-hour offline | BDD-SC-001 | TDD-TS-004 | Disenado |
| PRD-FR-183 | Several offline registers | TDD-TC-003 | TDD-TS-004 | Disenado |
| PRD-FR-184 | Outbox, inbox, idempotency | BDD-SC-002 | TDD-TS-004 | Disenado |
| PRD-FR-185 | Reconciliation | BDD-SC-002 | TDD-TS-004 | Disenado |
| PRD-FR-186 | Sync status | BDD-SC-001 | TDD-TS-004 | Disenado |
| PRD-FR-187 | No duplicate/loss | BDD-SC-002 | TDD-TS-004 | Disenado |
| PRD-FR-188 | Local KDS and printing | BDD-SC-001, BDD-SC-018 | TDD-TS-004, TDD-TS-011 | Disenado |
| PRD-FR-189 | External continuity | BDD-SC-022, BDD-SC-023 | TDD-TS-009 | Disenado |

## Requisitos no funcionales

| Requisito | Diseno | Escenario BDD | Suite TDD | Estado |
|---|---|---|---|---|
| PRD-NFR-001 | Offline-first gateway | BDD-SC-001 | TDD-TS-004 | Disenado |
| PRD-NFR-002 | Idempotency and command log | BDD-SC-002, BDD-SC-003 | TDD-TS-004, TDD-TS-009 | Disenado |
| PRD-NFR-003 | Performance envelope | Pendiente | Performance tests | Propuesto |
| PRD-NFR-004 | Local latency | BDD-SC-001 | Performance tests | Propuesto |
| PRD-NFR-005 | Cloud latency | BDD-SC-003 | Performance tests | Propuesto |
| PRD-NFR-006 | Security | BDD-SC-021 | TDD-TS-012 | Disenado |
| PRD-NFR-007 | Auditability | BDD-SC-007, BDD-SC-012, BDD-SC-021 | TDD-TS-012 | Disenado |
| PRD-NFR-008 | Recovery | Pendiente | Recovery tests | Propuesto |
| PRD-NFR-009 | Observability | BDD-SC-023, BDD-SC-024 | TDD-TS-009, TDD-TS-013 | Scaffold |
| PRD-NFR-010 | Maintainability | BDD-SC-024, Architecture tests | TDD-TS-013, Architecture tests | Scaffold |
| PRD-NFR-011 | Portability | BDD-SC-024, Docker/Easypanel | TDD-TS-013, CI checks | Scaffold |
| PRD-NFR-012 | Exact arithmetic | BDD-SC-008 | TDD-TS-001 | Disenado |
| PRD-NFR-013 | Future multi-company | Organization module | TDD-TS-012 | Disenado |
| PRD-NFR-014 | Privacy | Security design | TDD-TS-012 | Propuesto |
| PRD-NFR-015 | Gateway compatibility | BDD-SC-018 | TDD-TS-011 | Disenado |

## Regla de mantenimiento

No se acepta una nueva historia sin:

- requisito PRD,
- impacto SDD,
- escenario BDD,
- suite y caso TDD,
- estado de implementacion.
