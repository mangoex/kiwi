# PCO-005B — evidencia local para auditoría Sol

Fecha: 2026-08-14. Riesgo: R3. No hubo commit, push, despliegue, migración productiva ni acceso a
`DATABASE_URL`.

## Cambio

- `0040_order_corrections` agrega correcciones, líneas y ajustes financieros/productivos aditivos.
- `/api/v1/orders/reopen-requests/{id}/apply` exige Dueño, plan estricto e `Idempotency-Key`; crea
  corrección, ajuste y movimiento cash en una transacción y sólo entonces marca `APPLIED`.
- El detalle conserva pedido/pago original y proyecta las correcciones por separado.
- POS muestra la acción de Dueño para una solicitud aprobada, con confirmación explícita e
  idempotencia; no recalcula totales.

## Evidencia

- RED histórico: el gate inicial de apply falló por la firma legacy sin plan completo. Los RED
  posteriores de auditoría se incorporaron como regresiones; el primer pase de TDD-TC-102/105
  detectó un fixture JSON no serializable y una aserción TypeScript demasiado amplia, ambos
  corregidos sin relajar el contrato.
- GREEN backend focal final: `python3 -m pytest -p no:cacheprovider
  apps/api/tests/test_order_corrections.py -q` → `54 passed`; incluye centavos exactos,
  TDD-TC-107 SQLite file-backed, conflictos de idempotencia/versión y rollback productivo.
- Regresión backend dirigida: `test_order_corrections`, `test_order_reopen_workflow`,
  `test_cash_ledger`, `test_sales_monitor` y `test_cash_shift_operational_close` →
  `82 passed, 2 skipped`.
- Suite API completa: `242 passed, 21 skipped`; ninguna omisión se contabiliza como aprobada.
- Contratos PCO-005B/PCO-004: `7 passed, 1 skipped`. Migración PCO-005B: `5 passed`; SQLite
  `0039 → 0040 → 0039 → 0040` y guardas de downgrade verdes. La respuesta y el comando
  permanecen cerrados y redactados.
- Harness PostgreSQL: `2 passed, 5 skipped`; pasaron las guardas deterministas de seguridad y
  quedaron omitidas las carreras que requieren una base aislada real.
- Frontend semántico, TypeScript y build: verdes con las dependencias existentes del checkout.
- Lint focal: `python3 -m ruff check --no-cache restaurant_os/operations.py
  tests/test_order_corrections.py` verde. `git diff --check` verde.

## Gates omitidos y residual

- PostgreSQL aislado: `5 skipped` por ausencia de `PCO005B_TEST_POSTGRES_URL` con base aislada
  `pco005b_*`; no se consultó `DATABASE_URL`. SQLite prueba invariantes, no row locking PostgreSQL.
- `jsonschema` PCO-004: `1 skipped` por dependencia local ausente; los contratos PCO-005B tienen
  pruebas estructurales deterministas y no se presenta ese skip como validación JSON Schema plena.
- QA visual: se inició preview local y navegador, pero la política de seguridad del navegador
  bloqueó la URL local antes de inspeccionar estados PCO-005B; el gate queda omitido. El servidor
  se detuvo y se retiró el enlace temporal de dependencias.
- Corte final: diferido a PCO-006. No existe `UserCashCut` ni asociación de operación finalizada;
  el cierre legacy continúa fail-closed con `legacy_cash_cut_forbidden`. No se inventó esa entidad.
- No hubo commit, push, despliegue, migración productiva ni uso de datos productivos.

## Consolidación local auditada

- Los 19 archivos de runtime, pruebas, migración, contratos y este reporte se sincronizaron desde
  el worktree de Terra al checkout principal y se verificaron byte por byte antes de probar.
- Se preservaron las versiones más recientes del SDD, BDD, TDD, decisión y handoff del checkout
  principal: documentan `register_id` para cash y el editor POS real, en concordancia con el código.
- Gates repetidos en el checkout principal: correcciones `54 passed`; migración `5 passed`;
  contratos `7 passed, 1 skipped`; trazabilidad `8 passed`; harness PostgreSQL
  `2 passed, 5 skipped`; prueba frontend, TypeScript, build Vite (1584 módulos), Ruff y
  `git diff --check` verdes.
- `PCO005B_TEST_POSTGRES_URL` no está configurada y el equipo local no ofrece `docker` ni `psql`;
  por ello no se intentó fabricar una base ni reutilizar `DATABASE_URL`.
- El job Python de GitHub Actions ahora provisiona PostgreSQL 16 efímero con base `pco005b_ci`,
  healthcheck y exclusivamente `PCO005B_TEST_POSTGRES_URL`. El YAML fue parseado y auditado
  localmente; las cinco carreras permanecen pendientes hasta que el workflow remoto se ejecute.
- La consolidación permanece sin commit, merge, push, despliegue ni migración productiva.
