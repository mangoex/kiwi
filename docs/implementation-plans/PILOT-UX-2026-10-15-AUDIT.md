# Auditoría independiente R3 — PILOT-UX-2026-10-15

Base revisada: `0aec8ba`; candidato de trabajo `codex/pilot-pos-admin-stories`, 2026-10-15. Revisión de corrección, seguridad/alcance, compatibilidad SQL y operación. Se aplicaron AGENTS.md y restaurantos-development. No se editaron fuentes, especificaciones, Git ni producción desde esta auditoría; únicamente evidencia y probes sintéticos bajo este directorio.

## Resultado

Sin hallazgos bloqueantes pendientes en el diff revisado. Se detectaron y comunicaron dos defectos de PostgreSQL en la búsqueda del nuevo feed; ambos quedaron corregidos y fueron refutados con ejecución independiente en PostgreSQL local en este mismo ciclo.

1. `q` se usaba con sus mayúsculas contra `lower(campo).contains(q)`: SQLite LIKE ocultaba el fallo; PostgreSQL no encontraba el folio WEB escrito tal como se muestra ni nombres en mayúsculas. Corregido normalizando la consulta tras validar su longitud.
2. `substr(public_reference, -6)` devolvía los últimos seis caracteres en SQLite y la cadena entera en PostgreSQL: construía un folio SQL distinto al mostrado. Corregido con `substr(reference, length(reference)-5, 6)`.

