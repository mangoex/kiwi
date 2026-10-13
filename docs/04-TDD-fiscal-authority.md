# TDD - Facturación directa gobernada

## TDD-TS-142 FISCAL-001

RED dirigido antes del cambio: API y servicio con FakePAC que cuenta llamadas/identidades;
fixtures de dos organizaciones, emisores y sucursales, lector/emisor/configurador independientes,
pedidos pagados/parciales/cancelados, moneda distinta y configuración apagada/insuficiente.
Ninguna prueba de este paquete envía mensajes ni documentos a un proveedor real.

## TDD-TC-382 Autoridad por recurso y proyección segura

BDD-SC-679/683: negativos por endpoint, actor inactivo/sin grants/lector, branch query omitida o
cruzada, ID desconocido/ajeno, config sin alcance organizacional. Assert cero llamadas al FakePAC,
filas fiscal sin cambios y ausencia de api_key/raw response en DTO/log/auditoría. Positivos con
permisos persistidos explícitos; nunca por nombre Dueño ni claims del token. PDF/XML autenticados
prueban lector correcto y credencial vigente, sin URL con secreto.
Descargas focales: formatos PDF/XML, cruce de sucursal y actor sin permiso, pendiente/UUID o ID
inválido, URL legacy maliciosa ignorada, cuenta/contexto revocado durante red, sink fallido, MIME,
redirección y archivo excesivo. Assert ninguna transacción abierta durante el adaptador, bytes
privados ausentes en errores/logs y fuente legacy conservada. Cliente real usa bearer/contexto,
descarta respuesta tardía y revoca blob; navegador verifica descarga y el estado visible.

## TDD-TC-383 Elegibilidad y conservación de dinero

BDD-SC-680: conjunto vacío/duplicado/missing, mezcla branch/emisor/org/moneda, pago parcial,
PENDING, ausencia de pago, cancelado pagado y compensación confirmada. Comparar conjunto exacto de
relaciones y versión fuente. Config ausente/apagada/ambigua y datos fiscales incompletos generan
rechazo sin PAC. Centavos como 19.99, medio centavo y acumulados no usan float; total de conceptos e
impuestos conserva el total autorizado. No se acepta IVA ni datos de identidad por fallback.
Configuración por emisor: dos razones sociales y otra organización, lectura sin clave, schema
estricto/versiones, estado deshabilitado inicial sin valores SAT inventados, RFC discordante,
ambiente cambiado sin nueva clave y versiones obsoletas. Las revisiones se conservan cifradas;
alterar ciphertext/AAD o retirar una clave produce fallo cerrado. Original legacy permanece
idéntico y no habilita emisión/recibo. Sink fallido revierte identidad/revisión/audit. Migración
aditiva SQLite/PG preserva original y bloquea downgrade con configuraciones/documentos ligados.

## TDD-TC-384 Comando durable y recuperación tras fallos

BDD-SC-681: same-key/body, key con payload distinto, recursos cambiados, revocación entre replay,
respuesta perdida y reinicio. FakePAC guarda clave/ref remota; inyectar caída antes/después de PAC
y antes/después de commit. Resultado desconocido permanece recuperable; nuevo key no evade la
reserva del pedido. Comparar una intención, outbox/inbox coherentes y una identidad externa.

## TDD-TC-385 Proyección monotónica de emisión y cancelación

BDD-SC-682: pending/verifying sin UUID, valid con/sin UUID, rejected/desconocida, cancelación
pending/verifying/accepted/rejected y evento final tardío/duplicado. Nunca fabricar UUID/ID externo;
conservar original protegido. Firma inválida rechaza antes de procesar inbox. Polling respeta
identidad, no retrocede estados finales y no transforma timeout en cancelación confirmada.

## TDD-TC-386 PostgreSQL, workers y migración

BDD-SC-684: dos sesiones/claim de worker y lease vencida, reservación concurrente del mismo pedido,
lectura/autoridad revocada y expansión de schema desde head previa. Observar locks/uniques reales y
que red no sostiene transacción. Upgrade conserva history; downgrade con documentos/commands
rechaza. La evidencia PG se incorpora al verificador CI cuando exista la suite, sin declarar un
gate aprobado por compilar o por tests SQLite. Migración productiva y sandbox externo separados.

## TDD-TC-387 UI y contrato fiscal visible

BDD-SC-681/682/683: capacidad lectora sin emisión, configuración sin mostrar clave, recibo/pedidos
pagados, intención incierta recuperable por cuenta, doble clic/tabs, reload y respuesta tardía.
Estados pendientes no muestran UUID/enlace final ni permiten nueva emisión. Descargas pasan por
API autenticada. BDD-SC-680 verifica petición estricta y conserva importes/versiones, sin cálculo
fiscal paralelo en JavaScript. Typecheck, prueba semántica y navegador dirigidos al flujo afectado.

