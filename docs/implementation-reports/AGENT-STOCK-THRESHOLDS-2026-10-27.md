# Umbrales de inventario para Agent Tools — evidencia local

Cambio R3 acotado a la lectura de stock y su contrato. Autoridad: PRD-FR-271, SDD §59.4,
BDD-SC-650, TDD-TC-358/360; contrato de consumo en `docs/14-grokbot-agent-tools-api.md`.
Se activaron esos documentos, matriz y OpenAPI. No se modifica UI, esquema, permisos, fórmulas
de inventario, configuración productiva ni servicios de escritura.
Se incluye un refactor R1 en `inventory_ai.py`: renombrar la variable local de un bucle para
evitar reutilizar `pres` con tipos incompatibles y cerrar el gate mypy normal. Conserva query,
orden y cálculo; no activa cambios adicionales de PRD/SDD/BDD/TDD ni una fase RED artificial.

## Verificación

- RED previo al runtime: tres fallos por campos ausentes en respuesta/OpenAPI, un caso de permisos
  aprobado y dos casos PostgreSQL inicialmente omitidos por falta de URL. Otro RED confirmó que
  un almacén inactivo antes respondía 200 en vez del 503 definido.
- `python -m pytest apps/api/tests/test_agent_stock_thresholds.py apps/api/tests/test_agent_tools.py
  apps/api/tests/test_agent_tools_contract.py tests/architecture/test_traceability.py -q`:
  **29 aprobadas**, dos PostgreSQL inicialmente omitidas.
- PostgreSQL 16.15 local, base `grokbot_stock_test`, esquema aislado por caso:
  `GROKBOT_TEST_POSTGRES_URL` configurada para el proceso y
  `python -m pytest apps/api/tests/test_agent_stock_thresholds.py -q -k postgresql`:
  **2 aprobadas**. Los dos casos inicialmente omitidos tienen evidencia real: total **31 aprobadas**.
- `python -m pytest apps/api/tests/test_inventory_ai.py
  apps/api/tests/test_inventory_ai_remediation.py -q`: **24 aprobadas** después del refactor de
  nombre local. Total de casos ejecutados aprobados en el paquete: **55**.
- `python -m ruff check apps/api/restaurant_os/agent_tools.py apps/api/restaurant_os/inventory_ai.py
  apps/api/tests/test_agent_stock_thresholds.py`: aprobado.
- `python -m mypy apps/api/restaurant_os/agent_tools.py apps/api/restaurant_os/inventory_ai.py`:
  **aprobado, dos módulos**, siguiendo dependencias normalmente. La primera ejecución había
  detectado una asignación de `dict[str, Any] | None` a una variable inferida `RowMapping` en
  `inventory_ai.py:284`; quedó resuelta con el refactor, sin flags de silenciamiento ni exclusiones.
- `git diff --check`: aprobado. Las ejecuciones Python usan `.venv/Scripts/python.exe`.
- Advertencia preexistente de deprecación Starlette/httpx; no se agregaron exclusiones ni
  silenciamientos al código o a la configuración de pruebas/tipos.

## Revisión R3 independiente

Auditoría Sol con contexto fresco, sin hallazgos accionables. El seguimiento focal del mismo ciclo
aprobó también el refactor R1 de `inventory_ai.py` y confirmó que no cambia comportamiento ni las
conclusiones originales. Evidencia revisada y posteriormente complementada por ejecución PostgreSQL:

| Afirmación | Evidencia e intento de refutación | Resultado y riesgo residual |
|---|---|---|
| Sólo se expone el alcance autorizado | Guardas antes del SELECT; señuelos de organización, sucursal y almacén; solicitudes sin capacidad y fuera de allowlist | Pruebas verdes; mantiene la reautorización existente |
| Umbrales exactos, ausencia distinguible de cero y sin duplicados | NUMERIC→str sin float; LEFT JOIN; unicidad de almacén, estado y umbral; cero, seis decimales, sin estado/umbral y páginas de una fila | SQLite y PostgreSQL verdes; no añade snapshot entre páginas ante ediciones concurrentes |
| La lectura no altera historia ni configuración | Camino exclusivamente SELECT; snapshots de tablas de umbrales, estados, movimientos e insumos antes/después | Sin cambios; no necesita compensaciones ni migraciones |
| Contrato aditivo visible en Swagger | Prueba de campos anulables en OpenAPI compartible y runtime; modelo de respuesta explícito | Verde local; publicación pendiente. Clientes que rechacen propiedades adicionales deben aceptar la ampliación |

## Operación y publicación

Preguntas operativas cubiertas por las señales existentes de solicitudes de Agent Tools:

1. ¿La lectura se rechaza por autorización o por almacén no disponible? Estado HTTP, código estable
   (`agent_capability_denied`, `agent_branch_denied`, `dependency_unavailable`) y correlación del
   evento `agent.request.accepted|denied` permiten distinguirlo sin registrar tokens o cantidades.
2. ¿La lectura conserva latencia aceptable? La duración existente del endpoint permite comparar
   antes/después en el canary; consulta paginada y una resolución de almacén, sin consulta por insumo.

La URL compartida por el usuario, `https://asistto.bots2.me/docs`, sirve el OpenAPI de Asistto, que
no contiene esta ruta. Se confirmó por lectura pública que `https://kiwipos.mimenu.onl/openapi.json`
sí contiene la ruta de Kiwi, todavía con el esquema genérico anterior.

No se ejecutó suite completa local: cambio acotado, regresión focal ejecutada; CI configura suite
completa y PostgreSQL, pero este paquete aún no tiene ejecución CI, commit, push ni despliegue.
Frontend, gateway y migraciones no se activan. El usuario autorizó explícitamente publicación y
despliegue en este chat, conforme a GOV-REL-001. Tras CI verde, desplegar y hacer canary autenticado
con `inventory`: comparar un insumo con
umbral y otro sin él contra Admin, validar unidad, ceros/null y rechazo de sucursal ajena. No escribir
datos productivos para el canary. Ante regresión, revertir el código/contrato de esta ampliación;
no hay datos que migrar ni movimientos que compensar.
