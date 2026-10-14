# Auditoría independiente R3: captura privada XML de proveedor

Fecha: 2026-10-14. Base observada: e17dae2, rama codex/supplier-xml-imports, diff de trabajo aún en evolución. Revisión fresca de AGENTS, README, skill restaurantos-development, referencia review-and-observability, PRD-FR-102/103/107, SDD64.2, BDD-SC-691..694 y TDD-TC-394..397. No se editaron implementación, especificaciones, Git ni datos productivos; sólo este informe y probes independientes en output.

Estado final de la revisión focal local: **SIN HALLAZGOS ACTIVOS**. Dos defectos P1 y un P2 se reprodujeron y corrigieron dentro del mismo ciclo; las refutaciones ahora pasan. Esta auditoría permite continuar a los gates del paquete, pero no acredita gates no ejecutados. No cierra X01, el plan completo de31 paquetes, validación fiscal/SAT, UI, CI ni un despliegue.

## Remediación y revisión final del mismo ciclo

- **F1 cerrado.** Bypass del buffering JSON se limita a POST de captura con UUID de branch y POST exacto resolve. El lector crudo propio aplica1MiB y deadline total5s después del preflight. Probe HTTP300000bytes ahora200; el probe ASGI sin bearer observa cero receive(). Un probe adicional sobre app ASGI real con receive demorado y deadline reducido sólo en fixture produce422 xml_upload_timeout y cero originales. Las rutas JSON hermanas conservan su límite262144bytes.
- **F2 cerrado.** _private_operation envuelve authorize/capture/resolve/metadata/download, convierte SQLAlchemyError en código privado estable y hace rollback local; wrapper HTTP también evita el handler SQL genérico. El mismo StatementError de lookup resolve ahora produce503 sin sentinel en respuesta ni caplog. Revisión de origen→SELECT/audit→respuesta/log no encuentra traceback ni parámetros en la frontera nueva.
- **F3 cerrado.** Contrato resolve actualizado en SDD64.2 a Idempotency-Key en header y body vacío; cualquier byte JSON se rechaza sin parser/echo. Main añade handler XML422 sanitizado incondicional, preservando Agent Tools400. Probe header válido recupera comando; header demasiado largo, JSON con key y extra contexto no reflejan valores. Probe independiente de UUID inválido en GET confirma handler422 sin input literal.

Reauditoría propia tras fixes:15 passed/18.41s, deadline ASGI1 passed/12.73s y validation-path1 passed/15.68s. Tras cambiar wrapper transaccional se repitieron solamente negativos y concurrencia PostgreSQL:3 passed/45.05s, mismos invariantes sin originales/comandos duplicados. No se efectuó un nuevo ciclo separado ni se alteró implementación para obtener verde.

También se revisó estáticamente el nuevo módulo test_supplier_xml_postgres.py y su alta en CI/verify_postgres_evidence.py: URL loopback y DB supplier_xml_test_* validada antes de DROP, ausencia URL falla sin skip, CI provisiona DB independiente y pasa URL, verifier exige todo caso recogido sin skipped/failure/error. El módulo agrega recorrido Alembic0091 real, bloqueo poblado, locks actor/branch/receptor, competencia key/UUID, restricciones, reissue público antes de captura y reissue bloqueado hasta auditoría/commit. Esta revisión no inventa resultado de ejecución del módulo del implementador ni de CI. Se recomendó usar una branchB existente para el adversario FK de scope, pues UUID inexistente prueba principalmente integridad referencial.

Ajuste operativo adicional revisado dentro del mismo ciclo, sobre HEADd00c03e antes de su commit: las rutas async llevan preflight+rollback, captura y resolve a run_in_threadpool del framework. Revisión estrictamente focal de diff API/test/SDD64.2/TDD-TC396; no cambia el dominio SQL. Se mantuvo el estado sin hallazgos activos después de6 pruebas propias HTTP/deadline/privacidad/validación verdes (14.79s) y2 pruebas de ejecución fuera del loop/progreso del scheduler verdes (11.60s). No se repitió PostgreSQL ni suite completa porque los contratos SQL permanecen iguales.