Las pruebas legacy `test_facturapi_integration.py` no acreditan este contrato. F02..F04 implementan
los casos progresivamente; los archivos y gates todavía no ejecutados permanecen pendientes.

Evidencia incremental F01/F02 y D02 (local, sin PAC externo):

- `test_fiscal_authority_remediation.py`: 23 casos API de permisos, conjunto estricto y DTO.
- `test_fiscal_authority_audit.py`: 12 casos de contexto V2, actor/scope, denegaciones, errores
  sanitizados y rollback ante fallo del sink; commit posterior no publica configuración sin audit.
- `test_fiscal_permission_migration.py`: 7 casos SQLite de registro sin grants, versión una vez,
  colisiones/overflow y downgrade con asignación/config; revisión independiente agrega colisión
  tardía y documentos sin configuración.
- `test_fiscal_authority_postgres.py`: migración real y barrera de revocación de configuración;
  la revocación espera gobierno/actor hasta el commit auditado. Primera ejecución de migración
  interrumpida sin evidencia, repetición acotada con stdin cerrado pasó; no cuenta la interrupción
  como gate verde. El verificador CI exige ejecutar esta suite, sin skips ni ausencia de collection.
- `test_fiscal_eligibility.py`: 19 casos de pago confirmado completo, cancelación, alcance/moneda,
  compensación enlazada, importe corregido e historia preservada. Proyección en centavos; no
  certifica todavía impuestos ni serialización del adaptador.
- `test_fiscal_eligibility_evidence.py`: 17 refutaciones permanentes de delta inconsistente, JSON
  malformado, bool/float, compensaciones ajenas y conjunto parcialmente elegible. Suite dirigida
  conjunta de elegibilidad: 36 passed; revisión independiente repitió los 17 negativos sin relajarlos.
- La prueba PG de snapshot conserva bloqueos reales de pedido, pago, corrección y ajuste hasta
  rollback: cuatro writers esperan `Lock` simultáneamente; las fuentes y la proyección se conservan.
  Se incorpora a `test_fiscal_authority_postgres.py`; verifica snapshot, no reserva ni worker.

La auditoría independiente de autoridad cerró una carrera P1 y dos omisiones de auditoría P2;
la revisión de elegibilidad cerró un P1 (delta inconsistente) y un P2 (snapshot malformado/tipos).
- `test_fiscal_downloads.py`: 33 casos de PDF/XML autenticados, evidencia final coherente,
  archivos legacy ambiguos sin efecto, origen fijo/tamaño/MIME/redirect, fallos sin bytes y enlaces
  históricos no publicados. Cinco pruebas de evidencia final y dos fugas de URL fallaron antes
  de sus correcciones; filas originales se conservan.
- `test_fiscal_capability_projection.py`: 4 casos de proyección fiscal independiente y
  configuración sólo bajo autoridad organizacional de esa misma capacidad.
- `test_fiscal_reader_workspace.py`: lector V2 recupera contexto/consulta sin grants POS/caja;
  configuración sola no reemite contexto. `test_fiscal_download_refutations.py` conserva
  4 adversarios que exigen transporte real antes de suspender actor/cambiar alcance/ID/estado
  y una proyección no mutante con comparación profunda del original.
- Conjunto focal de autoridad/descargas/capacidades/contexto: 78 passed. El adversario de
  proyección añadido después pasó de forma focal; no se repite una suite verde sin un nuevo riesgo.
- PG permanente de descarga observa ambos PID (revocación canónica y writer noop CFDI) en
  `wait_event_type=Lock` antes del commit auditado: 1 passed, 3 deselected; no holds DB durante PAC.
  La prueba ya se incorpora a la suite fiscal obligatoria del verificador CI.
- `test_fiscal_document_transport.py`: 2 respuestas slowdrip reales de cabeceras/cuerpo en loopback
  verifican el presupuesto de 20 segundos del método, excluyendo sólo limpieza del servidor del
  tiempo medido. DNS/TLS bootstrap mantiene el límite de plataforma explicitado en SDD.
- Cliente: semántica bearer/contexto, credencial faltante, archivos privados, blob revocado,
  cuenta/contexto tardíos y denegaciones verde; navegador sintético a 1440/390 valida lector V2,
  descarga local, estados distintos y configuración sin hidratar credencial. Build Admin,
  typecheck recursivo de los 6 proyectos con script, mypy/lint focales e integridad documental verdes.
- Auditoría independiente del incremento cerró una carrera P1 y dos P2 de timeout y contexto
  fiscal; extensión de URLs históricas verde. Evidencia local en
  `output/audit-remediation/sol-fiscal-artifacts/AUDIT.md` y JUnit focales.

Incremento de configuración explícita por emisor (F02):

- `test_fiscal_emitter_configuration.py`: RED inicial de 27 casos y luego 28 verdes; configuración
  por razón social, expected_version estricto, identidad/ambiente/credencial, protección de legacy,
  ausencia de keyring y cierre de emisión/recibo sin vínculo antes del PAC.
