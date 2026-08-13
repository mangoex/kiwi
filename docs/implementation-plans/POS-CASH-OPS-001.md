# POS-CASH-OPS-001 — plan gobernado de caja, cuentas, corte y perfiles

**Estado:** PCO-001 y PCO-002 fueron validados, publicados, desplegados y migrados de forma controlada
en producción el 2026-08-11. PCO-003 fue implementado, auditado, publicado, desplegado y migrado en la
base productiva original el 2026-08-12, con respaldo, revisión `0037` y canary empresarial autenticado
verificados; retiro y compensación dejaron efecto neto cero. PCO-004 está autorizado para
especificación, implementación Terra, auditoría Sol y rollout controlado; no autoriza PCO-005+.

## Alcance y exclusiones

Incluye perfiles acumulativos, permisos/alcance, depósitos/retiros, conceptos versionados, libro compensatorio, cuentas, cierre operativo, monitor de ventas, corte por usuario y reportes históricos por insumo. Integra compras cash existentes sólo como movimiento enlazado y conserva el flujo de enmienda vigente. Excluye resolver reapertura real de pedido pagado/cerrado, impresora/Excel/estación/ficha de consumo del video, cambio de permisos productivos, migración automática a Dueño y cualquier big bang.

## Hechos, inferencias y gates de decisión

| Tipo | Elemento | Impacto / gate |
|---|---|---|
| Confirmado | Los seis perfiles y su herencia acumulativa; Dueño todas las sucursales y permisos persistidos de su organización. | PCO-001: permisos atómicos, no nombre de rol. |
| Confirmado por lectura externa | Los dos destinatarios iniciales existen, están activos, pertenecen a una misma organización y conservan Administrador corporativo legacy. | Precondición de bootstrap; preservar rol legacy, no ejecutar contra producción desde este plan. |
| Confirmado | Perfiles no Dueño sólo operan sucursales asignadas; sin asignación o `branch_id=NULL`, fail-closed. | PCO-001: guard backend por actor/permiso/alcance. |
| Confirmado, no ejecutado | La primera asignación de Dueño usa sólo el bootstrap interno aprobado, atómico y auditable. | Requiere ejecución humana controlada fuera de este worktree; PCO-001 no asigna usuarios en datos reales. |
| Confirmado | Retiro es efectivo manual con turno abierto; manejar caja no incluye corte final. | PCO-002+; no implementar en PCO-001. |
| Confirmado | Reapertura, corte, conceptos, receta y gasto/día operativo. | `OPEN-013A/B`→PCO-005; `014`→PCO-006; `015`→PCO-002; `016/017`→PCO-007. |
| Contradictorio | Cajero hoy abre/cierra; jerarquía nueva lo asigna a Cajero jefe. | `CONS-011`, Gate 1. |
| Contradictorio | Administrador corporativo actual tiene todo; Dueño nuevo tiene todo. | `CONS-012`, ADR-023, Gate 1. |
| Contradictorio | `PRD-FR-204` bloquea pedido pagado/producción; video dice reabrir. | `CONS-013`, Gate 2. |
| Contradictorio | UI envía contado cero y backend mezcla cierre/corte. | `CONS-014`, Gate 3. |

## Roles y permisos

La matriz canónica está en SDD §38.1. Regla operativa: permiso persistido + actor + alcance canónico en backend. Dueño usa alcance organizacional; todos los demás niegan una sucursal no asignada. Se conservan sin alteración los roles de cocina, bebidas, empaque, despachador, repartidor, inventarios, cuentas por pagar, auditor y receptor de traspaso. Cada superficie debe probar permiso negativo, guard de ruta y API; ocultar UI no autoriza.

## Incrementos verticales y tareas atómicas

### I0 — decisiones y baseline

1. **Completado documentalmente:** resolver `OPEN-011..017` y registrar responsable, alternativa elegida y fecha; artefacto: PRD/consistencia/ADR actualizados. `OPEN-013A/B` queda trazado aunque la ruta sea PCO-005.
2. Inventariar permisos/roles semilla, usuarios afectados y movimientos/cierres existentes en PostgreSQL y SQLite; depende de acceso read-only; artefacto: reporte de dry-run sin PII.
3. Definir fixtures reproducibles para seis perfiles, dos sucursales, caja, turno, pedido, receta y pagos; depende de 1; artefacto: fixtures y matriz actualizada.

### I1 — autorización y migración reversible