## Hallazgos históricos reproducidos y remediados

1. **P1 — middleware anula la frontera XML (workspace_body_limit.py:40..75).** La ruta nueva comienza con `/api/v1/purchases`, por lo que el middleware consume la red completa antes del preflight y sin deadline, con límite de 262144 bytes. Una captura HTTP de 300000 bytes produjo 413 `workspace_payload_too_large`; un probe ASGI sin autenticación observó `receive()` antes del rechazo 401. El reader XML de 1MiB/5s llega después de ese buffering y no gobierna la red. Refutaciones: `test_raw_http_above_workspace_limit_reaches_xml_one_mib_contract` y `test_capture_preflight_rejects_unauthenticated_request_before_receive`. Corregir la excepción exacta de la ruta de captura cruda preservando límites de otros writers.

2. **P1 — fallo SQL de resolución registra idempotency key (api.py:_supplier_xml_response → _database_response).** El wrapper genérico registra `traceback.format_exc()`, que contiene SQL y parámetros de StatementError. Un fallo inyectado en el SELECT real de `supplier_document_import_commands` dejó `sol-private-command-sentinel` en caplog. La respuesta HTTP503 de ese probe no incluyó la clave, porque repr(StatementError) no imprime sus parámetros; el defecto demostrado es el log. Refutación: `test_resolve_sql_failure_never_exposes_command_key`, 1 fallo. Captura tiene traducción SQL segura, resolución/metadata/download/preflight carecen de ella. Corregir sólo el wrapper XML, con salida estable y registro sin excepción cruda/SQL/params.

3. **P2 — validación de resolve refleja key/contexto (api.py:SupplierXmlResolveRequest y handler FastAPI).** Key de más de128 caracteres o extra `branch_context` devuelve 422 con `input` literal, aunque el contrato exige DTO sin key ni contexto. Refutación: `test_resolve_invalid_payload_does_not_echo_sensitive_values`, dos fallos. Usar respuesta de validación sanitizada y acotada al nuevo contrato, preservando el handler existente de Agent Tools.

## Afirmaciones R3 e intentos de refutación

### C1 — persistencia y efectos privados permanecen atómicos

Afirmación: original, comando y auditoría se confirman juntos; no se dejan filas parciales.
Evidencia: servicio inserta sólo tres tablas privadas y audit_events y no llama a dominio de compra/stock/caja/deuda. Wrapper capture hace rollback ante errores de dominio, SQL y genéricos.
Intento de refutación: fallos después del INSERT original, después del INSERT comando y durante auditoría, usando after_cursor_execute y _audit en SQLite efímero.
Resultado: tres probes pasan; cero filas privadas nuevas y auditoría igual al estado previo.
Riesgo residual: concurrencia y bloqueo reales PostgreSQL pendientes de gate focal; la ausencia de llamadas a otros dominios se combina con la comparación de ledgers del test original, no acredita contabilización futura.

### C2 — commit realizado con respuesta perdida permite resolver sin duplicar

Afirmación: un commit cuyo acuse se pierde deja un comando terminal recuperable.
Evidencia: command se persiste antes de _result; resolve requiere actor/org/key actuales y permiso del recurso, sin flag de captura ni contexto operativo.
Intento de refutación: Session.commit real seguido de OperationalError sintético antes del retorno HTTP.
Resultado: pasa; capture devuelve supplier_xml_persistence_unavailable y resolve recupera unverified con una importación y un comando.
Riesgo residual: pérdida de conexión real durante COMMIT no simulada a nivel TCP; gate PostgreSQL/CI pendiente. Negativos cross-branch se rechazan antes de command para no enlazar otra branch; no se presentan como negativos persistidos.

