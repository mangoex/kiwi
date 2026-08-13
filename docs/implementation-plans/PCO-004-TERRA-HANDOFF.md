# PCO-004 — handoff de implementación a Terra Alto

**Estado:** implementación local cerrada con evidencia dirigida; PostgreSQL aislado, canary,
despliegue y observación productiva siguen pendientes. No es una autorización de publicación.

## 1. Autoridad y alcance

Implementar exclusivamente `PRD-FR-208/218`, `BDD-SC-284/285/292/307/308` y
`TDD-TS-080/TC-076/090/091`, conforme a SDD §38.2.3 y `SDD-ADR-026`.

Incluye:

1. Apertura de turno idempotente.
2. Cierre operativo transaccional separado del corte.
3. Atribución del pago al turno `OPEN` de la caja que cobra.
4. Snapshots históricos de familia y venta por pago/línea.
5. Monitor de ventas y drill-down con cálculos Python.
6. POS en español, rutas/permiso, estados accesibles y responsive.
7. Migración `0038`, contratos, auditoría, logs-métrica, pruebas y runbook.

Excluye estrictamente:

- `UserCashCut`, contado/diferencia/tolerancia y cualquier PCO-006;
- reapertura de pedidos o turnos, PCO-005;
- venta por insumos, gasto, receta o reportes PCO-007;
- outbox/inbox/offline PCO-008;
- estación, impresión, Excel/descarga o formato especial de nota de consumo;
- tasa fiscal inferida, implementación de cortesías FR-205 o cambios de permisos;
- cierre o alteración de turnos/datos productivos.

No tocar archivos no rastreados del usuario. No commit, push, PR, merge, deploy ni acceso externo.

## 2. Orden obligatorio RED → GREEN

1. Confirmar branch/cwd/status y ejecutar baseline dirigido.
2. Escribir primero las pruebas nuevas y registrar el RED esperado por ausencia de `0038`, rutas y
   servicios. No provocar RED mediante sintaxis rota o fixtures inválidos.
3. Implementar migración/modelos.
4. Implementar dominio y concurrencia.
5. Implementar API y JSON Schemas.
6. Implementar POS y enlace Admin sin duplicar el monitor.
7. Ejecutar pruebas dirigidas GREEN.
8. Ejecutar suites completas, lint, typecheck, builds y `git diff --check`.
9. Entregar a Sol lista exacta de archivos, evidencia RED/GREEN, riesgos y gates omitidos.

## 3. Migración `0038_cash_shift_closures_sales_monitor`

Crear una única head lineal desde `0037_cash_movement_ledger`.

### 3.1 `cash_shift_closures`

Columnas mínimas:

- `id`, `organization_id`, `branch_id`, `cash_shift_id UNIQUE`;
- `register_code_snapshot`;
- `closed_by_user_id`;
- `summary_snapshot JSON NOT NULL`;
- `closed_at`, `created_at` UTC.

No se actualiza ni elimina por dominio. El JSON congela:

- `sales_total_cents`;
- `payment_total_cents`;
- `cash_payment_cents`;
- `opening_cash_cents`;
- `deposit_cents`, `withdrawal_cents`;
- `excluded_movement_count`;
- `expected_cash_cents`;
- `confirmed_payment_count`, `closed_order_count`.

### 3.2 `cash_shift_commands`

Columnas mínimas:

- `id`, `organization_id`, `actor_user_id`, `cash_shift_id NULLABLE`;
- `command_type=open|close`;
- `idempotency_key`, `request_hash`, `result JSON`, `status=completed`;
- `created_at`;
- `UNIQUE (organization_id, idempotency_key)`.

El hash canónico de `open` incluye actor, sucursal, caja y fondo. El de `close` incluye actor e ID del
turno. La respuesta persistida nunca incluye la key ni el hash.

### 3.3 Turno activo

Recrear `uq_cash_shifts_open_register` para considerar activos `OPEN` y `CLOSING`, tanto en SQLite
como PostgreSQL. Hacer preflight de duplicados por sucursal/caja antes de cambiar el índice. Preservar
estados legacy `CLOSED`; no normalizarlos destructivamente.

### 3.4 Familia congelada

Agregar a `order_lines`:

- `family_id_snapshot`;
- `family_name_snapshot`;
- `family_snapshot_source=captured|legacy_catalog_backfill`.

