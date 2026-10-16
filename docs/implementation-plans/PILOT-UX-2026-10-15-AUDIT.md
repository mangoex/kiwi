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
## Revisión focal del mismo ciclo — guardas de detalle, impresión y SEC001

Se revisaron las modificaciones posteriores: History valida `detail.branch_id === branchId` antes de `setSelected`, mantiene fencing de secuencia y limpia selected/loading al detectar un branch_id de enlace distinto. Resultado: falla cerrado ante enlace que afirma A pero respuesta B, y no deja visible el detalle previo en ese rechazo. ProductsList incorpora una tabla del catálogo filtrado, oculta en pantalla y visible sólo en media print; la vista de trabajo se oculta al imprimir. Conserva Imprimir sin devolver lista lateral ni introducir escrituras. Sin hallazgo bloqueante en estas modificaciones. Se leyó la nueva prueba `tests/browser/test_pilot_pos_admin.mjs`: incluye respuesta B, cero lecturas del enlace branch B, cancelación de edición/alta y tabla print, en 1440/390. La ejecución verde de navegador fue reportada por el coordinador; el auditor revisó su contrato pero no la repitió.

El scanner local emitió `apps/api/tests/test_whatsapp_integration.py|sensitive_signature`; las seis pruebas de `tests/architecture/test_sec001_repository_policy.py` pasaron (5.77s). El mecanismo exacto está previsto por SDD (RepositoryPolicyGate: ruta, hash y procedencia exactos) y TC145 exige que contenido modificado, otra ruta o procedencia incorrecta vuelvan a rojo. AGENTS.md permite excepciones locales, estrechas, justificadas y visibles; prohíbe conseguir verde mediante silenciamientos generales.

Conclusión SEC001: una inscripción de UNA ruta con hash LF-normalizado del blob realmente incluido en el candidato y procedencia `restaurantos-whatsapp-asistto-fixtures-v1`, tras revisar que sus credenciales son literales sintéticos de tests y documentarlo en el diff/revisión, es una remediación apropiada del mecanismo ya especificado. No requiere alterar PRD/SDD ni cambiar scanner/tests/umbrales, y no equivale a una autorización de secreto real. El marcador por sí solo no prueba inocuidad ni permite aceptar hashes nuevos automáticamente. Esta auditoría no modificó la allowlist ni el archivo WhatsApp.

Advertencia de aislamiento del candidato: durante esta revisión aparecieron cambios de trabajo ajenos en `apps/api/tests/test_whatsapp_integration.py` (+61 líneas de TC405), `apps/api/restaurant_os/integrations/whatsapp.py` y actualizaciones de hashes en la allowlist. No son del auditor; preservar su propiedad. El archivo WhatsApp actual NO es idéntico al blob base0aec8ba y `git diff --check` global falla por su nueva línea vacía EOF (línea700). Por tanto no se debe registrar ciegamente el hash de todo el árbol actual para publicar el piloto. Si se incluye la remediación estrecha, usar el contenido exacto que irá en el candidato y comprobar scanner/integridad en checkout aislado de ese candidato; el reporte global del árbol compartido puede seguir rojo por trabajo ajeno. Si se omite esa inscripción, el gate queda como blocker de base y la entrega puede ser PR sin merge; no presentarlo como verde.

La auditoría de lógica del piloto queda sin bloqueantes pendientes; autorización de merge depende además de gates reales del candidato, sin atribuir cambios concurrentes ajenos al piloto.