### C3 — lectura y resolución derivan scope del recurso histórico

Afirmación: permisos actuales se evalúan contra branch original; no basta seleccionar otra branch.
Evidencia: _read y resolve consultan org vigente, toman lock gobernanza/actor y requieren purchases.read/manage con la branch del registro. No usan branch suministrada por cliente para lecturas.
Intento de refutación: convertir actor existente en rol branch y asignarlo sólo a otra branch después de capturar; probar metadata, download y resolve.
Resultado: pasa; las tres operaciones rechazan con permission_denied. El test original cubre historia de branch inactiva y captura flag off.
Riesgo residual: comprobar lock real frente a transición y revocación en PostgreSQL. Semántica corporativa usa guardas hermanas canónicas require_permission.

### C4 — AAD/hash y keyring protegen el original sin fallback

Afirmación: originales siguen bytes exactos; cambio de scope/evidencia o falta de clave impide liberarlos.
Evidencia: AESGCM contextual liga propósito, organización, branch, entidad, import/evidencia, UUID y hash; download compara tamaño y SHA256 después de descifrar. Resolver común de clave extrae exactamente el código fiscal previo y no amplía el envelope fiscal.
Intento de refutación: intercambiar ciphertext entre importaciones; rotar clave activa conservando la anterior; retirar clave anterior.
Resultado: tres condiciones pasan: sustitución falla, rotación lee original antiguo y remoción falla cerrado. Ejecución adicional de test_supplier_xml_crypto.py + test_fiscal_emitter_refutations.py:51 passed/35.38s. Comprueba1MiB/UTF16/tampering de XML y guardas fiscales/rotación privadas heredadas; unseal fiscal mantiene límite65536 sin diff en su implementación. F1 fue remediado y el límite HTTP se revalidó como consta arriba.
Riesgo residual: operación productiva depende de conservar keyring histórico; no se generaron claves ni se habilitó configuración productiva.

### C5 — migración añade sólo tablas scoped y bloquea pérdida de historia

Afirmación: upgrade aditivo/downgrade vacío conserva historia previa; downgrade poblado falla.
Evidencia: revision0092 desde0091, FKs compuestas actor/org/branch/entidad/original/conflict, UNIQUE org/UUID y org/actor/key, checks tamaño/hash/perfil/unverified y link resultado-conflicto; downgrade inspecciona cualquier tabla privada antes de DROP.
Intento de refutación: probes SQLite reales de upgrade/downgrade vacío sobre esquema base sintético y downgrade con original capturado.
Resultado: SQLite 2 passed/9.95s y PostgreSQL 2 passed/24.92s. Upgrade/downgrade vacío preserva ledgers previos; downgrade con original/conflicto/comando bloquea sin cambiar ninguna fila privada. Los probes ejecutan la migration0092 real sobre esquema sintético equivalente, no el historial Alembic completo desde0091.
Riesgo residual: recorrido Alembic versionado desde0091 y CI pendientes del gate que se revisará; upgrade/downgrade directo de la migration actual sí se probó en ambas bases.

### C6 — PostgreSQL conserva exclusión de autoridad y comandos simultáneos

Afirmación: locks de actor/branch/entidad impiden cambios hasta commit; dos capturas no crean originales o comandos duplicados.
Evidencia: PostgreSQL local55444, usuario xmltest, DB exclusivamente supplier_xml_test_sol. authorize_capture mantiene NO KEY UPDATE sobre actor y branch/entidad; locks advisory de gobernanza/key/UUID hasta commit.
Intento de refutación: otro Session intenta inactivar actor, branch o entidad con lock_timeout200ms mientras authorize_capture conserva transacción; tras rollback repite. ThreadPoolExecutor y Barrier lanzan dos imports con mismo key y con keys distintos sobre mismo UUID.
Resultado: locks/negative-command/status-check 4 passed/56.81s; actor/branch/receiver updates fallan por lock y después pasan. Concurrencia 2 passed/18.78s: mismo key deja1original/1command; keys distintos dejan1original/2commands y resultado duplicate durable. CHECK fiscal_validation valid rechaza y download original exacto sigue disponible.
Riesgo residual: pruebas locales sintéticas, no canary; modificación de selección/contexto V2 y rollout completo dependen del gate del implementador. PostgreSQL detectó warning ya existente de ciclo orders/public_order_intents durante enumeración de todas las tablas para TRUNCATE sólo de DB propia; no se ignoró ningún fallo.