El upgrade completa cada línea legacy mediante `order_lines.product_id -> products.category_id ->
product_categories`. Una relación faltante, vacía, cross-org o incoherente aborta antes de crear una
historia ambigua. Nuevas creaciones/enmiendas capturan ID/nombre en la misma transacción.

### 3.5 Snapshots de venta

Crear `sales_operation_snapshots` uno-a-uno con `payments.id`:

- IDs de organización, sucursal, pago, pedido y turno de cobro;
- `register_code_snapshot`, `folio_snapshot`, `service_type_snapshot`, moneda;
- `gross_cents`, `net_cents`, `discount_cents NULL`, `courtesy_cents NULL`, `tax_cents NULL`;
- `quality_status=captured|legacy_backfill|incomplete`;
- `confirmed_at`, `created_at`.

Crear `sales_operation_line_snapshots`:

- snapshot/pago, `order_line_id`, producto ID/nombre, familia ID/nombre/origen;
- cantidad;
- `gross_cents`, `net_cents NULL`, `discount_cents NULL`, `courtesy_cents NULL`,
  `tax_cents NULL`;
- unicidad por snapshot + línea.

Para pagos legacy:

- bruto = suma de líneas activas;
- neto de cabecera = importe confirmado;
- si bruto = pago, descuento/cortesía/impuesto registrado son cero conocido y los netos de línea
  pueden copiar bruto;
- si no reconcilia, no prorratear: cabecera neta sigue conocida, componentes y netos de línea quedan
  `NULL`, calidad `incomplete`;
- origen de familia = `legacy_catalog_backfill`.

Agregar índices para periodo/sucursal, turno/caja/servicio y familia. No agregar dependencia crítica.

### 3.6 Downgrade

El downgrade a `0037`:

- borra sólo snapshots `legacy_backfill` regenerables;
- se bloquea si existe cierre, comando, snapshot `captured` o línea con familia `captured`;
- restaura el índice OPEN previo y retira sólo estructuras `0038`;
- pasa `0037 -> 0038 -> 0037 -> 0038` en SQLite y PostgreSQL aislado con huella legacy.

## 4. Dominio Python

### 4.1 Apertura

Agregar un servicio idempotente que valide payload estricto, actor, `cash.shift.open`, scope, caja no
vacía y fondo entero no negativo. Reservar la escritura SQLite antes de lecturas sensibles. Replay
idéntico devuelve el turno original; payload/actor diferente con la misma key devuelve
`idempotency_conflict`. Carrera de dos aperturas confirma una y normaliza la otra como replay o
`cash_shift_already_open`, nunca `IntegrityError` sin traducir.

### 4.2 Cierre operativo

Agregar `close_cash_shift_operationally(session, shift_id, idempotency_key, actor_id)`:

1. Reserva SQLite/lock PostgreSQL.
2. Carga el turno exacto por ID, autoriza `cash.shift.close` en su sucursal y exige `OPEN`.
3. Comprueba/reproduce comando idempotente.
4. Cambia a `CLOSING` dentro de la transacción.
5. Calcula el resumen exclusivamente en Python.
6. Inserta un único cierre y auditoría.
7. Cambia a `OPERATIVELY_CLOSED` y confirma una sola vez.

Una excepción inyectada entre pasos 4–7 revierte estado, cierre, comando y auditoría. No llamar
`close_cash_shift_with_cut`, no escribir `cash_shift_cuts`, no recibir contado y no crear corte.

`get_cash_shift_summary` debe devolver `summary_snapshot` para un turno cerrado; nunca recalcularlo
contra filas posteriores. El resumen vivo de turno OPEN usa pagos confirmados cuyo
`payments.cash_shift_id` coincide con el turno, no `orders.cash_shift_id`.

### 4.3 Pago bajo el guard

Cambiar la confirmación para exigir `register_id` explícito y no vacío. Antes de leer estado que pueda
cambiar, reservar SQLite; cargar pedido/scope, resolver y lockear el turno `OPEN` de la caja de cobro,
volver a validar pedido/pago bajo lock e insertar:

- `payments.cash_shift_id = turno de cobro`;
- payment/eventos/auditoría;
- snapshot de operación y líneas;
- estado `CLOSED` del pedido.

Todo se confirma junto. Si cierre ganó, devolver `cash_shift_not_open` sin payment, evento, snapshot
ni cambio de orden. Si pago ganó, el cierre posterior debe incluirlo. Actualizar ambos clientes POS
(cobro inmediato y Pedidos) para enviar la caja validada; no usar `CAJA-01` implícita.