4. Escribir pruebas RED de permisos heredados/negativos, scope y roles especializados; depende de 1-3; artefactos: TDD-TS-077/TC-073 implementados.
5. Diseñar migración de permisos/roles con mapeo explícito, compatibilidad `cash.withdraw`, rollback y una sola head; depende de 2; artefacto: revisión Alembic propuesta y plan SQLite.
6. Implementar el cambio mínimo backend de autorización y migración; depende de 4-5; GREEN: pruebas
   unitarias/API SQLite, migración SQLite/PostgreSQL aislado y negativos. E2E por perfil permanece
   proyectado y no autoriza PCO-002+.

### I2 — movimientos y cierre operativo

7. RED de concepto, retiro/depósito, idempotencia, compensación y efectivo esperado; depende de I1; artefactos: TDD-TS-078 y TC-074/079/085..088. Offline permanece PCO-008.
8. Migrar ledger/conceptos y contratos versionados; depende de 7; reversibilidad: retirar sólo tablas nuevas si no hay datos no reversibles o bloquear downgrade explícitamente con evidencia.
9. Implementar servicio Python y POS mínimo; depende de 8; GREEN: movimiento, reintento, compensación, scope y fallo de red no confirmado. Outbox/inbox permanece PCO-008.
10. Separar cierre operativo de corte; depende de 9; GREEN: no `counted_cash_cents=0`, no corte implícito, auditoría y monitor de resumen.

### I3 — cuentas, monitor y reportes

11. RED de filtros, detalle snapshot, monitor/drill-down, receta histórica y permisos; depende de I2; artefactos: TDD-TS-079/080/082.
12. Implementar proyecciones Python y contratos de sólo lectura; depende de 11; GREEN: `Decimal`, snapshots, branches y rutas guardadas.
13. Implementar UI en español y E2E/QA visual de cada perfil, desktop y ancho reducido; depende de 12; GREEN: estados vacío/carga/error, foco/teclado/contraste y contención del layout.

### I4 — corte por usuario y reapertura gobernada

14. Con decisiones `OPEN-013A/B` y `OPEN-014` ya registradas, RED de solicitud request-only,
   autorización/aplicación y corte/reapertura en sus PCO posteriores; depende del incremento
   correspondiente, no de una decisión pendiente; artefactos: TDD-TS-079/081/086.
15. Implementar solicitud sin aplicar sólo con 013A; autorización/aplicación sólo con 013B; GREEN: no altera pagos/inventario/corte fuera de política y conserva estados terminales.
16. Implementar corte final y eventual reapertura compensatoria sólo con 014; GREEN: PostgreSQL/SQLite concurrencia, recibo, auditoría, rollback y asociación histórica de operación no reutilizable.

## Orden de migraciones y reversibilidad

Después de la head integrada: `roles_permissions_transition` → `cash_movement_concepts_ledger` → `cash_shift_operational_closures_user_cuts` → `cash_reporting_indexes` → `gateway_cash_outbox`. No renumerar ni mezclar con migraciones ajenas. La reversibilidad se diseña por fases: respaldo verificable de mapeo, columnas/tablas nuevas compatibles, escritura append-only, lectura dual si aplica, desactivación de rutas/flags y restauración de permisos mapeados. Nunca se elimina un pago, movimiento, snapshot, auditoría o concepto confirmado para bajar versión.

`Rollback de aplicación` desactiva rutas/flags y restaura una versión desplegada compatible; `downgrade de esquema` retira sólo estructuras sin historia o deja esquema compatible inerte; `compensación de negocio` crea el evento/movimiento inverso referenciado. Son procedimientos independientes, con simulación de fallo y reversión aprobada por humano antes de R3. Cada paso prueba PostgreSQL y SQLite `head -> upgrade -> rollback de aplicación -> downgrade seguro/re-upgrade`, y conserva evidencia sin declarar el downgrade destructivo como reversible.

## QA funcional y visual

Para Cajero, Cajero jefe, Líder, Supervisor, Administrador y Dueño: iniciar sesión, comprobar navegación permitida/ausente, intentar una capacidad superior y una sucursal ajena, verificar actor/auditoría y estado de error. Para los estados afectados: turno abierto/cierre operativo, movimiento válido/denegado/compensado, lista/detalle de cuentas, monitor vacío/carga/error/datos, corte pendiente/finalizado/conflicto, offline pending_sync/denegado. QA visual mide contención de paneles anidados, responsive, foco, contraste, lectura en español y no trata un padre limitado como evidencia del contenido interno.

## Rollout y rollback