### C7 — esperas síncronas SQL no bloquean el event loop ASGI

Afirmación: preflight incluido rollback, captura y resolve se ejecutan fuera del event loop; Session se usa secuencialmente y no se mantienen locks durante la lectura de red.
Evidencia: run_in_threadpool(preflight) se espera antes de read_original; preflight hace rollback en ese mismo worker después de autorizar. Después de terminar la lectura, un segundo await run_in_threadpool ejecuta capture. Resolve verifica cuerpo vacío antes de su llamada SQL en worker. No se crean tareas paralelas sobre una Session y no cambia el código de dominio.
Intento de refutación: test mantenido test_async_upload_runs_database_operations_outside_event_loop instrumenta authorize/capture/resolve y rechaza asyncio.get_running_loop() dentro de ellas (RED1F reportado por implementador). Probe independiente test_event_loop_progresses_while_sync_preflight_waits bloquea el worker con Event hasta que una coroutine del mismo event loop progresa; el flujo ASGI real debe concluir200. Además se repiten deadline realASGI, preflight sin body anónimo, captura300KiB, SQLprivacy, headerresolve y validación sin echo.
Resultado: prueba mantenida y probe de progreso2 passed/11.60s; negativos HTTP anteriores6 passed/14.79s. SQL no bloquea el loop, el deadline de lectura y la salida privada conservan comportamiento. git diff --check sin fallos.
Riesgo residual: pool de workers y conexiones es finito; una espera de locks puede ocupar un worker y solicitudes posteriores pueden hacer cola. No se certifica concurrencia ilimitada ni latencia de la fase SQL. Los5s acotan lectura de body, no duración total de autorización/captura. Una Session puede pasar secuencialmente por workers distintos, sin compartir ejecución concurrente. El adaptador y pool de base real conservan sus límites de operación.

## Preguntas operativas y señales

- ¿Qué original/comando quedó después de un timeout o respuesta perdida? Eventos captured/replayed/resolved con IDs y result_kind, nunca key/contexto/UUID/RFC/XML.
- ¿Qué impidió captura/descarga sin comprometer privacidad? Códigos estables de autoridad/parser/crypto/persistencia; los probes F2/F3 remediados comprueban fallos SQL/schema sin clave/contexto en respuesta/log.
- ¿Una captura alteró compra/stock/caja/deuda? Comparación antes/después de ledgers y command/original específicos; no usar métricas con RFC/XML ni dimensiones libres.

## Evidencia local y límites

Probes ubicados en `output/audit-remediation/sol-supplier-xml-capture/test_sol_supplier_capture.py` y `test_sol_supplier_capture_pg.py`. Interpreter: `C:/Users/Miguel Gonzalez/.codex/worktrees/implement-audit-remediation/Kiwi/.venv/Scripts/python.exe`, cwd supplier-xml-parser/Kiwi. Primer conjunto: 8 passed (antes de incluir caplog), luego fallos dirigidos F1/F2/F3 como arriba. SQLite migration2P y PG8P en tres conjuntos focales independientes. `git diff --check` pasó; warnings CRLF no son fallo de integridad. No se ejecutó CI, suite completa, canary, migración productiva ni se tocó DB de root en55444 o cluster antiguo55443. La DB supplier_xml_test_sol fue creada para esta auditoría y permanece como evidencia local; no comparte schema ni fixtures con root.
