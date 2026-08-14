# PCO-005A — evidencia integrada parcial

Este incremento implementa consulta de cuentas y solicitudes `REQUESTED -> APPROVED|REJECTED`
sin modificar pedidos, pagos, inventario, producción, caja, cierres ni snapshots. `POST /apply`
continúa cerrado con `order_reopen_policy_pending`; PCO-005B sigue pendiente y `PRD-FR-217`
permanece **Disenado** en la matriz.

## Trazabilidad

- Requisito: `PRD-FR-217`.
- Escenarios: `BDD-SC-312..316`.
- Pruebas: `TDD-TS-079`, `TDD-TC-096..100`, RED #12.

## Evidencia ejecutada

- `/Users/renatavictoriagonzalez/Documents/miguelgespino/Kiwi/.venv/bin/python -m pytest apps/api/tests/test_order_reopen_workflow.py apps/api/tests/test_order_reopen_migration.py apps/api/tests/test_order_reopen_contracts.py tests/architecture/test_traceability.py -q`: `21 passed`.
- `python3 -m pytest tests/architecture/test_traceability.py -q`: `8 passed`.
- `node --test tests/frontend/test_pos_order_reopen.mjs`: `1 passed`.
- Los seis casos antes rojos por el head Alembic (tres en `test_migrations.py` y tres en
  `test_alembic_version_capacity.py`) se ejecutaron contra `0039_order_reopen_requests`:
  `6 passed`.
- `python3 -m ruff check --no-cache apps/api/restaurant_os/operations.py apps/api/tests/test_order_reopen_contracts.py`: correcto.
- `git diff --check`: correcto.
- SQLite aislado: la prueba cubre `0038 -> 0039 -> 0038 -> 0039`.

## Entrega integrada

- `History.tsx` consulta exclusivamente `/orders/accounts` con filtros de día convertidos con
  la zona horaria de la sesión, turno, caja, servicio, búsqueda y cursor de continuación.
  La búsqueda espera 250 ms, sólo envía `q` desde dos caracteres y descarta respuestas de una
  consulta anterior. El cambio de filtro reinicia la consulta; el DTO se presenta como
  `customer_label` y `service_type`.
- `GET /orders/{id}` conserva `owner_name` y `order_type` para consumidores existentes y añade
  los aliases canónicos `customer_label` y `service_type`; el test dirigido cubre ambos pares.
- La solicitud aparece únicamente con `orders.reopen.request`; conserva en memoria su clave de
  idempotencia mientras el payload no cambie, exige motivo de 10 a 500 caracteres y 1 a 10
  referencias de evidencia, desaparece cuando ya hay solicitud activa y no actualiza la UI de
  forma optimista ante 403/409.
- La bandeja y la decisión aparecen únicamente con `orders.reopen.authorize`, incluyen motivo y
  referencias de evidencia, usan claves estables por solicitud/decisión/payload y no contiene
  ninguna acción `apply` ni redirección al editor.
- El DTO contractual de solicitud incluye `reason` y `evidence_refs` para que Dueño pueda
  revisar la justificación antes de decidir. El backend conserva su política de logs/auditoría
  redactados: no se agregó esa información a eventos ni logs.

## Gates omitidos o no aprobatorios

- PostgreSQL aislado aprobado contra `pco005_test` en `database-prueba`:
  `apps/api/tests/test_order_reopen_postgres.py -q` → `3 passed in 61.21s`. El gate usa únicamente
  `PCO005_TEST_POSTGRES_URL`, valida PostgreSQL y base `pco005_*`, migra `0038 -> 0039`, y cubre
  concurrencia/índice activo, conflicto de versión e inmutabilidad de orden/pago. Una instancia
  remota aislada requiere además el opt-in explícito `PCO005_TEST_POSTGRES_ALLOW_REMOTE=1`; sin él
  hace skip antes de conectar. Rechaza objetivos protegidos `kiwi-postgres` y `restaurantos`, y sus
  pruebas de URL confirman que no lee `DATABASE_URL`.
