# Matriz de trazabilidad

Estado permitido: `Propuesto`, `Disenado`, `Scaffold`, `Probado`, `Implementado`.

## Requisitos funcionales

| Requisito | Diseno | Escenario BDD | Suite TDD | Estado |
|---|---|---|---|---|
| PRD-FR-001 | Organization module | BDD-SC-025, BDD-SC-046, BDD-SC-056, BDD-SC-058 | TDD-TS-014, TDD-TS-026, TDD-TS-033, TDD-TS-035 | Scaffold |
| PRD-FR-002 | Organization module | BDD-SC-025, BDD-SC-046, BDD-SC-047, BDD-SC-058 | TDD-TS-014, TDD-TS-026, TDD-TS-027, TDD-TS-035 | Scaffold |
| PRD-FR-003 | Organization module | BDD-SC-025, BDD-SC-047 | TDD-TS-014, TDD-TS-027 | Scaffold |
| PRD-FR-004 | Inventory module | Pendiente | TDD-TS-002 | Disenado |
| PRD-FR-005 | RBAC scoped authorization | BDD-SC-021, BDD-SC-025, BDD-SC-043, BDD-SC-044, BDD-SC-045, BDD-SC-057, BDD-SC-058, BDD-SC-059, BDD-SC-060, BDD-SC-061, BDD-SC-063, BDD-SC-064, BDD-SC-065, BDD-SC-066, BDD-SC-067, BDD-SC-068, BDD-SC-118, BDD-SC-119, BDD-SC-123, BDD-SC-125, BDD-SC-126, BDD-SC-127, BDD-SC-132, BDD-SC-133, BDD-SC-136, BDD-SC-137, BDD-SC-141, BDD-SC-143 | TDD-TS-012, TDD-TS-014, TDD-TS-025, TDD-TS-034, TDD-TS-035, TDD-TS-036, TDD-TS-037, TDD-TS-038, TDD-TS-050, TDD-TS-051, TDD-TS-052, TDD-TC-031, TDD-TC-043, TDD-TC-044, TDD-TC-045 | Scaffold |
| PRD-FR-006 | Devices, registers, stations, printers | BDD-SC-018 | TDD-TS-011 | Disenado |
| PRD-FR-007 | Audit events append-only | BDD-SC-007, BDD-SC-012, BDD-SC-021, BDD-SC-025, BDD-SC-043, BDD-SC-044, BDD-SC-045, BDD-SC-057, BDD-SC-061, BDD-SC-062, BDD-SC-063, BDD-SC-066, BDD-SC-122 | TDD-TS-012, TDD-TS-014, TDD-TS-017, TDD-TS-025, TDD-TS-034, TDD-TS-037, TDD-TS-050, TDD-TC-031, TDD-TC-043 | Scaffold |
| PRD-FR-008 | Configuration inheritance | BDD-SC-118, BDD-SC-122, BDD-SC-129 | TDD-TS-012, TDD-TS-050, TDD-TS-051 | Scaffold |
| PRD-FR-009 | Business unit hierarchy | BDD-SC-066, BDD-SC-124 | TDD-TS-038, TDD-TS-050 | Scaffold |
| PRD-FR-010 | Catalog module | BDD-SC-026, BDD-SC-027, BDD-SC-048, BDD-SC-056, BDD-SC-058 | TDD-TS-015, TDD-TS-016, TDD-TS-027, TDD-TS-033, TDD-TS-035 | Scaffold |
| PRD-FR-011 | Station-aware products | BDD-SC-004, BDD-SC-048 | TDD-TS-006, TDD-TS-027 | Scaffold |
| PRD-FR-012 | Shared menu by channel | BDD-SC-026, BDD-SC-027, BDD-SC-048 | TDD-TS-015, TDD-TS-016, TDD-TS-027 | Scaffold |
| PRD-FR-013 | Sale schedules | Pendiente | TDD-TS-009 | Propuesto |
| PRD-FR-014 | Branch stockouts | BDD-SC-026, BDD-SC-027, BDD-SC-048 | TDD-TS-015, TDD-TS-016, TDD-TS-027 | Scaffold |
| PRD-FR-015 | Price versioning | BDD-SC-026, BDD-SC-027, BDD-SC-048 | TDD-TS-015, TDD-TS-016, TDD-TS-027 | Scaffold |
| PRD-FR-016 | External product mappings | BDD-SC-013 | TDD-TS-009 | Disenado |
| PRD-FR-017 | Canonical catalog consistency | BDD-SC-110, BDD-SC-111, BDD-SC-114, BDD-SC-122, BDD-SC-129 | TDD-TS-047, TDD-TS-050, TDD-TS-051, TDD-TC-040, TDD-TC-043, TDD-TC-044 | Scaffold |
| PRD-FR-018 | POS administrative hub | BDD-SC-113, BDD-SC-118, BDD-SC-119, BDD-SC-120, BDD-SC-121, BDD-SC-122, BDD-SC-123, BDD-SC-125, BDD-SC-126, BDD-SC-127, BDD-SC-128, BDD-SC-129, BDD-SC-130, BDD-SC-133, BDD-SC-136, BDD-SC-137, BDD-SC-138, BDD-SC-139, BDD-SC-141, BDD-SC-142, BDD-SC-143 | TDD-TS-047, TDD-TS-050, TDD-TS-051, TDD-TS-052, TDD-TC-040, TDD-TC-043, TDD-TC-044, TDD-TC-045 | Scaffold |
| PRD-FR-019 | Canonical branch context | BDD-SC-112, BDD-SC-118, BDD-SC-121, BDD-SC-125, BDD-SC-131, BDD-SC-134, BDD-SC-135, BDD-SC-140, BDD-SC-157, BDD-SC-162 | TDD-TS-047, TDD-TS-050, TDD-TS-051, TDD-TS-052, TDD-TS-055, TDD-TC-044, TDD-TC-045, TDD-TC-048 | Scaffold |
| PRD-FR-020 | Orders module | BDD-SC-001, BDD-SC-030, BDD-SC-063, BDD-SC-066, BDD-SC-160, BDD-SC-161 | TDD-TS-003, TDD-TS-018, TDD-TS-037, TDD-TS-055, TDD-TC-031, TDD-TC-048 | Scaffold |
| PRD-FR-021 | Channel adapters | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-022 | Integration idempotency | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-023 | Original payload retention | BDD-SC-003 | TDD-TS-009 | Disenado |
| PRD-FR-024 | Customer/address/channel data | BDD-SC-016, BDD-SC-159, BDD-SC-160 | TDD-TS-008, TDD-TS-055, TDD-TC-048 | Scaffold |
| PRD-FR-025 | Order totals and payments | BDD-SC-011, BDD-SC-030, BDD-SC-032, BDD-SC-033, BDD-SC-062, BDD-SC-066 | TDD-TS-005, TDD-TS-018, TDD-TS-020, TDD-TS-037, TDD-TC-031 | Scaffold |
| PRD-FR-026 | Historical catalog snapshots | TDD-TC-004 | TDD-TS-003 | Disenado |
| PRD-FR-027 | Order events/state machine | BDD-SC-001, BDD-SC-030 | TDD-TS-003, TDD-TS-018 | Implementado |
| PRD-FR-028 | Cancellation rules | BDD-SC-006, BDD-SC-007, BDD-SC-054, BDD-SC-055 | TDD-TS-003, TDD-TS-031, TDD-TS-032 | Implementado |
| PRD-FR-029 | Notes by order/product/station | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-030 | Offline-safe folios | BDD-SC-001, BDD-SC-002, BDD-SC-030 | TDD-TS-004, TDD-TS-018, TDD-TC-031 | Scaffold |
| PRD-FR-031 | Customer identity and phones | BDD-SC-069, BDD-SC-157 | TDD-TS-039, TDD-TS-055, TDD-TC-048 | Scaffold |
| PRD-FR-032 | Unlimited customer addresses | BDD-SC-070, BDD-SC-159, BDD-SC-160 | TDD-TS-039, TDD-TS-055 | Scaffold |
| PRD-FR-033 | Separate customer tax profile | BDD-SC-069, BDD-SC-073 | TDD-TS-039 | Scaffold |
| PRD-FR-034 | Customer and address snapshots | BDD-SC-071, BDD-SC-072, BDD-SC-158 | TDD-TS-039, TDD-TS-055 | Scaffold |
| PRD-FR-035 | Repeat order with current rules | BDD-SC-074 | TDD-TS-039 | Scaffold |
| PRD-FR-040 | Production tasks | BDD-SC-004, BDD-SC-031 | TDD-TS-006, TDD-TS-019 | Scaffold |
| PRD-FR-041 | Station model | BDD-SC-004, BDD-SC-031 | TDD-TS-006, TDD-TS-019 | Scaffold |
| PRD-FR-042 | Timing, priority and delays | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-043 | Production state machine | BDD-SC-004, BDD-SC-031 | TDD-TS-006, TDD-TS-019 | Scaffold |
| PRD-FR-044 | Authorized reopen/reprint | BDD-SC-018, BDD-SC-036 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-045 | Incidents and stockouts | BDD-SC-004 | TDD-TS-006 | Propuesto |
| PRD-FR-046 | Print service | BDD-SC-018, BDD-SC-035, BDD-SC-036 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-047 | Printer routing | BDD-SC-018, BDD-SC-035 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-048 | Print audit trail | BDD-SC-018, BDD-SC-035, BDD-SC-036 | TDD-TS-011, TDD-TS-022 | Scaffold |
| PRD-FR-050 | Cash shifts | BDD-SC-011, BDD-SC-028, BDD-SC-029, BDD-SC-061, BDD-SC-066 | TDD-TS-005, TDD-TS-017, TDD-TS-037, TDD-TC-031 | Scaffold |
| PRD-FR-051 | Opening cash fund | BDD-SC-011, BDD-SC-028, BDD-SC-061, BDD-SC-066 | TDD-TS-005, TDD-TS-017, TDD-TS-037, TDD-TC-031 | Scaffold |
| PRD-FR-052 | Cash movements | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-053 | Payment methods | BDD-SC-012, BDD-SC-032, BDD-SC-033, BDD-SC-062, BDD-SC-063 | TDD-TS-005, TDD-TS-020, TDD-TS-037 | Scaffold |
| PRD-FR-054 | Immutable payments | BDD-SC-012, BDD-SC-032, BDD-SC-033, BDD-SC-062 | TDD-TS-005, TDD-TS-020, TDD-TS-037 | Scaffold |
| PRD-FR-055 | Partial close | BDD-SC-011 | TDD-TS-005 | Propuesto |
| PRD-FR-056 | Cash count differences | BDD-SC-011, BDD-SC-034 | TDD-TS-005, TDD-TS-021 | Scaffold |
| PRD-FR-057 | Final close | BDD-SC-011, BDD-SC-029, BDD-SC-034, BDD-SC-061, BDD-SC-066 | TDD-TS-005, TDD-TS-017, TDD-TS-021, TDD-TS-037, TDD-TC-031 | Scaffold |
| PRD-FR-058 | Reopen evidence and audit | BDD-SC-011 | TDD-TS-005 | Disenado |
| PRD-FR-059 | Driver cash settlement | BDD-SC-016 | TDD-TS-008 | Disenado |
| PRD-FR-060 | Inventory ledger | BDD-SC-005, BDD-SC-049, BDD-SC-050, BDD-SC-056, BDD-SC-058 | TDD-TS-002, TDD-TS-028, TDD-TS-033, TDD-TS-035 | Scaffold |
| PRD-FR-061 | Units by process | BDD-SC-005, BDD-SC-049, BDD-SC-050 | TDD-TS-002, TDD-TS-028 | Scaffold |
| PRD-FR-062 | Exact conversions | BDD-SC-005, BDD-SC-049, BDD-SC-050 | TDD-TS-002, TDD-TS-028 | Scaffold |
| PRD-FR-063 | Inventory reservation | BDD-SC-005, BDD-SC-052 | TDD-TS-002, TDD-TS-030 | Scaffold |
| PRD-FR-064 | Consumption | BDD-SC-005, BDD-SC-053 | TDD-TS-002, TDD-TS-030 | Scaffold |
| PRD-FR-065 | Release reservation | BDD-SC-006, BDD-SC-054 | TDD-TS-002, TDD-TS-031 | Scaffold |
| PRD-FR-066 | Post-production cancellation | BDD-SC-007, BDD-SC-055 | TDD-TS-002, TDD-TS-032 | Scaffold |
| PRD-FR-067 | Lots and expirations | BDD-SC-010 | TDD-TS-002 | Disenado |
| PRD-FR-068 | Counts and authorized adjustments | BDD-SC-021, BDD-SC-057, BDD-SC-105, BDD-SC-106, BDD-SC-107, BDD-SC-108, BDD-SC-109, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141 | TDD-TS-002, TDD-TS-034, TDD-TS-046, TDD-TS-052, TDD-TC-039, TDD-TC-045 | Scaffold |
| PRD-FR-069 | Transfers | BDD-SC-015, BDD-SC-100, BDD-SC-101, BDD-SC-102, BDD-SC-103, BDD-SC-104, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141 | TDD-TS-002, TDD-TS-045, TDD-TS-052, TDD-TC-038, TDD-TC-045 | Scaffold |
| PRD-FR-070 | Kardex and theoretical stock | BDD-SC-005, BDD-SC-049, BDD-SC-050, BDD-SC-056, BDD-SC-162 | TDD-TS-002, TDD-TS-028, TDD-TS-033, TDD-TS-055 | Scaffold |
| PRD-FR-071 | Classified real waste | BDD-SC-095, BDD-SC-096, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141 | TDD-TS-044, TDD-TS-052, TDD-TC-045 | Scaffold |
| PRD-FR-072 | Configurable waste reasons | BDD-SC-095, BDD-SC-096 | TDD-TS-044 | Scaffold |
| PRD-FR-073 | Authorized idempotent waste confirmation | BDD-SC-097, BDD-SC-098 | TDD-TS-044, TDD-TC-037 | Scaffold |
| PRD-FR-074 | Immutable waste compensation | BDD-SC-099 | TDD-TS-044, TDD-TC-037 | Scaffold |
| PRD-FR-075 | Waste costing and reconciliation | BDD-SC-097, BDD-SC-099 | TDD-TS-044, TDD-TC-037 | Scaffold |
| PRD-FR-076 | Transfer document and states | BDD-SC-100 | TDD-TS-045 | Scaffold |
| PRD-FR-077 | Authorized idempotent transfer out | BDD-SC-101, BDD-SC-102 | TDD-TS-045, TDD-TC-038 | Scaffold |
| PRD-FR-078 | Explicit destination receipt | BDD-SC-103, BDD-SC-104 | TDD-TS-045, TDD-TC-038 | Scaffold |
| PRD-FR-079 | Transfer differences and costing | BDD-SC-103, BDD-SC-104 | TDD-TS-045, TDD-TC-038 | Scaffold |
| PRD-FR-080 | Recursive recipes | BDD-SC-008, BDD-SC-051, BDD-SC-056, BDD-SC-086, BDD-SC-087 | TDD-TS-001, TDD-TS-029, TDD-TS-033, TDD-TS-042 | Scaffold |
| PRD-FR-081 | Cycle detection | BDD-SC-009, BDD-SC-088 | TDD-TS-001, TDD-TS-042 | Scaffold |
| PRD-FR-082 | Recipe versioning | BDD-SC-051, BDD-SC-085, TDD-TC-004 | TDD-TS-001, TDD-TS-029, TDD-TS-042 | Scaffold |
| PRD-FR-083 | Yield | BDD-SC-010 | TDD-TS-001 | Disenado |
| PRD-FR-084 | Planned and real waste | BDD-SC-010, BDD-SC-084 | TDD-TS-001, TDD-TS-042 | Scaffold |
| PRD-FR-085 | Batch production | BDD-SC-010, BDD-SC-086, BDD-SC-087, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141 | TDD-TS-006, TDD-TS-042, TDD-TS-052, TDD-TC-045 | Scaffold |
| PRD-FR-086 | Lot traceability | BDD-SC-010 | TDD-TS-002 | Disenado |
| PRD-FR-087 | Real batch cost | BDD-SC-010, BDD-SC-086 | TDD-TS-001, TDD-TS-042 | Scaffold |
| PRD-FR-088 | Theoretical product cost | BDD-SC-008, BDD-SC-051, BDD-SC-084, BDD-SC-085 | TDD-TS-001, TDD-TS-029, TDD-TS-042 | Scaffold |
| PRD-FR-089 | Weighted average cost | BDD-SC-005 | TDD-TS-001 | Disenado |
| PRD-FR-090 | Standard cost | BDD-SC-008 | TDD-TS-001 | Disenado |
| PRD-FR-091 | Central suppliers | BDD-SC-075, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141, BDD-SC-142 | TDD-TS-040, TDD-TS-052, TDD-TC-045 | Scaffold |
| PRD-FR-092 | Supplier contacts and branch terms | BDD-SC-075, BDD-SC-076 | TDD-TS-040 | Scaffold |
| PRD-FR-093 | Purchase presentations | BDD-SC-077, BDD-SC-078 | TDD-TS-040 | Scaffold |
| PRD-FR-094 | Informational presentation prices | BDD-SC-077 | TDD-TS-040 | Scaffold |
| PRD-FR-095 | Modifier groups and cardinality | BDD-SC-089, BDD-SC-090 | TDD-TS-043 | Scaffold |
| PRD-FR-096 | Modifier inventory effects and kitchen text | BDD-SC-091, BDD-SC-092, BDD-SC-093 | TDD-TS-043, TDD-TC-036 | Scaffold |
| PRD-FR-097 | Effective modifier snapshot | BDD-SC-089, BDD-SC-094 | TDD-TS-043 | Scaffold |
| PRD-FR-098 | Modified reservation and consumption | BDD-SC-091, BDD-SC-092, BDD-SC-093 | TDD-TS-043, TDD-TC-036 | Scaffold |
| PRD-FR-099 | Backend modifier pricing | BDD-SC-094 | TDD-TS-043, TDD-TC-036 | Scaffold |
| PRD-FR-100 | Direct receipts | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-101 | Supplier presentation and lot | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-102 | XML import | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-103 | XML duplicate | BDD-SC-014 | TDD-TS-007 | Disenado |
| PRD-FR-104 | Supplier mappings | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-105 | Accounts payable | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-106 | AP payments and balances | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-107 | XML evidence retention | BDD-SC-013 | TDD-TS-007 | Disenado |
| PRD-FR-108 | Direct purchase and cash reconciliation | BDD-SC-079, BDD-SC-080, BDD-SC-081, BDD-SC-138, BDD-SC-139, BDD-SC-140, BDD-SC-141 | TDD-TS-041, TDD-TS-052, TDD-TC-045 | Scaffold |
| PRD-FR-109 | Receipt-driven weighted average cost | BDD-SC-082 | TDD-TS-041 | Scaffold |
| PRD-FR-110 | Purchase idempotency and compensations | BDD-SC-080, BDD-SC-081 | TDD-TS-041 | Scaffold |
| PRD-FR-111 | Base inventory cost policy | BDD-SC-082, BDD-SC-083 | TDD-TS-041 | Scaffold |
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
| PRD-FR-190 | Idempotent legacy import batches | BDD-SC-144 | TDD-TS-053, TDD-TC-046 | Scaffold |
| PRD-FR-191 | Branch-exclusive imported catalogs | BDD-SC-145, BDD-SC-146, BDD-SC-149, BDD-SC-150 | TDD-TS-053, TDD-TC-046 | Scaffold |
| PRD-FR-192 | Product review before sale | BDD-SC-145, BDD-SC-152, BDD-SC-154 | TDD-TS-053, TDD-TC-046, TDD-TS-054, TDD-TC-047 | Scaffold |
| PRD-FR-193 | Incomplete presentation and recipe review | BDD-SC-147, BDD-SC-148, BDD-SC-152, BDD-SC-153 | TDD-TS-053, TDD-TC-046, TDD-TS-054, TDD-TC-047 | Scaffold |
| PRD-FR-194 | Legacy cost is non-operational reference | BDD-SC-146 | TDD-TS-053, TDD-TC-046 | Scaffold |
| PRD-FR-195 | Paginated branch customer directory | BDD-SC-149, BDD-SC-150, BDD-SC-157, BDD-SC-158 | TDD-TS-053, TDD-TS-055, TDD-TC-046, TDD-TC-048 | Scaffold |
| PRD-FR-196 | Scoped imported catalog adjustments | BDD-SC-151, BDD-SC-152, BDD-SC-153, BDD-SC-154, BDD-SC-155 | TDD-TS-053, TDD-TC-046, TDD-TS-054, TDD-TC-047 | Scaffold |
| PRD-FR-197 | Import retry and audit | BDD-SC-144, BDD-SC-151 | TDD-TS-053, TDD-TC-046 | Scaffold |

