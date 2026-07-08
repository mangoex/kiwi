# Matriz de trazabilidad

Estado permitido: `Propuesto`, `Disenado`, `Scaffold`, `Probado`, `Implementado`.

## Requisitos funcionales

| Requisito | Diseno | Escenario BDD | Suite TDD | Estado |
|---|---|---|---|---|
| PRD-FR-001 | Organization module | BDD-SC-025, BDD-SC-046, BDD-SC-056 | TDD-TS-014, TDD-TS-026, TDD-TS-033 | Scaffold |
| PRD-FR-002 | Organization module | BDD-SC-025, BDD-SC-046, BDD-SC-047 | TDD-TS-014, TDD-TS-026, TDD-TS-027 | Scaffold |
| PRD-FR-003 | Organization module | BDD-SC-025, BDD-SC-047 | TDD-TS-014, TDD-TS-027 | Scaffold |
| PRD-FR-004 | Inventory module | Pendiente | TDD-TS-002 | Disenado |
| PRD-FR-005 | RBAC scoped authorization | BDD-SC-021, BDD-SC-025, BDD-SC-043, BDD-SC-044, BDD-SC-045, BDD-SC-057 | TDD-TS-012, TDD-TS-014, TDD-TS-025, TDD-TS-034 | Scaffold |
| PRD-FR-006 | Devices, registers, stations, printers | BDD-SC-018 | TDD-TS-011 | Disenado |
| PRD-FR-007 | Audit events append-only | BDD-SC-007, BDD-SC-012, BDD-SC-021, BDD-SC-025, BDD-SC-043, BDD-SC-044, BDD-SC-045, BDD-SC-057 | TDD-TS-012, TDD-TS-014, TDD-TS-025, TDD-TS-034 | Scaffold |
| PRD-FR-008 | Configuration inheritance | Pendiente | TDD-TS-012 | Propuesto |
| PRD-FR-010 | Catalog module | BDD-SC-026, BDD-SC-027, BDD-SC-048, BDD-SC-056 | TDD-TS-015, TDD-TS-016, TDD-TS-027, TDD-TS-033 | Scaffold |
| PRD-FR-011 | Station-aware products | BDD-SC-004, BDD-SC-048 | TDD-TS-006, TDD-TS-027 | Scaffold |
| PRD-FR-012 | Shared menu by channel | BDD-SC-026, BDD-SC-027, BDD-SC-048 | TDD-TS-015, TDD-TS-016, TDD-TS-027 | Scaffold |
| PRD-FR-013 | Sale schedules | Pendiente | TDD-TS-009 | Propuesto |
| PRD-FR-014 | Branch stockouts | BDD-SC-026, BDD-SC-027, BDD-SC-048 | TDD-TS-015, TDD-TS-016, TDD-TS-027 | Scaffold |
| PRD-FR-015 | Price versioning | BDD-SC-026, BDD-SC-027, BDD-SC-048 | TDD-TS-015, TDD-TS-016, TDD-TS-027 | Scaffold |
| PRD-FR-016 | External product mappings | BDD-SC-013 | TDD-TS-009 | Disenado |
| PRD-FR-020 | Orders module | BDD-SC-001, BDD-SC-030 | TDD-TS-003, TDD-TS-018 | Scaffold |
| PRD-FR-021 | Channel adapters | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-022 | Integration idempotency | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-023 | Original payload retention | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-024 | Customer/address/channel data | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-025 | Order totals and payments | BDD-SC-011, BDD-SC-030, BDD-SC-032, BDD-SC-033 | TDD-TS-005, TDD-TS-018, TDD-TS-020 | Scaffold |
| PRD-FR-026 | Historical catalog snapshots | TDD-TC-004 | TDD-TS-003 | Disenado |
| PRD-FR-027 | Order events/state machine | BDD-SC-001, BDD-SC-030 | TDD-TS-003, TDD-TS-018 | Scaffold |
| PRD-FR-028 | Cancellation rules | BDD-SC-006, BDD-SC-007, BDD-SC-054, BDD-SC-055 | TDD-TS-003, TDD-TS-031, TDD-TS-032 | Scaffold |
| PRD-FR-029 | Notes by order/product/station | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-030 | Offline-safe folios | BDD-SC-001, BDD-SC-002, BDD-SC-030 | TDD-TS-004, TDD-TS-018 | Scaffold |
| PRD-FR-040 | Production tasks | BDD-SC-004, BDD-SC-031 | TDD-TS-006, TDD-TS-019 | Scaffold |
| PRD-FR-041 | Station model | BDD-SC-004, BDD-SC-031 | TDD-TS-006, TDD-TS-019 | Scaffold |
| PRD-FR-042 | Timing, priority and delays | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-043 | Production state machine | BDD-SC-004, BDD-SC-031 | TDD-TS-006, TDD-TS-019 | Scaffold |
| PRD-FR-044 | Authorized reopen/reprint | BDD-SC-018, BDD-SC-036 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-045 | Incidents and stockouts | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-046 | Print service | BDD-SC-018, BDD-SC-035, BDD-SC-036 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-047 | Printer routing | BDD-SC-018, BDD-SC-035 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-048 | Print audit trail | BDD-SC-018, BDD-SC-035, BDD-SC-036 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-050 | Cash shifts | BDD-SC-011, BDD-SC-028, BDD-SC-029 | TDD-TS-005, TDD-TS-017 | Scaffold |
| PRD-FR-051 | Opening cash fund | BDD-SC-011, BDD-SC-028 | TDD-TS-005, TDD-TS-017 | Scaffold |
| PRD-FR-052 | Cash movements | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-053 | Payment methods | BDD-SC-012, BDD-SC-032, BDD-SC-033 | TDD-TS-005, TDD-TS-020 | Scaffold |
| PRD-FR-054 | Immutable payments | BDD-SC-012, BDD-SC-032, BDD-SC-033 | TDD-TS-005, TDD-TS-020 | Scaffold |
| PRD-FR-055 | Partial close | BDD-SC-011 | TDD-TS-005 | Propuesto |
| PRD-FR-056 | Cash count differences | BDD-SC-011, BDD-SC-034 | TDD-TS-005, TDD-TS-021 | Scaffold |
| PRD-FR-057 | Final close | BDD-SC-011, BDD-SC-029, BDD-SC-034 | TDD-TS-005, TDD-TS-017, TDD-TS-021 | Scaffold |
| PRD-FR-058 | Reopen evidence and audit | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-059 | Driver cash settlement | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-060 | Inventory ledger | BDD-SC-005, BDD-SC-049, BDD-SC-050, BDD-SC-056 | TDD-TS-002, TDD-TS-028, TDD-TS-033 | Scaffold |
| PRD-FR-061 | Units by process | BDD-SC-005, BDD-SC-049, BDD-SC-050 | TDD-TS-002, TDD-TS-028 | Scaffold |
| PRD-FR-062 | Exact conversions | BDD-SC-005, BDD-SC-049, BDD-SC-050 | TDD-TS-002, TDD-TS-028 | Scaffold |
| PRD-FR-063 | Inventory reservation | BDD-SC-005, BDD-SC-052 | TDD-TS-002, TDD-TS-030 | Scaffold |
| PRD-FR-064 | Consumption | BDD-SC-005, BDD-SC-053 | TDD-TS-002, TDD-TS-030 | Scaffold |
| PRD-FR-065 | Release reservation | BDD-SC-006, BDD-SC-054 | TDD-TS-002, TDD-TS-031 | Scaffold |
| PRD-FR-066 | Post-production cancellation | BDD-SC-007, BDD-SC-055 | TDD-TS-002, TDD-TS-032 | Scaffold |
| PRD-FR-067 | Lots and expirations | BDD-SC-010 | TDD-TS-002 | Disenado |
| PRD-FR-068 | Counts and authorized adjustments | BDD-SC-021, BDD-SC-057 | TDD-TS-002, TDD-TS-034 | Scaffold |
| PRD-FR-069 | Transfers | BDD-SC-015 | TDD-TS-002 | Disenado |
| PRD-FR-070 | Kardex and theoretical stock | BDD-SC-005, BDD-SC-049, BDD-SC-050, BDD-SC-056 | TDD-TS-002, TDD-TS-028, TDD-TS-033 | Scaffold |
| PRD-FR-080 | Recursive recipes | BDD-SC-008, BDD-SC-051, BDD-SC-056 | TDD-TS-001, TDD-TS-029, TDD-TS-033 | Scaffold |
| PRD-FR-081 | Cycle detection | BDD-SC-009 | TDD-TS-001 | Disenado |
| PRD-FR-082 | Recipe versioning | BDD-SC-051, TDD-TC-004 | TDD-TS-001, TDD-TS-029 | Scaffold |
| PRD-FR-083 | Yield | BDD-SC-010 | TDD-TS-001 | Disenado |
| PRD-FR-084 | Planned and real waste | BDD-SC-010 | TDD-TS-001 | Disenado |
| PRD-FR-085 | Batch production | BDD-SC-010 | TDD-TS-006 | Disenado |
| PRD-FR-086 | Lot traceability | BDD-SC-010 | TDD-TS-002 | Disenado |
| PRD-FR-087 | Real batch cost | BDD-SC-010 | TDD-TS-001 | Disenado |
| PRD-FR-088 | Theoretical product cost | BDD-SC-008, BDD-SC-051 | TDD-TS-001, TDD-TS-029 | Scaffold |
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
| PRD-FR-180 | Edge gateway | BDD-SC-001, BDD-SC-037, BDD-SC-038, BDD-SC-041, BDD-SC-042 | TDD-TS-004, TDD-TS-023, TDD-TS-024 | Scaffold |
| PRD-FR-181 | Local coordination | BDD-SC-001, BDD-SC-037, BDD-SC-041 | TDD-TS-004, TDD-TS-023, TDD-TS-024 | Scaffold |
| PRD-FR-182 | Two-hour offline | BDD-SC-001, BDD-SC-041 | TDD-TS-004, TDD-TS-024 | Scaffold |
| PRD-FR-183 | Several offline registers | TDD-TC-003 | TDD-TS-004 | Disenado |
| PRD-FR-184 | Outbox, inbox, idempotency | BDD-SC-002, BDD-SC-037, BDD-SC-038, BDD-SC-041, BDD-SC-042 | TDD-TS-004, TDD-TS-023, TDD-TS-024 | Scaffold |
| PRD-FR-185 | Reconciliation | BDD-SC-002, BDD-SC-037, BDD-SC-038, BDD-SC-042 | TDD-TS-004, TDD-TS-023, TDD-TS-024 | Scaffold |
| PRD-FR-186 | Sync status | BDD-SC-001, BDD-SC-037 | TDD-TS-004, TDD-TS-023 | Scaffold |
| PRD-FR-187 | No duplicate/loss | BDD-SC-002, BDD-SC-038, BDD-SC-041, BDD-SC-042 | TDD-TS-004, TDD-TS-023, TDD-TS-024 | Scaffold |
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
| PRD-NFR-006 | Security | BDD-SC-021, BDD-SC-057 | TDD-TS-012, TDD-TS-034 | Scaffold |
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
