# PCO-005A — consulta de cuentas y reapertura gobernada sin mutación

## 1. Autoridad y objetivo

Este handoff es la especificación vinculante para Terra. Se deriva de `PRD-FR-217`,
`OPEN-013A/013B`, `BDD-SC-281..283`, `TDD-TS-079`, `TDD-TC-075` y del catálogo
`POS-CASH-OPS-001`, que exige **aplicación directa RED y solicitud sin mutación GREEN**.

Objetivo: entregar la consulta histórica de cuentas y el primer incremento gobernado de
reapertura. Un Cajero jefe o perfil superior puede solicitarla; sólo Dueño puede aprobar o
rechazar. Ninguna ruta PCO-005A modifica pedidos, pagos, inventario, producción, cortes o snapshots.

## 2. Límites obligatorios

Incluido:

1. `GET /api/v1/orders/accounts` con alcance, filtros, búsqueda y cursor autoritativos.
2. Detalle histórico reutilizando `GET /api/v1/orders/{id}` y ampliándolo con snapshots y
   elegibilidad de reapertura.
3. Solicitud idempotente y auditable mediante
   `POST /api/v1/orders/{order_id}/reopen-requests`.
4. Consulta de solicitudes para Dueño mediante `GET /api/v1/orders/reopen-requests`.
5. Aprobación o rechazo idempotentes mediante `/approve` y `/reject`.
6. `/apply` existe como gate explícito y responde `order_reopen_policy_pending` sin escritura.
7. UI POS de cuentas, filtros, detalle, solicitud y decisión, siempre derivada de permisos backend.
8. Migración aditiva y reversible `0039_order_reopen_requests`.
9. Auditoría, logs y métricas redactados.

Excluido:

- alterar el estado o versión de un pedido protegido;
- llamar `amend_order` desde una solicitud aprobada;
- reversar, borrar o editar pagos;
- liberar o volver a reservar inventario;
- cancelar/recrear tareas de producción;
- crear merma o recuperación;
- alterar cierres operativos, cortes o asociaciones históricas;
- expirar solicitudes automáticamente, porque no existe TTL aprobado;
- PCO-005B aplicación compensatoria, PCO-006 cortes, PCO-007 reportes, PCO-008 offline;
- commit, push, PR, merge, despliegue o acceso a producción.

Ante cualquier contradicción se conserva la historia y se falla cerrado.

## 3. Reglas funcionales cerradas

### 3.1 Consulta de cuentas

`GET /api/v1/orders/accounts` requiere actor autenticado y `orders.read`. Parámetros:

- `branch_id`: opcional para Dueño; para otros actores sólo una sucursal autorizada;
- `from_utc`, `to_utc`: datetimes conscientes de zona, intervalo semiabierto `[from,to)` y
  `from < to`;
- `cash_shift_id`, `register_code`, `service_type=dine-in|takeout|delivery`;
- `q`: búsqueda normalizada de folio o nombre snapshot de cliente, 2 a 120 caracteres;
- `limit`: 1 a 100, default 50;
- `cursor`: opaco, estable y validado estrictamente.

El backend Python realiza filtros y paginación. El cursor contiene el orden estable
`created_at DESC, id DESC` y queda ligado al hash de filtros; reutilizarlo con filtros distintos
devuelve `order_accounts_cursor_invalid`. Datetimes ingenuos, intervalos inválidos, servicio no
canónico o límites fuera de rango fallan sin consulta parcial.

Cada elemento devuelve sólo datos necesarios: identidad, folio, sucursal, turno/caja, estado,
servicio, total entero en centavos, moneda, timestamp UTC, etiqueta snapshot de cliente, estado de
pago, resumen de producción, elegibilidad y estado de solicitud activa. No devuelve claves de
idempotencia ni evidencia completa.

Para pagos confirmados, el detalle usa `sales_operation_snapshots` y
`sales_operation_line_snapshots`; no consulta nombres o familias del catálogo vigente. Para pedidos
sin snapshot de venta conserva las revisiones append-only de líneas y marca la calidad, sin inventar
datos faltantes.

### 3.2 Elegibilidad de solicitud

La solicitud es necesaria cuando se cumple al menos una condición protegida:

- existe pago `CONFIRMED`;
- el pedido está `CLOSED`;
- alguna tarea de producción del pedido está fuera de `PENDING`.