## Requisitos no funcionales

| Requisito | Diseno | Escenario BDD | Suite TDD | Estado |
|---|---|---|---|---|
| PRD-NFR-001 | Offline-first gateway | BDD-SC-001 | TDD-TS-004 | Disenado |
| PRD-NFR-002 | Idempotency and command log | BDD-SC-002, BDD-SC-003 | TDD-TS-004, TDD-TS-009 | Disenado |
| PRD-NFR-003 | Performance envelope | Pendiente | Performance tests | Propuesto |
| PRD-NFR-004 | Local latency | BDD-SC-001 | Performance tests | Propuesto |
| PRD-NFR-005 | Cloud latency | BDD-SC-003 | Performance tests | Propuesto |
| PRD-NFR-006 | Security | BDD-SC-021, BDD-SC-057, BDD-SC-059, BDD-SC-060, BDD-SC-061, BDD-SC-063, BDD-SC-064, BDD-SC-065, BDD-SC-066 | TDD-TS-012, TDD-TS-034, TDD-TS-036, TDD-TS-037, TDD-TC-031 | Scaffold |
| PRD-NFR-007 | Auditability | BDD-SC-007, BDD-SC-012, BDD-SC-021 | TDD-TS-012 | Disenado |
| PRD-NFR-008 | Recovery | Pendiente | Recovery tests | Propuesto |
| PRD-NFR-009 | Observability | BDD-SC-023, BDD-SC-024 | TDD-TS-009, TDD-TS-013 | Scaffold |
| PRD-NFR-010 | Maintainability | BDD-SC-024, Architecture tests | TDD-TS-013, Architecture tests | Scaffold |
| PRD-NFR-011 | Portability | BDD-SC-024, BDD-SC-061, Docker/Easypanel | TDD-TS-013, TDD-TC-030, CI checks | Scaffold |
| PRD-NFR-012 | Exact arithmetic | BDD-SC-008 | TDD-TS-001 | Disenado |
| PRD-NFR-013 | Future multi-company | Organization module | TDD-TS-012 | Disenado |
| PRD-NFR-014 | Privacy | Security design | TDD-TS-012 | Propuesto |
| PRD-NFR-015 | Gateway compatibility | BDD-SC-018 | TDD-TS-011 | Disenado |
| PRD-NFR-016 | Frontend CI quality gate | BDD-SC-115 | TDD-TS-048, TDD-TC-041 | Scaffold |
| PRD-NFR-017 | Alembic revision capacity | BDD-SC-116, BDD-SC-117 | TDD-TS-049, TDD-TC-042 | Scaffold |
| PRD-NFR-018 | Operational localization | BDD-SC-156 | TDD-TS-055, TDD-TC-048 | Scaffold |

## Regla de mantenimiento

No se acepta una nueva historia sin:

- requisito PRD,
- impacto SDD,
- escenario BDD,
- suite y caso TDD,
- estado de implementacion.