Mantener historia: `orders.cash_shift_id` no cambia. No reescribir pagos existentes.

### 4.4 Snapshots nuevos

Creación y enmienda capturan familia desde el producto canónico en la misma transacción. Al pagar,
crear snapshots sólo desde líneas activas ya congeladas. Verificar:

- cantidad positiva;
- moneda consistente;
- suma de líneas contra pedido/pago;
- cero únicamente para componentes explícitamente ausentes en el dominio actual;
- cualquier inconsistencia devuelve `historical_snapshot_missing` o error estable y revierte pago.

### 4.5 Monitor y drill-down

Implementar `ReportingProjectionService` en Python, separado de controladores HTTP.

Filtros permitidos:

- `from_utc` y `to_utc` obligatorios, conscientes de zona, intervalo `[from,to)` y `from < to`;
- `branch_id`, `register_id`, `cash_shift_id`, `family_id`, `service_type`;
- `service_type` sólo `dine-in|takeout|delivery`;
- drill-down: `metric=gross|net|tax|discount|courtesy`, `limit 1..100`, cursor opaco.

Scope se autoriza siempre con `reports.sales.read`. Administrador branch-scope no puede omitir para
escapar ni inyectar otra sucursal; Dueño puede omitir o seleccionar una sucursal activa de su
organización. Ninguna consulta cruza organización.

Respuesta de resumen:

```json
{
  "applied_filters": {
    "from_utc": "...", "to_utc": "...", "branch_id": "...",
    "register_id": null, "cash_shift_id": null, "family_id": null,
    "service_type": null
  },
  "summary": {
    "gross": {"known_cents": 0, "unknown_operation_count": 0},
    "net": {"known_cents": 0, "unknown_operation_count": 0},
    "tax": {"known_cents": 0, "unknown_operation_count": 0},
    "discount": {"known_cents": 0, "unknown_operation_count": 0},
    "courtesy": {"known_cents": 0, "unknown_operation_count": 0},
    "order_count": 0, "line_count": 0, "item_quantity": 0,
    "legacy_backfilled_line_count": 0
  },
  "breakdowns": {"families": [], "services": []},
  "facets": {"cash_shifts": [], "families": [], "service_types": []},
  "data_quality": {"incomplete_operation_count": 0}
}
```

Cada breakdown lleva ID/label, cinco indicadores, `order_count`, `line_count` e `item_quantity`.
Resumen cuenta IDs de pedido distintos; una orden multifamilia cuenta una vez. Las sumas por familia
usan snapshots de línea y no catálogo vivo. `unknown_operation_count` cuenta operaciones distintas
con `NULL` para el indicador, no líneas. No usar SQL `float` ni agregados que oculten `NULL`; iterar
enteros en Python.

Drill-down devuelve los mismos `applied_filters`, `metric`, items y `next_cursor`. Cada item expone
sólo `payment_id`, `order_id`, `folio`, sucursal, turno, caja, servicio, fecha UTC, cinco indicadores
known/unknown, conteos y calidad; no cliente, evidencia, key ni payload. Orden estable descendente
`confirmed_at,payment_id`; cursor firmado/no adivinable no es obligatorio, pero sí opaco, validado y
estable.

## 5. API y contratos

Rutas canónicas:

- `POST /api/v1/cash/shifts/open` — header `Idempotency-Key`, JSON exacto
  `{branch_id, register_id, opening_cash_cents}`.
- `GET /api/v1/cash/shifts/current` — sucursal/caja; devuelve estado y último cierre si no hay OPEN.
- `GET /api/v1/cash/shifts` — filtros/cursor, lista scoped.
- `GET /api/v1/cash/shifts/{id}` — turno + cierre/snapshot scoped.
- `POST /api/v1/cash/shifts/{id}/close-operationally` — header, body `{}` exacto.
- `GET /api/v1/reports/sales-monitor`.
- `GET /api/v1/reports/sales-monitor/drill-down`.

Compatibilidad temporal:

- `/cash-shifts/open`, `/cash-shifts/current`, `/cash-shifts/summary` delegan a semántica canónica;
- `/cash-shifts/close` permite exactamente `{branch_id, register_id}`, exige key y resuelve turno
  OPEN; `counted_cash_cents`, esperado, diferencia o extras devuelven
  `cash_shift_counted_cash_forbidden` sin escritura;
- el POS nuevo no usa aliases.