- `test_fiscal_emitter_refutations.py`: revisión independiente de 41 casos, más la regresión
  existente de atomicidad legacy. Corrige selección de credencial histórica P1, secretos en logs P1,
  normalización de Organization/revalidación de razón social/marcador de audit P2. Refuta ciphertext,
  contexto, rotación, rollback, redirects, JSON excesivo/no objeto, referencias cambiadas en red
  y escritura legacy. El positivo usa Organization del contrato oficial, no el mock legacy.
- `test_fiscal_emitter_migration.py`: 5 casos SQLite verdes en repetición focal con stdin cerrado
  y timeout explícito. `test_fiscal_emitter_postgres.py`: dos carreras create/revoke verdes con PID
  esperando `Lock`, una revisión/audit, conflicto explícito o versión de autorización 2/denegación;
  migración aditiva y guard downgrade verdes en repetición focal.
- La suite fiscal de 198 casos terminó 197 verdes y un proceso Alembic detenido sin stderr;
  la repetición SQLite de cinco casos pasó. PG conserva un timeout auxiliar de upgrade y dos carreras
  verdes, seguido por la migración focal verde. Esas ejecuciones mixtas permanecen en JUnit, nunca
  se presentan como suites completamente verdes. No se relajaron aserciones ni se omitieron casos.
- Las 36 pruebas de elegibilidad y 5 positivas anteriores pasan con emisor explícito y PAC inyectado:
  41 passed. Los datos sintéticos no dependen del mock implícito del factory de runtime.
- Dos regresiones PG de autoridad/config legacy y descarga con origen histórico conocido: 2 passed,
  2 deselected; ambas esperan el commit auditado antes de revocar/modificar el recurso.
- Verificador de evidencia PG: 13 casos verdes/6 deselected; exige ahora 9 módulos, incluyendo
  `fiscal_emitter`. Ese gate valida el verificador, no acredita ejecución local de los 9 módulos.
- Admin build/typecheck, mypy focal de 7 archivos, Ruff, descarga semántica, integridad de plan,
  trazabilidad y navegador sintético verdes (lector 1440/390, configurador 390). Formulario exige selección/versiones, no copia
  secretos, limpia clave al cambiar de emisor/cuenta y no atribuye éxito al resultado false.
  Una revisión externa bloquea guardar/probar sin rebasar el borrador; recargar explícitamente
  descarta la clave y carga la versión actual. Navegador verde tras corregir el evento de foco
  sintético (window, no document); un intento auxiliar de navegación agotó timeout y su reprise pasó.
- Auditoría independiente del incremento y sus extensiones:
  `output/audit-remediation/sol-fiscal-emitters/AUDIT.md`. Configuración productiva/keyring no tocados.

El gate focal de transporte JSON utiliza respuestas loopback reales con cabeceras/cuerpo slowdrip
y un positivo rápido: debe terminar dentro del presupuesto sin repetir solicitudes ni revelar
credenciales. DNS/TLS previo al socket mantiene el límite de plataforma declarado en SDD.
La revisión independiente usa TLS real local con certificado sintético temporal: 12 casos verdes,
incluyendo cert no confiable/hostname distinto, escritura bloqueada, slowdrip entre fases,
chunked/sin longitud, redirect, HTTP error, cuerpo truncado y cleanup de Timer/socket.
El P2 de paridad PDF/XML truncado tuvo RED real y reprise verde independiente; la validación
de Content-Length restante ahora precede retornar bytes. Las refutaciones se incorporan como
`test_fiscal_json_tls_transport.py` (presupuesto sintético de 1 s, sin modificar runtime) y
`test_fiscal_document_truncation.py`. El combinado permanente pasó: 51 casos de JSON20s,
TLS local, truncación, documento20s y descargas; JUnit `fiscal-shared-transports-current.xml`.
Siete regresiones de saneamiento/redirect/tamaño del emisor también verdes; Ruff/mypy focales
y `git diff --check` verdes. No se repitió la suite fiscal completa ni PG sin riesgo de persistencia.
Se conservan RED JSON 2 failed/1 passed, primer intento 43 passed/1 failed y segunda reprise
2 passed/1 failed; read1 con timeout restante y salida normal sin reutilizar FD cerrado corrigen
los fallos. Esos JUnit no se renombran ni se presentan como completamente verdes.
Revisión: `output/audit-remediation/sol-fiscal-json/AUDIT.md`; no certifica efecto externo ni
ausencia de emisión tras timeout. Una intención durable debe reconciliar esa incertidumbre.

F03 requiere comando/relaciones/snapshot durable/worker/recuperación y dinero/impuestos exactos;
el deadline total JSON está revisado y con gate combinado focal verde. F04 requiere estados finales. Ninguna evidencia
local acredita CI, sandbox externo, migración o comportamiento productivo.