- El primer gate real quedó RED: `2 failed, 1 passed in 100.55s`, por permisos globales ya sembrados
  por migración y falta del turno del fixture PostgreSQL; no fue un fallo de dominio. Se corrigió el
  fixture para truncar `organizations` y `permissions` con dependencias `CASCADE`, y crear
  explícitamente `CAJA-01`, tras lo cual el gate quedó verde.
- Tras el gate, el puerto temporal se restauró a `0` y la credencial efímera se eliminó. No se usó
  `DATABASE_URL`, `kiwi-postgres` ni producción.
- El gate de contratos se ejecuta con el virtualenv compartido, que contiene `jsonschema 4.25.1` y
  `referencing`; no se instaló ninguna dependencia.
- `python3 -m ruff check --no-cache` sobre los siete archivos PCO-005A: correcto.
- Baseline posterior a `0039`: la suite completa reportada por la auditoría fue `309 passed,
  6 failed, 10 skipped`; los seis fallos eran expectativas heredadas de head `0038` y se
  actualizaron a `0039_order_reopen_requests` sin cambiar comportamiento de migraciones.
- Gates dirigidos posteriores: `21 passed` (workflow, migración, contratos, trazabilidad y
  expectativas Alembic actualizadas).
- La suite Python completa se inició con el virtualenv, pero este entorno no devolvió una terminación
  verificable; ese intento histórico no se declara aprobatorio por sí mismo.
- Se intentó el store indicado con `pnpm install --offline --frozen-lockfile --store-dir .../v10`:
  falló sin red porque falta `@tanstack/react-query@5.101.2`. El `pnpm --filter` posterior no pudo
  iniciar typecheck/build y reportó intentos de metadata/tarballs que fallaron por `ENOTFOUND`; no
  descargó ni instaló dependencias. Ambos gates siguen no aprobados.
- El gate se reintentó sin pnpm con cuatro enlaces temporales de workspace (raíz, POS, UI y cliente
  API) y Node `v24.19.0`. Desde `apps/pos-web`, `./node_modules/.bin/tsc --noEmit` pasó y
  `./node_modules/.bin/vite build --configLoader runner` pasó (`1584 modules transformed`,
  `431.67 kB` JS gzip `129.10 kB`). Las tres pruebas frontend relacionadas dieron `3 passed`.
  Los cuatro enlaces se verificaron como enlaces y fueron retirados; no quedó `node_modules` nuevo
  en los cuatro puntos del worktree.
- QA visual local detectó contraste insuficiente en la cola navy de reaperturas a 1440×900. Se
  corrigió sólo su CSS: superficie `#102a43`, texto/encabezados/strong/span `#f8fafc`, texto y
  labels `#dbeafe`, campos con fondo blanco y texto `#0f172a`, además de `overflow: visible` para
  evitar recortes. La prueba semántica exige esos contratos; con Node `v24.19.0`, typecheck y build
  volvieron a pasar (`42.10 kB` CSS gzip `8.14 kB`) y el test dirigido dio `1 passed`.
- QA visual local aprobada a 1440×900 y 1000×800 con mock determinista: sin overflow horizontal;
  filtros, lista, detalle y cola contenidos; contraste de la cola corregido; consola con 0 warnings
  y 0 errors. Este mock no es producción ni una prueba E2E contra la API real.
- Suite Python final ejecutada por Sol:
  `/Users/renatavictoriagonzalez/Documents/miguelgespino/Kiwi/.venv/bin/python -m pytest -p no:cacheprovider`
  → `320 passed, 12 skipped in 334.25s (0:05:34)`. Los dos skips adicionales corresponden a los
  casos de conexión PostgreSQL opt-in dentro de la suite normal; el gate PostgreSQL aislado
  separado quedó verde con `3 passed`.

No se usó `DATABASE_URL`, `kiwi-postgres`, producción, commit, push, merge ni despliegue.
