# PCO-005B — handoff Terra para corrección compensatoria

**Estado de autoridad:** `SDD-ADR-027` aprobada por el Dueño de producto el 2026-08-14.<br>
**Riesgo:** R3.<br>
**Objetivo:** implementar y probar exclusivamente PCO-005B; Sol audita antes de cualquier commit,
merge, push, despliegue o migración productiva.

## 1. Fuentes obligatorias

Leer antes de editar:

1. `README.md`, `AGENTS.md` y `.agents/skills/restaurantos_dev/SKILL.md`;
2. `docs/01-PRD.md`: `PRD-FR-217`, `PRD-NFR-025`;
3. `docs/02-SDD.md`: secciones 38.2.5, 38.2.6 y 38.3;
4. `docs/03-BDD-pos-cash-ops.md`: `BDD-SC-312..326`;
5. `docs/04-TDD-pos-cash-ops.md`: `TDD-TS-079`, `TDD-TC-096..112`;
6. `docs/05-matriz-trazabilidad.md`, `docs/08-adrs-propuestas.md` ADR-027;
7. `docs/implementation-plans/PCO-005B-SOL-DECISION-SPEC.md`.

Si código y especificación se contradicen, conservar `/apply` fail-closed, detener esa parte y
reportar la contradicción. No inventar política financiera/productiva.

## 2. Alcance permitido

- migración Alembic aditiva `0040_order_corrections` desde `0039`;
- modelos/tablas de corrección, líneas y ajustes de pago/producción;
- servicio Python de cálculo/aplicación transaccional;
- contratos JSON Schema y ruta `/api/v1/orders/reopen-requests/{id}/apply`;
- proyección de detalle/cuentas para mostrar original y corrección por separado;
- integración focal con ledger cash, inventario, producción y monitor/corte sin reescribir historia;
- UI POS exclusiva de Dueño para plan y aplicación;
- pruebas TC-101..112 y actualización de reporte de implementación.

## 3. Exclusiones duras

- PCO-006+, corte nuevo, offline/outbox, proveedores de pago, CFDI/devolución fiscal, impresión o
  exportación;
- editar/eliminar pagos, snapshots, movimientos, cierres, cortes o auditoría históricos;
- convertir una corrección en edición normal de `orders`/`order_lines`;
- usar `DATABASE_URL`, base productiva, Easypanel, datos reales o migración productiva;
- commit, merge, push o PR;
- refactor global, formateo masivo o cambios ajenos.

## 4. Diseño mínimo obligatorio

### 4.1 Migración y datos

Crear revisión lineal `0040_order_corrections` con tablas equivalentes a:

- `order_corrections`: `id`, org/branch/order/request, folio único, captured/resulting version,
  before/after JSON, currency, corrected total, settlement delta, actor, applied UTC;
- `order_correction_lines`: correction, source line nullable, product/family/price/quantity/modifiers
  snapshots, line total, consumption snapshot/link, classification;
- `order_payment_adjustments`: correction, original payment, `CHARGE|REFUND`, positive amount,
  method, current cash shift nullable, status, evidence refs, cash movement nullable, UTC;
- `order_production_adjustments`: correction, source line/task nullable, correction line nullable,
  `RELEASE|WASTE|RECOVERY|ADDITION`, quantity, inventory movement/task links, UTC.

Agregar FKs, checks de importe/cantidad/moneda/estado, índices org-branch-time y unicidad de una
corrección por solicitud. No guardar valores derivados del navegador. Downgrade vacío funciona;
downgrade con historia lanza guard explícito antes de `drop_table`.

### 4.2 Servicio Python

Extraer un módulo cohesivo si `operations.py` crecería de forma no localizada. El servicio:

1. autentica y autoriza Dueño antes de consultar replay;
2. valida body estricto y hash canónico completo;
3. bloquea solicitud/pedido y, para cash, turno actual;
4. exige solicitud `APPROVED`, versión igual y un pago `CONFIRMED` único de la misma moneda;
5. reconstruye parte histórica sólo desde snapshots;
6. valida adiciones contra catálogo/receta vigente y captura snapshot nuevo;
7. calcula total/delta en Python; centavos `int`, cantidades/conversiones `Decimal`;
8. aplica la matriz productiva exacta ADR-027;
9. crea ajuste financiero y movimiento cash exactamente una vez cuando corresponde;
10. inserta corrección/líneas/ajustes/eventos/auditoría/command y marca `APPLIED` en una transacción;
11. revierte todo ante cualquier fallo;
12. devuelve DTO redactado y replay estable sólo después de reautorizar.

La venta original conserva hashes de pedido, pago, snapshot, turno, cierre, corte y asociaciones.
El detalle proyecta `original` y `correction`; no reemplaza silenciosamente campos históricos.