PCO-001/002/003 ya cuentan con publicación, respaldo y migración productiva controlada. PCO-003
conservó los conteos preexistentes; su canary autenticado verificó ledger/permisos/efectivo esperado
y compensó el movimiento para dejar efecto neto cero. PCO-004 mantiene su propio rollout pendiente.
Para rollback: congelar comandos nuevos, preservar auditoría y
compensaciones, restaurar mapeo de permisos y desactivar proyecciones/rutas; el downgrade `0037 ->
0036` sólo es admisible sin historia PCO-003 y el respaldo `pre-pco003-2026-08-12` requiere
restauración humana controlada.

## Riesgos R3 y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Efectivo, pagos o corte duplicado | Centavos, idempotencia, lock/índice único, append-only y pruebas concurrentes. |
| Reapertura altera historia financiera/productiva | Solicitud sin mutación y gate explícito de Dueño. |
| Escalación por rol/UI o branch_id | Permiso + scope backend, actor obligatorio, negativos, auditoría de denegación. |
| Receta actual reescribe reporte histórico | Snapshot/versiones aplicadas y cálculo Python Decimal. |
| Offline declara éxito falso | `pending_sync`, outbox/inbox, revalidación central y conflicto visible. |
| Migración pierde autoridad o especialidades | Dry-run, mapeo reversible, PostgreSQL/SQLite y rollback. |

## Threat model mínimo R3

| Activo | Actor/amenaza y vector | Control preventivo | Detección | Prueba definida | Riesgo residual |
|---|---|---|---|---|---|
| Permisos/organización | Usuario escala rol o altera branch/org en UI/payload | Permiso persistido, scope backend, no wildcard cliente | `authorization.denied`, traza | TDD-TS-077/087, BDD-SC-271/293 | Política de mapeo pendiente |
| Efectivo | Replay de idempotency key o comando offline | Idempotencia payload-hash, inbox/outbox, actor y turno revalidados | conflicto, lag y métrica | TDD-TS-078/083 | Dispositivo comprometido offline |
| Corte | Doble corte o intervalo parcial solapado | lock y asociación única por operación FINALIZED | `cash_cut_*`, alerta de diferencia | TDD-TS-081, TC-080, BDD-SC-295 | Política de periodo pendiente |
| Evidencia/PII | Archivo/referencia o log filtra datos | referencia mínima, objeto fuera de log, controles de acceso | escaneo de logs/auditoría | TDD-TS-086/087 | Retención pendiente |
| Historia | Reapertura/modificación altera pago, inventario o receta | solicitud sin mutación, snapshots, step-up/gate | auditoría before/after | TDD-TS-079/082/086 | PCO-005/007 aún no implementados |
| Migración | Downgrade borra datos o altera permisos | fases compatibles, backup/mapeo, no delete confirmado | dry-run y comparación | TDD-TS-084/087 | Operación de rollback humana |

Toda simulación de fallo, reversión de R3, compensación y promoción de gate requiere aprobación humana identificada, evidencia de dry-run y revisión del riesgo residual.

## Catálogo de tareas atómicas auditables

| ID | Requisito/BDD/TDD | Archivos o componentes previstos | Depende de | RED → GREEN / DoD |
|---|---|---|---|---|
| PCO-001 | FR-215, SC-270/271/277/290/298/299/300 ejecutados parcialmente; SC-272..276/291/293 proyectados; TS-077/TC-073/TC-081/TS-084/087/088 parciales, TC-082/083, TS-085 definido | API auth, Alembic roles, bootstrap interno, mapping reversible | Decisiones 011/012 y dos Dueños iniciales confirmados | branch NULL/Owner escalation/invariante/bootstrap/mapping/downgrade, aislamiento de rechazo, actor cross-org, stale mapping exacto y colisión de semilla GREEN; SQLite/PostgreSQL aislado GREEN y ejecución productiva controlada registrada el 2026-08-11; no autoriza PCO-002+ por sí sola |
| PCO-002 | FR-216, SC-278/296/301, TS-078/TC-084 | cash concepts, contratos, Admin/POS | Decisión 015, PCO-001 | concepto inválido/idempotencia/código mutable RED; versión/archivo/read efectivo e historia GREEN; sin ledger |
| PCO-003 | FR-216, SC-278..280/294/302..305, TS-078/TC-074/079/085..088 | ledger Python, PostgreSQL/SQLite del API, contratos y POS; sin outbox | PCO-002 | autoridad/fórmula/idempotencia/concurrencia/compatibilidad RED; movimiento/compra/compensación una vez GREEN |
| PCO-004 | FR-208/218, SC-284/285/292/307/308, TS-080/TC-076/090/091 | cierre/snapshots/monitor/rutas POS | PCO-003, ADR-026 | contado/carrera/catalogo vivo RED; cierre transaccional, pago atribuido y drill-down GREEN |
| PCO-005 | FR-217, SC-281..283, TS-079 | accounts/reopen workflow, detalle reutilizado | Decisión 013A/B, PCO-001 | aplicación directa RED; solicitud sin mutación GREEN |
| PCO-006 | FR-219, SC-286/287/295, TS-081 | cuts, locks, reportes | Decisión 014/017, PCO-004 | concurrencia/solape/reuso post-compensación RED; asociación histórica única GREEN |
| PCO-007 | FR-220, SC-288/297, TS-082 | proyecciones Python/reportes | Decisión 016/017, PCO-003 | unidad/gasto duplicado RED; snapshots/fuente única GREEN |
| PCO-008 | NFR-022, SC-289, TS-083 | gateway SQLite, inbox/outbox | PCO-003 | stale auth RED; revalidación/conflicto visible GREEN |
| PCO-009 | NFR-023, SC-291, TS-086 | auditoría, logs, métricas | PCO-001..008 | secreto/PII RED; trazas y redacción GREEN |
| PCO-010 | NFR-024, SC-290, TS-084/087 | Alembic, runbooks | PCO-001..009 | downgrade destructivo RED; fases/restore GREEN |