Verificación literal anterior a la corrección en PostgreSQL local: `substr('0123456789abcdef',-6)` produjo `0123456789abcdef`; `lower('WEB-ABCDEF') like '%WEB-ABCDEF%'` produjo `False`. Semántica de funciones: [documentación oficial PostgreSQL](https://www.postgresql.org/docs/current/functions-string.html).

## Afirmaciones R3 y refutaciones

### Feed conjunto acotado, sin duplicación por origen

- Afirmación: orders e intents se filtran antes del UNION ALL, se ordenan y limitan conjuntamente por created_at/id/kind; hidratar no altera el orden de página.
- Evidencia: `operations.py:list_order_accounts`; regresión original de 28 intents más un POS; `test_audit_probes.py` y `probe_postgres.py`.
- Refutación: mismo timestamp e identificador deliberadamente compartidos por un order y un intent, página de tamaño uno, tanto SQLite como PostgreSQL; kind de cursor desconocido; cash register aplicado; intent con accepted_order_id presente.
- Resultado: ambos orígenes aparecen exactamente una vez en páginas sucesivas; cursor final nulo; kind inválido rechazado; register excluye las solicitudes sin caja; solicitud ya aceptada excluida.
- Riesgo residual: la lista mantiene paginación sobre datos vivos, sin promesa de snapshot entre consultas/páginas. Una aceptación concurrente puede cambiar la composición; refrescar es necesario. No se midió carga de volumen productivo. No se agregan escrituras ni compensaciones a este recorrido de lectura.

### Alcance y diagnóstico no conceden autoridad

- Afirmación: exponer el motivo de bloqueo y el selector deshabilitado no otorga permisos ni cambia selección canónica.
- Evidencia: can_select_branch conserva exactamente su condición previa; motivo es una proyección adicional; UI envía selección sólo por selectBranch y el comando canónico; session.ts conserva permisos, authorized IDs, credential fencing y bloqueadores de turno/concesión/comando incierto.
- Refutación: prueba de rollout deshabilitado y comando denegado; intento de listar sucursal B con cajero A; cursor malformado/kind inválido; revisión origen raw.branch_id -> authorize_branch_scope -> filtros de ambos orígenes.
- Resultado: perfil puede mostrar sucursales sin habilitar el comando; sucursal ajena denegada antes de consultar feed. No hay inferencia por nombre Dueño ni nuevos grants.
- Riesgo residual: habilitar rollout/configurar permisos efectivos continúa siendo operación separada; esta revisión no certifica la configuración de producción.

### Enlace de confirmación conserva el transporte operativo

- Afirmación: Ver pedidos usa order_id/branch_id y History abre el detalle con useCashierOrderRequest, manteniendo autoridad local/central configurada y sin fallback ante configuración local inválida.
- Evidencia: PointOfSale confirmation incorpora id en todos los caminos modificados; navigate respeta basename /pos; History compara linkedBranchId antes de requestOrder; hook compartido falla cerrado si configuración local no corresponde y utiliza operationalOrderRequest al estar configurado.
- Refutación: seguimiento estático de ID, branch y transporte; respuesta tardía invalidada por secuencia al cambiar enlace o cerrar detalle; root App remonta el árbol al cambiar usuario/sucursal/versión/contexto.
- Resultado: no se introduce consulta de otra sucursal ni fetch central de respaldo. La lectura detallada sigue autorizada por backend.
- Riesgo residual: no ejecuté navegador en esta auditoría; pruebas de navegador/autoridad y QA visual pertenecen a la verificación raíz. El enlace determina el transporte desde la configuración vigente al abrirlo, no contiene una instantánea durable de gateway/dispositivo; cambios manuales de configuración después de confirmar requieren recuperación explícita del entorno de origen.

## Presentación y borradores

Revisión focal de ProductsList: select controlado con label, búsqueda/grupo preservados, opción de selección fuera del filtro conservada, alta usa valor vacío y cancelación de confirm restablece el valor DOM; sólo después de aceptar se descarta edición/alta y cambia selección. Detalle pasa a una sola columna minmax(0,1fr); seis pestañas y handlers canónicos permanecen. AdminLayout limita ocultamiento al hub exacto /inventory y catálogo /inventory/items; pantallas operativas conservan contexto. La configuración V2 mantiene su selector explícito y bloqueo de alcance local. Sin hallazgo estático pendiente. No sustituye QA visual ni pruebas semánticas raíz.

## Evidencia ejecutada por auditor

- `.venv/Scripts/python.exe -m pytest apps/api/tests/test_pilot_order_feed.py apps/api/tests/test_branch_scope_selection.py -q`: 9 passed, 25.37s.
- `.venv/Scripts/python.exe -m pytest output/pilot-pos-admin/sol/test_audit_probes.py apps/api/tests/test_order_reopen_workflow.py -q`: 11 passed, 12.22s.
- `.venv/Scripts/python.exe output/pilot-pos-admin/sol/probe_postgres.py`: PASS búsqueda WEB-/web-, CLIENTE SOL/cliente sol y cursor de timestamp/id/origen empatados. Base propia `pilot_feed_test_sol_edb0bfe90b`, creada y eliminada por el probe. Sólo loopback `127.0.0.1:55444`, usuario local xmltest, sin entorno/secretos ni bases ajenas.
- `git diff --check`: limpio durante la revisión.
- Advertencia preexistente de Starlette TestClient/httpx; no se silenció.

Preguntas operativas cubiertas por señales existentes: ¿qué sucursal/autoridad usa la vista? Contexto visible local/central y branch. ¿Por qué no cambia? Motivo estable rollout/conexión/gateway/permiso. ¿Dónde quedó la venta? ID explícito y error de lectura autorizado, sin payloads nuevos ni secretos en logs.

Límites: esta auditoría ejecutó pruebas focales y SQL PostgreSQL aislado; no ejecutó typecheck/build, suites completas, CI, navegador, despliegue, migración ni canary. El coordinador debe incorporar sus gates y evidencia antes del cierre. Nuevos cambios de lógica de feed/alcance/transporte tras este punto requieren revisión focal dentro del mismo ciclo, no una segunda auditoría ceremonial.
## Extensión focal del mismo ciclo — bloqueadores mecánicos de publicación

Candidato aislado: `C:/Users/Miguel Gonzalez/.codex/worktrees/pilot-pos-admin-fixes/Kiwi`, HEAD `0fcd2de`, PR78; revisión del diff sin commit informado por el coordinador. El checkout primario no fue editado por el auditor. La auditoría continúa siendo la misma del paquete.

Resultado: sin hallazgos bloqueantes en formato/imports de `integrations/service.py`, `integrations/whatsapp.py`, `main.py` y `test_whatsapp_integration.py`, ni en `content: object`, retorno `AsyncIterator[None]` de lifespan o los dos parámetros `Annotated[Session, Depends(get_session)]`. Los cambios no modifican SQL, mensajes, guardas ni lógica de WhatsApp. Esta afirmación se apoya en evidencia independiente, no sólo en el log del implementador.

- Afirmación: el cambio es mecánico salvo equivalencia explícita de anotación DI. Evidencia: `sol/probe_mechanical.py` compara cada AST HEAD/árbol sin atributos de posición. Sólo elimina nodos import comprobando por separado los bindings exactos (únicas adiciones permitidas: Annotated y AsyncIterator), normaliza el retorno de lifespan, los dos parámetros nombrados de alias webhook y la única anotación content:object. No normaliza SQL, literales, mensajes, expresiones, ramas, nombres, llamadas, excepciones ni efectos. Refutación: cualquier diferencia restante produce assertion. Resultado: cuatro PASS. Riesgo residual: no certifica la conducta funcional previa del adaptador, que permanece bajo su autoridad y pruebas existentes; tampoco prueba por sí solo el sistema de DI.
- Afirmación: los alias GET/POST siguen inyectando `get_session` con cache y liberación de generador. Evidencia/refutación: `sol/probe_di.py` configura SQLite explícito, reemplaza la dependencia con generador/sentinel y los delegados con verificadores sync/async, inspecciona APIRoute y ejecuta ambos requests sin lifespan ni red/DB externa. Resultado: ambos dependency.call son get_session con use_cache=True; se abrió/cerró exactamente una vez por request y ambos delegados recibieron la misma instancia inyectada. No se invocaron mensajes externos ni migraciones. Riesgo residual: el probe verifica equivalencia del cableado; las regresiones funcionales WhatsApp quedan en las pruebas focales del coordinador.
- `ruff check` focal de los cuatro archivos ejecutado por el auditor: All checks passed. `git diff --check` del checkout aislado: limpio.

La actualización de `test_admin_session_recovery.mjs` conserva su comprobación de producto recuperado y ahora selecciona/valida la opción del control accesible; no reduce el chequeo de credencial inválida, reautenticación ni API real. La nueva allowlist de ese fixture sólo cambia su hash exacto. Tras el formato del fixture WhatsApp debe recalcularse también SU hash exacto, sin agregar rutas ni variar procedencia/detector. La regla SEC001 y sus condiciones de inscripción sintética ya revisadas siguen vigentes.

Ruff completo y mypy94 con el entorno frozen previo fueron informados verdes por el coordinador; no se presentan como ejecución independiente del auditor. La diferencia del venv primario (stubs ausentes/versiones SQLAlchemy) no se resolvió con silenciamientos ni alterando código corporate/systemdiagnostics según el diff revisado. Pruebas focales WhatsApp/feed/branch se encontraban en ejecución al recibir esta extensión; el cierre debe registrar su resultado real y el CI del candidato final. El alcance sigue siendo reparación mecánica de los bloqueadores de publicación, sin nuevas funciones ni habilitación productiva.
## Integración focal con main remoto — bd818afe56e906f143164fd8acb91138293b029b

Revisión de resolución de merge en el mismo checkout aislado y ciclo. `origin/main` verificado exactamente en `bd818afe56e906f143164fd8acb91138293b029b`. Sin hallazgos bloqueantes nuevos.

- Afirmación: la resolución conserva íntegra la actualización remota de WhatsApp. Refutación/evidencia: comparación binaria de blobs del index y origin/main, más contenido de trabajo normalizado sólo CRLF/LF, para `integrations/whatsapp.py` y `test_whatsapp_integration.py`. Resultado: ambos idénticos a remoto; ningún cambio de formato propio anterior permanece sobre esos archivos. La entrada SEC001 de WhatsApp es idéntica a la remota y el archivo resuelto satisface su hash normalizado y procedencia exactos. Se preservan por separado los hashes propios de fixtures CI/browser del piloto.
- Afirmación: los únicos cambios mecánicos Python propios restantes, `integrations/service.py` y `main.py`, no alteran comportamiento. Evidencia: `sol/probe_integrated_mechanical.py`, comparación AST/bindings contra origin/main con las mismas normalizaciones estrechas ya documentadas. Resultado: ambos PASS, incluidos SQL, literales, mensajes, condiciones, llamadas y guardas intactos. La equivalencia de lifespan y Depends/Annotated se mantiene.
- Refutación DI repetida sobre el árbol integrado: `sol/probe_di.py` PASS. Ambos alias conservan get_session con cache; cada request abre/cierra el generador una sola vez y el delegado sync/async recibe exactamente el sentinel inyectado. SQLite explícito, sin lifespan/migración ni red externa.
- Integridad del merge: `git diff --name-only --diff-filter=U` vacío; búsqueda de marcadores de conflicto en los cuatro Python/allowlist sin coincidencias; `git diff --check` y `git diff --cached --check` limpios.

Riesgo residual y gates: esta revisión demuestra preservación de la resolución y equivalencia de nuestros cambios, no sustituye las 17 pruebas focales ni CI del candidato integrado. Ruff completo y mypy94 del integrado fueron reportados verdes por el coordinador; registrar sus logs y el resultado de pruebas/CI antes de merge/publicación final. No se añadieron exclusiones ni cambios al detector SEC001. Esta integración no autoriza despliegue o configuración productivos.
## Extensión autorizada de arranque — contrato BDD-SC-192 / TDD-TC-053

Revisión R3 focal del mismo ciclo, tras autorización explícita comunicada por el coordinador: corregir arranque según el contrato. Sin hallazgos bloqueantes pendientes en la extensión revisada; PostgreSQL focal y CI final continúan bajo verificación raíz.

- Afirmación: iniciar/reiniciar la API no promueve el esquema ni queda condicionado a Alembic. Autoridad: BDD-SC-192, TDD-TC-053 y `docs/10-operacion-easypanel.md` §promoción manual (líneas729+), que exige migración separada antes de API/worker y detener promoción ante fallo. Evidencia: ambos Dockerfiles pasan de shell Alembic&&Uvicorn al argv directo de Uvicorn; main elimina el lifespan de migración y su hook. Refutación independiente: `sol/probe_startup_diff.py` compara el AST HEAD/árbol permitiendo únicamente retirar ese lifespan, sus imports y la keyword FastAPI correspondiente. Resultado PASS: ninguna otra llamada, guarda, ruta, excepción ni literal de main cambia; no se editó migración alguna.
- Afirmación: ni el dialecto PostgreSQL ni RESTAURANTOS_AUTO_MIGRATE=true reactivan migraciones al arrancar. Refutación independiente: `sol/probe_startup_runtime.py` usa SQLite y PostgreSQL loopback sintético con Engine.connect interceptado y Alembic upgrade prohibido; inicia/shutdown TestClient y consulta live/ready. Resultado PASS en ambos dialectos: startup/live200 sin una sola conexión de base ni upgrade, y readiness comunica postgres down/status degraded al simular base inalcanzable. Sin red externa, DDL ni base productiva. Las pruebas nuevas del repositorio conservan además las guardas estáticas de main/config y ambos CMD.
- Afirmación: actualizar expectativas head a0093 no debilita las guardas de integridad o downgrade. Refutación: el mismo probe AST compara los cinco archivos de pruebas afectados permitiendo sólo el literal `0092_supplier_xml_imports` → `0093_whatsapp_order_channel`. Resultado cinco PASS; condiciones, snapshots, assertions y controles de bloqueo permanecen idénticos. La cadena fuente tiene0093 como hijo de0092 y no hubo cambios de migraciones. El perfil exacto sólo incorpora branch_selection_block_reason=single_branch, ya parte del contrato auditado.

Evidencia ejecutada por el auditor: `pytest tests/architecture/test_repository_scaffold.py tests/architecture/test_alembic_version_capacity.py -q`: **21 passed,92.04s**, una advertencia preexistente Starlette/httpx sin silenciamiento. Probes independientes AST y runtime anteriores PASS; `git diff --check` limpio en la extensión. Raíz informó además arquitectura/perfil22passed103.21s, Ruff apps/api+tests verde y mypy94verde; no se atribuyen al auditor. Las once pruebas PostgreSQL de heads/integridad y CI del candidato final estaban pendientes al cerrar esta revisión; su resultado exacto debe quedar en PR/cierre sin convertir este estado en aprobación de gates no ejecutados.

Riesgo residual operativo: API puede estar viva con esquema pendiente o dependencia degradada; `/health/live` no acredita servicio utilizable. `/health/ready` comprueba disponibilidad de dependencias, no sustituye `alembic current` contra la revisión aprobada del release. Antes de desplegar/promover, un operador debe realizar el paso de migración separado, verificar revisión/código de salida y detener API/worker si falla; no ejecutar automáticamente los targets históricos de un runbook para otro release. Rollback de binario conserva esquema/historia y no dispara downgrade. Esta revisión sólo acredita la frontera de arranque: no certifica ausencia de DDL en otros recorridos heredados del repositorio ni autoriza ejecutarlos.

Preguntas operativas y señales existentes: ¿inició el proceso sin promover esquema? CMD directo/probe y live. ¿está la revisión aprobada aplicada? Alembic current y resultado del paso separado del release. ¿puede operar la API? readiness/version y canary autorizado. No se agregan logs de credenciales/payloads ni señales nuevas. No se ejecutó build Docker, despliegue, migración productiva o canary; esos gates siguen separados y la ejecución productiva requiere autorización propia.