### 4.3 Producción e inventario

- `PENDING` reducido: transición a cancelado y `RESERVATION_RELEASE` sólo por diferencia;
- `IN_PROGRESS` afectado: `production_in_progress`, cero escritura;
- `COMPLETED` reducido + `waste`: conserva consumo, registra WASTE/evidencia enlazada sin devolver
  existencia;
- `COMPLETED` reducido + `recovery`: `RECOVERY` positivo exacto;
- adición: snapshot vigente, `SALE_RESERVATION` negativa y tarea `PENDING` nueva;
- snapshot faltante/unidad incompatible: `historical_snapshot_missing`, cero escritura.

### 4.4 Ajuste financiero y reportes

- delta positivo: `CHARGE`; cash crea `DEPOSIT`, no cash exige evidencia manual;
- delta negativo: `REFUND`; cash crea `WITHDRAWAL`, no cash exige evidencia manual;
- delta cero: sin fila financiera;
- movimiento cash usa importe positivo y `register_id`; backend deriva el único turno `OPEN` de esa
  sucursal/caja y guarda source/correlation de corrección;
- efectivo esperado incluye el movimiento una vez;
- monitor/drill-down conserva venta original y muestra corrección en periodo actual;
- operación ya asociada a corte finalizado permanece asociada sólo a ese corte.

## 5. API y UI

El endpoint reutiliza el path existente y reemplaza únicamente el cuerpo fail-closed después de
validar ADR-027. El body acepta `register_id` nullable, obligatorio para delta cash; backend deriva
el turno por sucursal+caja. No acepta totales, actor, org, branch, currency, `cash_shift_id` ni
movement IDs. Agregar schemas versionados de comando/respuesta y errores.

En `History.tsx`, la acción sólo aparece con `orders.reopen.authorize` y status `APPROVED`, y abre el
editor POS existente en modo corrección. Ese editor permite cambiar cantidades, retirar/agregar
productos y elegir disposiciones, método, evidencia y caja cuando corresponda; reutiliza catálogo,
modificadores y carrito sin llamar al endpoint normal de enmienda. La UI obtiene el plan del backend
o muestra la respuesta calculada por backend; no implementa fórmulas.
Debe conservar la cola PCO-005A y sus estados, y agregar loading/validation/submitting/applied/
conflict/error, confirmación explícita, teclado/foco y español.

## 6. Secuencia RED → GREEN

1. Crear/ajustar tests focales que fallen por ausencia de PCO-005B: contrato, delta, RBAC,
   idempotencia y gate `/apply`.
2. Ejecutar RED y guardar salida exacta.
3. Migración/modelos mínimos; validar upgrade/downgrade vacío.
4. Servicio Python y API; lograr GREEN backend SQLite focal.
5. Integración inventario/producción/caja/reportes con fallos inyectados.
6. PostgreSQL aislado: migración, constraints, locks y tres carreras.
7. UI mínima, test semántico, TypeScript/build y QA visual de estados cambiados.
8. Suite focal final una sola vez y `git diff --check`.

## 7. Gates y comandos esperados

Usar el virtualenv/repositorio real; ajustar rutas sin sustituir gates:

```bash
python3 -m pytest tests/architecture/test_traceability.py
python3 -m pytest apps/api/tests/test_order_reopen_workflow.py apps/api/tests/test_order_corrections.py
python3 -m pytest apps/api/tests/test_order_reopen_postgres.py apps/api/tests/test_order_corrections_postgres.py
node --test tests/frontend/test_pos_order_reopen.mjs
pnpm --filter @restaurant-os/pos-web typecheck
pnpm --filter @restaurant-os/pos-web build
git diff --check
```

Si los paths reales difieren, descubrir con `rg --files` y reportar comandos exactos. PostgreSQL usa
exclusivamente `PCO005B_TEST_POSTGRES_URL`; si no está disponible, el gate queda **omitido**, nunca
verde. No ejecutar suite completa salvo que los tests focales no puedan acotar una regresión o CI sea
inconcluso.

## 8. Entrega para auditoría Sol

Sin commit ni push, reportar:

- archivos cambiados y por qué;
- mapa FR/NFR → BDD → TDD;
- salida RED y GREEN exacta, incluidos skips;
- revisión/migración y evidencia SQLite/PostgreSQL separada;
- decisiones de implementación y cualquier desviación;
- huellas que prueban inmutabilidad histórica;
- QA visual con dimensiones/estados, o gate omitido;
- `git status --short`, `git diff --stat` y `git diff --check`.

Sol inspeccionará el diff, ejecutará gates independientes y devolverá aceptación o hallazgos
accionables. Terra sólo iterará hallazgos materiales; no ampliará alcance.