DoD común: requisito, escenario, suite, contrato, migración/rollback si aplica, auditoría, métricas, error sin escritura parcial y evidencia exacta. No se marca GREEN sin prueba realmente ejecutada.

## Gates 0–5 y evidencia exigida

| Gate | Condición de salida | Evidencia requerida |
|---|---|---|
| 0 | Documentación coherente y IDs sin colisión. | PRD/SDD/BDD/TDD/matriz/consistencia, `git diff --check`, test documental. |
| 1 | Dueño aprobó transición roles/alcance y ADR-023. | Decisión escrita, dry-run de mapeo y rollback revisado. |
| 2 | Dueño definió 013A, 013B, 014, 016 y 017; cada una bloquea sólo su PCO posterior. | Solicitud/autorización/aplicación→PCO-005; corte/tolerancia→PCO-006; receta/gasto/día→PCO-007. |
| 3 | I1-I2 RED→GREEN con migraciones reversibles. | Salidas PostgreSQL/SQLite, contratos, negativos, idempotencia y diff limpio. |
| 4 | I3-I4 validado por rol y offline. | Suites exactas, E2E/QA visual, logs/métricas y reconciliación controlada; Node >=22, typecheck/build y Playwright. |
| 5 | Rollout autorizado y flujo empresarial real. | SHA/artefacto, migración, runtime, operación controlada y rollback probado. |

PCO-002 sólo puede implementar conceptos; no puede adelantar movimientos (`PCO-003`), cierre/monitor
(`PCO-004`), reapertura (`PCO-005`), corte (`PCO-006`), receta/gastos/reportes (`PCO-007`) ni controles
visuales candidatos. Las decisiones ya no son gates; los incrementos y su evidencia siguen siendo gates.

## Evidencia de cierre PCO-001 — 2026-08-11

- Local: `239 passed`; Ruff y `git diff --check` limpios.
- PostgreSQL aislado `database-prueba`: `0034 -> 0035 -> 0034 -> 0035`, seis perfiles, 19 permisos,
  un grant de autoridad y auditoría de semilla.
- Bootstrap aislado: dos Dueños exactos, roles legacy preservados y replay `already_bootstrapped`.
- Mapping aislado: dry-run, `PENDING`, `MAPPED`, `REVERSED`, replays idempotentes, siete eventos de
  auditoría y cero mappings activos al cierre.
- Runtime aislado: `ready=ok` con PostgreSQL/Redis exclusivos y commit `02a9bc6`.
- CI PR #15: Python, Docker y frontend verdes. La base original se comprobó sólo en lectura en
  `0034_category_option_selection`; no recibió migración ni bootstrap PCO-001.

## Comandos de referencia por entorno

```bash
# Arquitectura/documentación
python3 -m pytest tests/architecture/test_traceability.py -q
git diff --check

# PostgreSQL de integración
RESTAURANTOS_DATABASE_URL=postgresql+psycopg://... python3 -m pytest apps/api/tests/integration -q

# Gateway SQLite
RESTAURANTOS_DATABASE_URL=sqlite+pysqlite:////tmp/restaurantos-cash.db python3 -m pytest apps/api/tests -q

# Frontend: gate exige Node >=22 antes de ejecutar
node --version
pnpm typecheck
pnpm --filter @restaurantos/pos-web build
pnpm exec playwright test
```
