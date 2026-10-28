# Umbrales de inventario para Agent Tools — evidencia local

Cambio R3 acotado a la lectura de stock y su contrato. Autoridad: PRD-FR-271, SDD §59.4,
BDD-SC-650, TDD-TC-358/360; contrato de consumo en `docs/14-grokbot-agent-tools-api.md`.
Se activaron esos documentos, matriz y OpenAPI. No se modifica esquema, permisos, fórmulas de inventario, configuración productiva ni servicios
de escritura. El cierre de CI incluye la regresión de contexto del Copiloto Ejecutivo descrita abajo.
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

No se ejecutó suite completa Python local: cambio acotado, regresión focal ejecutada; CI configura
suite completa y PostgreSQL. El paquete se publicó en PR #91 como `9f3ce3c`. CI run `40624863714`
falló antes de ejecutar Python por diez errores de tipos heredados en otros cinco módulos, y
también por firmas de fixtures desactualizadas y dos expectativas antiguas de marca/icono de Admin.
Docker y revisión de dependencias sí aprobaron; ese run no acredita la suite funcional.

El seguimiento corrige esos gates sin modificar reglas ni UI: anota colecciones y filas SQL;
actualiza expectativas exactas de Mimenu Admin/Utensils conforme al layout vigente; renombra una
variable de credencial sintética; refresca únicamente cinco SHA de entradas existentes en la
allowlist, tras revisar sus fixtures. El lint completo detectó además formato heredado en
`executive_ai.py` y su prueba: se corrigió verificando igualdad del AST antes/después. No se agregan
silenciamientos, exclusiones ni nuevas entradas a la allowlist. Mypy completo aprueba los 150
módulos y Ruff aprueba `apps/api tests`. Auditoría Sol de seguimiento sin hallazgos; las regresiones
focales y semánticas de esta reparación se ejecutan antes del cierre. La integración requiere un
nuevo CI verde del PR, no el run fallido anterior.

CI run `40625872183` aprobó políticas, Docker y dependencias. Detectó una diferencia de tipado
SQLAlchemy en CI (desempaquetado de Row), corregida accediendo a sus columnas nombradas, y
expectativas frontend heredadas: métricas movidas a ExecutiveCopilot, componentes de producto
habilitados y botones de menú blancos por el cambio de marca ya integrado en main. Las pruebas
ahora verifican esa arquitectura vigente; conservan autoridad Python, contraste y foco accesible.

La prueba de alcance reveló además una regresión real: el nuevo Copiloto no cancelaba consultas
al cambiar de sucursal. Se añadió cancelación de la consulta sustituida y al desmontar, guardas
para resultados/errores tardíos y una key por sucursal que limpia el estado. BDD-SC-638,
TDD-TC-352 y su matriz documentan la regresión; PRD/SDD mantienen el contrato existente.
El RED se reconstruyó contra el componente de `6d31334`: la prueba ejecutable falla por ausencia
de AbortSignal; con el cambio pasa incluso cuando el transporte ignora la cancelación. Pasan los
cinco scripts frontend afectados y typecheck Admin. La secuencia semántica completa se recorrió
localmente durante el diagnóstico; el gate canónico final queda a cargo de CI. No se altera layout
ni estilo, por lo que no se activa QA visual; CI construye Admin antes de la publicación.

| Afirmación adicional | Evidencia e intento de refutación | Resultado y riesgo residual |
|---|---|---|
| El copiloto no publica resultados de una consulta sustituida ni del contexto anterior | Componente ejecutado con dos respuestas fuera de orden, desmontaje con petición pendiente y rechazo tardío; contrato de montaje por sucursal | Verde local; cancelar el cliente no garantiza cancelar trabajo ya iniciado en el servidor, que sigue sujeto a su autorización |

Seguimiento Sol independiente de estas correcciones: sin hallazgos accionables. La prueba de
hooks simulados no sustituye una navegación real en navegador. La regresión Python de transición
y la integridad de trazabilidad suman 12 pruebas aprobadas tras acceder a las columnas nombradas.

CI run `40627277696` aprobó los gates de tipos/lint, semántica frontend, políticas y Docker;
el navegador falló por esperar el título anterior del dashboard. Se actualizaron sólo el título
y color de marca en `test_admin_retro.mjs`, y se restauró `aria-hidden` en el icono decorativo
Utensils (el test detectó su ausencia). Se refrescó la firma de ese fixture sintético existente.
Build Admin y siete scripts browser del bloque "Verify Admin retro in browser" aprobados localmente
contra preview compilado: Admin retro (390/768/1440 y login claro/oscuro), recipe product flow,
compound product admin, shared modifier workspace, admin session recovery, corporate purchase
remediation y supplier workspace. Runtime local Playwright 1.63 con Chromium headless 1247;
CI usa su Chromium 1243. Un intento de descarga local de 1243 agotó timeout, sin alterar el gate.

Gateway y migraciones no se activan. El usuario autorizó explícitamente publicación y
despliegue en este chat, conforme a GOV-REL-001, y después indicó que él hará el redeploy.
La navegación automatizada se detuvo sin ejecutar el despliegue. Tras CI verde, integrar y entregar
el SHA al usuario para redeploy y canary autenticado
con `inventory`: comparar un insumo con
umbral y otro sin él contra Admin, validar unidad, ceros/null y rechazo de sucursal ajena. No escribir
datos productivos para el canary. Ante regresión, revertir el código/contrato de esta ampliación;
no hay datos que migrar ni movimientos que compensar.