Agregar JSON Schemas con `additionalProperties:false` para comando/response de turno, lista/detalle,
monitor y drill-down. Validar schemas en pruebas; no basta guardarlos. Códigos HTTP sugeridos:

- 400 filtros/payload/periodo inválido;
- 401 actor ausente/inválido;
- 403 permiso/scope;
- 404 turno inexistente;
- 409 estado, busy, contado prohibido o idempotency conflict.

## 6. POS y acceso Admin

### 6.1 Settings

Crear helper/reducer puro, sin fórmulas financieras. Estados:
`loading|open|closed|submitting|error`. Debe:

- consultar ruta canónica y fallar cerrado;
- mostrar controles sólo con permisos `cash.shift.read/open/close` correspondientes;
- parsear fondo a centavos exactos sin `parseFloat` y permitir cero;
- conservar key de apertura/cierre ante fallo de red incierto;
- impedir doble submit/cambio de intención mientras envía;
- cerrar por ID con body `{}` y mostrar “Cerrar operativamente”;
- explicar “El corte final queda pendiente”;
- mostrar actor, fecha y snapshot retornado sin recalcular;
- usar `role=status|alert`, confirmación accesible y botón Reintentar;
- eliminar `Cerrar Turno (Corte de Caja)` y todo `counted_cash_cents` del flujo.

### 6.2 Monitor

Crear `features/reports/SalesMonitor.tsx`, helper puro y CSS. Registrar `/sales-monitor` bajo
`PermissionRoute permission="reports.sales.read"`; el sidebar sólo muestra **Monitor de ventas** con
ese permiso. El item debe ser enlace/botón accesible por teclado.

La UI:

- inicia con el día local de la sucursal y convierte límites una sola vez a UTC;
- permite periodo, sucursal autorizada, caja, turno, familia y servicio;
- presenta tarjetas de cinco indicadores y sus faltantes;
- muestra breakdowns y drill-down sin `reduce` de dinero/conteos;
- distingue loading, error, vacío y datos; mantiene filtros al reintentar/paginar;
- no contiene controles excluidos por SC-292;
- a 1440x900 y 1000x800 no desborda la página; tabla tiene scroll interno y filtros/cards hacen wrap.

El item **Ventas** de Admin puede navegar a `/pos/sales-monitor` para hacer descubrible la superficie,
pero no se crea una segunda implementación ni se usan roles/nombres como autoridad.

## 7. Auditoría, logs-métrica y operación

Auditar apertura, cierre y denegaciones sensibles. Payload seguro: IDs, estado, conteos y componentes
de resumen; nunca key/hash, filtros completos, cliente o líneas. Registrar logs estructurados:

- `cash_shift_open_total{result}`;
- `cash_shift_operational_close_total{result}`;
- `cash_shift_guard_conflict_total{command}`;
- `sales_monitor_request_total{result}`;
- `sales_monitor_incomplete_operations`.

Usar el logger existente con campos estructurados; no agregar proveedor ni dependencia. Documentar en
`docs/10-operacion-easypanel.md`: upgrade `0038`, health/version, queries read-only de conteos,
eventos esperados, rollback de app, bloqueo de downgrade y canary con caja QA dedicada.

## 8. Pruebas mínimas obligatorias

Crear o separar:

- `apps/api/tests/test_cash_shift_operational_close.py`;
- `apps/api/tests/test_sales_monitor.py`;
- `apps/api/tests/test_pco004_migration.py`;
- `apps/api/tests/test_pco004_postgres.py`;
- pruebas de contratos;
- `tests/frontend/test_pos_operational_shift_sales_monitor.mjs` y script raíz/CI.

Cobertura:

1. Matriz Cajero/Cajero jefe/Líder/Supervisor/Administrador/Dueño y scope ajeno.
2. Actor ausente/inactivo/cross-org y payload que afirma autoridad.
3. Apertura replay/conflict/doble carrera/fondo inválido.
4. Cierre con esperado distinto de cero, sin cut ni diferencia.
5. Rechazo de contado y de cada propiedad adicional.
6. Cierre replay/conflict/otro actor/otro turno.
7. Fallo inyectado revierte `CLOSING`, cierre, comando y auditoría.
8. Carrera cierre vs movimiento, compra cash y pago en SQLite/PostgreSQL.
9. Pago diferido se atribuye a caja/turno de cobro; turno cerrado falla sin residuos.
10. Summary cerrado usa snapshot y no cambia ante filas posteriores sembradas.
11. Monitor con dos scopes, periodos límite, turnos, cajas, servicios y familias.
12. Orden multifamilia: count distinct una vez y centavos reconciliados.
13. Indicadores no-cero sembrados y `NULL` legacy; conocidos/faltantes exactos.
14. Cambio posterior de catálogo no altera familia ni resultados.
15. Drill-down conserva filtros/cursor, no filtra PII y rechaza cursor/limit inválidos.
16. JSON Schemas strict y TypeScript sin cálculos.
17. UI permisos, estados, key retry, rutas canónicas y SC-292 ausente.
18. Migración SQLite/PostgreSQL, downgrade seguro/bloqueado y una sola head.
19. Regresiones PCO-003: efectivo esperado, ledger, compra/compensación y guard.
20. Regresiones POS pago inmediato/diferido, enmiendas y builds.

## 9. Gates y comandos de entrega

Usar la virtualenv del repo y ejecutar, como mínimo:

```bash
.venv/bin/python -m pytest tests/architecture/test_traceability.py -q
.venv/bin/python -m pytest apps/api/tests/test_cash_shift_operational_close.py apps/api/tests/test_sales_monitor.py apps/api/tests/test_pco004_migration.py -q
.venv/bin/python -m pytest apps/api/tests/test_cash_ledger.py apps/api/tests/test_platform_api.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check apps/api tests
.venv/bin/python -m mypy apps/api/restaurant_os
node tests/frontend/test_pos_operational_shift_sales_monitor.mjs
pnpm typecheck
pnpm test
pnpm --filter @restaurantos/admin-web build
pnpm --filter @restaurantos/pos-web build
pnpm --filter @restaurantos/kds-web build
docker compose -f infra/docker/docker-compose.yml config
git diff --check
```

PostgreSQL usa una base local/aislada nombrada `pco004_*`, nunca `DATABASE_URL` productiva. La suite
debe validar el hostname/nombre y omitir con mensaje claro si falta URL. No llamar GREEN a
PostgreSQL, E2E/visual o producción si no se ejecutaron.

## 10. Criterio de devolución a Sol

Terra entrega únicamente cuando:

- pruebas RED se observaron y quedaron GREEN;
- matriz permanece `Scaffold/Disenado` hasta auditoría Sol;
- no existen escrituras de corte final ni cálculo frontend;
- migración y downgrade tienen evidencia SQLite y PostgreSQL aislado;
- suites completas, lint/typecheck/build/diff están verdes o cada omisión está identificada;
- estado Git enumera sólo paths intencionales y preserva todos los archivos del usuario.

## 11. Cierre local y relevo operativo

La evidencia local distingue explícitamente SQLite de PostgreSQL: la carrera cierre-vs-pago pasó con
dos sesiones SQLite; el gate PostgreSQL se omite deliberadamente hasta recibir una URL de base
`pco004_*` aislada y no productiva. La migración/modelos, contrato HTTP, monitor por snapshots,
cursores estrictos, preflight de moneda y logs-métrica tienen pruebas dirigidas locales. La prueba
frontend de contrato estático cubre zona de sucursal concreta, permiso/ruta y reglas responsive de
contención; no sustituye QA visual en navegador a 1440x900 y 1000x800.

Antes de declarar un entorno listo, ejecutar en el servicio API el procedimiento de
`docs/10-operacion-easypanel.md`, sección **PCO-004: cierre operativo y monitor de ventas**:

1. Respaldar PostgreSQL y confirmar una sola head `0038_cash_shift_closures_sales_monitor` en la
   imagen; confirmar que la base aún está en `0037_cash_movement_ledger`.
2. Ejecutar `alembic upgrade 0038_cash_shift_closures_sales_monitor`, luego `alembic current -v`,
   sin `stamp` ni edición de datos para superar un preflight.
3. Ejecutar el canary sólo con autorización operativa y caja exclusiva `QA-PCO004`: apertura/replay,
   pago de prueba si la política lo permite, cierre por ID con `{}`, replay y monitor UTC.
4. Revisar `/health/ready`, auditoría y métricas estructuradas; alertar resultados `error|conflict`
   de apertura/cierre/guard/monitor y `sales_monitor_incomplete_operations` sin inspeccionar PII.
5. Si falla aplicación, revertir sólo la aplicación y conservar `0038`; downgrade únicamente bajo
   las precondiciones y bloqueo de historia capturada descritos en el runbook.