Un pedido todavía editable por el flujo normal responde `order_reopen_not_required`. Un pedido
cancelado, rechazado, fallido o devuelto responde `order_reopen_not_eligible` hasta que exista una
política específica. La solicitud no cambia el resultado de `editable` ni habilita la ruta de
enmienda existente.

### 3.3 Creación de solicitud

Permiso mínimo: `orders.reopen.request`, ya asignado a Cajero jefe y superiores. El actor debe tener
alcance sobre la sucursal del pedido.

Contrato JSON:

```json
{
  "reason": "Corrección solicitada por el cliente",
  "evidence_refs": ["ticket:ABC-123"]
}
```

- `reason`: trim, 10 a 500 caracteres;
- `evidence_refs`: 1 a 10 referencias opacas, cada una trim de 1 a 500 caracteres, sin uploads;
- `Idempotency-Key`: obligatoria, trim de 12 a 160 caracteres.

La solicitud captura un `before_snapshot` mínimo e inmutable: versión/estado/total/moneda del pedido,
IDs/revisiones/totales de líneas, IDs/estado/importe/moneda de pagos, IDs/estado de tareas, y si existe
el identificador del snapshot de venta. No almacena secretos, tokens ni la clave de idempotencia
dentro del DTO o la auditoría.

Un replay con misma organización, clave, comando y hash canónico devuelve la misma solicitud. La
misma clave con otro pedido o payload devuelve `idempotency_conflict`. Sólo puede existir una
solicitud activa `REQUESTED|APPROVED` por pedido; otra clave devuelve
`order_reopen_request_active` y no crea filas.

### 3.4 Decisión de Dueño

`GET /api/v1/orders/reopen-requests` y las rutas de decisión requieren
`orders.reopen.authorize`, exclusivo de Dueño, y alcance organizacional/por sucursal revalidado por
backend.

Estados:

```text
REQUESTED -> APPROVED | REJECTED | EXPIRED
APPROVED  -> APPLIED
REJECTED | EXPIRED | APPLIED -> terminal
```

PCO-005A implementa `REQUESTED -> APPROVED|REJECTED`. `EXPIRED` queda reservado sin reloj automático
y `APPROVED -> APPLIED` permanece cerrado hasta PCO-005B.

`approve` y `reject` exigen `Idempotency-Key` y body `{ "decision_reason": "..." }`, con texto trim
de 10 a 500 caracteres. Replays idénticos devuelven la misma decisión; key/payload o transición
distinta devuelve `idempotency_conflict` o `order_reopen_transition_invalid`. Una decisión compara
la versión actual del pedido con `order_version_snapshot`; si cambió devuelve
`order_version_conflict` y conserva `REQUESTED`.

`POST /api/v1/orders/reopen-requests/{id}/apply`, incluso para Dueño y solicitud `APPROVED`, responde
`order_reopen_policy_pending`. Debe generar auditoría de rechazo en una transacción separada sólo si
el patrón de auditoría vigente permite conservar denegaciones sin contaminar una operación exitosa.
Nunca cambia la solicitud a `APPLIED`.

## 4. Modelo y migración `0039`

Crear `order_reopen_requests`:

- `id`, `organization_id`, `branch_id`, `order_id`;
- `status` con constraint `REQUESTED|APPROVED|REJECTED|EXPIRED|APPLIED`;
- `order_version_snapshot`, `order_status_snapshot`, `before_snapshot` JSON;
- `reason`, `evidence_refs` JSON;
- `requested_by_user_id`, `requested_at` UTC;
- `decided_by_user_id`, `decided_at` UTC, `decision_reason` nullable;
- `applied_by_user_id`, `applied_at` UTC, reservados y nulos en PCO-005A;
- `created_at`, `updated_at` UTC.

Constraints de coherencia:

- `REQUESTED`: sin decisión ni aplicación;
- `APPROVED|REJECTED`: decisión completa y aplicación nula;
- `EXPIRED`: sin actor de decisión y aplicación nula;
- `APPLIED`: aprobación y aplicación completas;
- razón no vacía, versión positiva y evidencia JSON no vacía validada también en dominio.

Índice único parcial por `order_id` para estados `REQUESTED|APPROVED`. Índices de lista por
`organization_id, branch_id, requested_at, id` y por `order_id, created_at`.

Crear `order_reopen_commands`:

- `id`, `organization_id`, `request_id` nullable para creación, `order_id`;
- `command_type=request|approve|reject|apply`;
- `idempotency_key`, `request_hash` SHA-256, `status=completed`, `response_snapshot` JSON;
- `actor_user_id`, `created_at` UTC;
- unique `(organization_id, idempotency_key)`.

No agregar FK desde pagos, inventario, tareas, cierres o snapshots hacia la solicitud.

El downgrade se bloquea con un error claro si cualquiera de las dos tablas contiene filas. Sólo una
base sin historia PCO-005A puede volver a `0038`. Probar `0038 -> 0039 -> 0038 -> 0039` en SQLite y
PostgreSQL aislado; producción nunca se usa como entorno de prueba destructiva.

## 5. Backend y contratos

Crear un `OrderReopenWorkflow` o módulo cohesivo; no añadir más lógica de reapertura a controladores.
Todas las operaciones usan transacción, locks apropiados y errores de dominio explícitos.

Contratos JSON Schema nuevos:

- `order-account-list-v1.schema.json`;
- `order-reopen-request-command-v1.schema.json`;
- `order-reopen-request-v1.schema.json`;
- `order-reopen-request-list-v1.schema.json`;
- `order-reopen-decision-command-v1.schema.json`.

Rutas:

| Método | Ruta | Permiso | Resultado |
|---|---|---|---|
| GET | `/orders/accounts` | `orders.read` | filtros/cursor y detalle snapshot |
| POST | `/orders/{id}/reopen-requests` | `orders.reopen.request` | crea/replay sin mutar pedido |
| GET | `/orders/reopen-requests` | `orders.reopen.authorize` | lista paginada y acotada |
| POST | `/orders/reopen-requests/{id}/approve` | `orders.reopen.authorize` | `REQUESTED -> APPROVED` |
| POST | `/orders/reopen-requests/{id}/reject` | `orders.reopen.authorize` | `REQUESTED -> REJECTED` |
| POST | `/orders/reopen-requests/{id}/apply` | `orders.reopen.authorize` | 409 `order_reopen_policy_pending` |

Mantener `POST /orders/{id}/amendments` sin cambios: pedidos protegidos siguen devolviendo los
errores existentes y ninguna aprobación los vuelve editables.

## 6. UI POS

Reutilizar `features/history/History.tsx`; no crear una segunda pantalla de historial.

- Sustituir filtrado local limitado por consulta server-side de `/orders/accounts`.
- Filtros accesibles: día de sucursal, turno, caja, servicio y búsqueda folio/cliente.
- Estados visibles: loading, error, vacío, datos, paginación y detalle.
- Detalle indica si usa snapshot capturado/legacy/incompleto y nunca consulta catálogo vivo.
- Botón `Solicitar reapertura` sólo cuando sesión declara permiso y backend devuelve elegible.
- Modal exige motivo y referencias de evidencia; conserva la key ante fallo incierto y genera una
  nueva sólo después de éxito o cambio de payload.
- Dueño ve solicitudes dentro de alcance y puede aprobar/rechazar con motivo.
- No mostrar botón aplicar ni redirigir al editor después de aprobar.
- Respuesta 403/409 se muestra y no conserva optimismo falso.
- Español, teclado/foco y contención real a 1440x900 y 1000x800.

La visibilidad de UI no reemplaza la autorización backend.

## 7. Auditoría, logs y métricas

Auditoría requerida:

- `order.reopen.requested`;
- `order.reopen.approved`;
- `order.reopen.rejected`;
- `order.reopen.apply_denied` cuando sea seguro conservar una denegación.

Payload mínimo: IDs internos de pedido/solicitud, estado anterior/nuevo, versión snapshot y actor.
No incluir motivo libre completo, evidencia, cliente, claves, tokens ni payloads de pago.

Logs estructurados: resultado `success|replay|conflict|denied|error`, comando, actor, sucursal y
request ID; sin PII ni `Idempotency-Key`.

Métricas:

- `order_reopen_request_total{result}`;
- `order_reopen_decision_total{decision,result}`;
- `order_reopen_apply_denied_total{reason}`;
- latencia de lista/decisión sin labels de alta cardinalidad.

## 8. RED obligatorio

Antes de implementación, agregar pruebas que fallen por ausencia del comportamiento:

1. filtros/alcance/cursor de cuentas y cursor ligado a filtros;
2. detalle usa snapshot histórico y no catálogo actual;
3. Cajero no solicita; Cajero jefe sí dentro de sucursal; cross-branch falla;
4. creación no cambia hash completo de pedido, líneas, pagos, tareas, inventario, cierres y snapshots;
5. replay idéntico devuelve mismo ID; key/payload distinto falla;
6. dos solicitudes activas concurrentes producen una sola fila;
7. sólo Dueño aprueba/rechaza; versión cambiada falla sin decidir;
8. estados terminales no cambian;
9. `/apply` falla `order_reopen_policy_pending` y la huella de historia queda idéntica;
10. API real valida los cinco JSON Schemas;
11. SQLite y PostgreSQL aislado cubren unicidad/lock/roundtrip;
12. UI cubre permisos, key persistente, error y ausencia de aplicación;
13. logs/auditoría no contienen motivo, evidencia, cliente ni key.

## 9. GREEN y comandos mínimos

Ejecutar desde la raíz, usando `python3` si `python` no existe:

```bash
python3 -m pytest apps/api/tests/test_order_accounts.py \
  apps/api/tests/test_order_reopen_workflow.py \
  apps/api/tests/test_order_reopen_migration.py
PCO005_TEST_POSTGRES_URL=postgresql+psycopg://... \
  python3 -m pytest apps/api/tests/test_order_reopen_postgres.py
python3 -m pytest tests/contract tests/integration
node --test tests/frontend/test_pos_order_reopen.mjs
pnpm --filter "@restaurantos/pos-web" typecheck
pnpm --filter "@restaurantos/pos-web" build
python3 -m pytest tests/architecture/test_traceability.py
python3 -m pytest
git diff --check
```

`PCO005_TEST_POSTGRES_URL` debe apuntar a una base local/aislada `pco005_*`. Nunca usar
`DATABASE_URL`, `kiwi-postgres` ni producción para estos gates.

## 10. Documentación y matriz

Sol materializó antes del código los refinamientos aprobados en:

1. `docs/01-PRD.md` — límite PCO-005A y PCO-005B;
2. `docs/02-SDD.md` — tabla, comandos, contratos, invariantes y rollback;
3. `docs/03-BDD-pos-cash-ops.md` — `BDD-SC-312..316`;
4. `docs/04-TDD-pos-cash-ops.md` — `TDD-TC-096..100`;
5. `docs/05-matriz-trazabilidad.md` — FR-217 sigue `Disenado` hasta completar PCO-005B; registrar
   evidencia parcial sin elevarla a `Implementado`;
6. `docs/10-operacion-easypanel.md` — gate de SHA exacto; Terra agrega respaldo, `0039`, health y
   canary sin aplicación;
7. `docs/implementation-reports/PCO-005A.md` — Terra agrega evidencia exacta y gates omitidos.

Terra debe preservar estos IDs y límites. Sólo puede ampliar redacción técnica para reflejar la
implementación real; no puede cambiar PCO-005A a aplicación mutante ni elevar FR-217 a
`Implementado`.

Escenarios nuevos:

- `BDD-SC-312`: filtros/cursor/alcance y snapshot histórico;
- `BDD-SC-313`: solicitud idempotente no muta historia;
- `BDD-SC-314`: solicitud concurrente única y conflicto de key;
- `BDD-SC-315`: Dueño aprueba/rechaza con versión estable;
- `BDD-SC-316`: aplicación sigue fail-closed sin mutación.

Casos nuevos:

- `TDD-TC-096`: consulta y cursor ligados a filtros;
- `TDD-TC-097`: inmutabilidad completa de solicitud;
- `TDD-TC-098`: idempotencia/concurrencia;
- `TDD-TC-099`: autorización/transiciones/versión;
- `TDD-TC-100`: aplicación denegada y redacción.

## 11. Entrega de Terra

Terra entrega:

- lista exacta de archivos modificados;
- evidencia RED previa y GREEN posterior;
- revisión/migración y resultado SQLite/PostgreSQL por separado;
- hashes o conteos de huella de no mutación;
- resultados de contrato, backend, frontend, typecheck, build y trazabilidad;
- `git status --short` y `git diff --check`;
- riesgos, gates omitidos y razón;
- confirmación de que no hizo push, merge, deploy ni tocó producción o archivos no rastreados.

Sol rechazará la entrega si una aprobación habilita edición, si una prueba sustituye PostgreSQL por
SQLite, si la UI decide autoridad, si falta evidencia de inmutabilidad o si se declara PCO-005
completo cuando PCO-005B sigue pendiente.
