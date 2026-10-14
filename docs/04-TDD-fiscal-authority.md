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
Lectura histórica/corporativa: `test_fiscal_historical_reads.py` exige lista/detalle/PDF/XML de
sucursales inactivas autorizadas y lectura corporativa de otra sucursal activa sin contexto.
El lector de sucursal activa conserva su fence; org-role sin `invoicing.read` no amplía el permiso
de otro rol. Revalidación tras red impide bytes si se revoca actor/permiso/recurso. Emitir/recibir
en una sucursal inactiva rechaza antes del proveedor. Sin modificación de documentos, claves
históricas ni creación de contexto durante la lectura.
Una refutación móvil comprueba que `organization_branch_workspaces` no presta autoridad histórica
de B cerrada a un rol asignado sólo en A; exige alcance fiscal corporativo o asignación exacta
con esa capacidad como define SDD §50. El listado mixto usa contexto persistido revalidado, sin
inferir home branch desde roles históricos adicionales.

## TDD-TC-383 Elegibilidad y conservación de dinero

BDD-SC-680: conjunto vacío/duplicado/missing, mezcla branch/emisor/org/moneda, pago parcial,
PENDING, ausencia de pago, cancelado pagado y compensación confirmada. Sobrepago de un centavo,
cargos sucesivos respecto del pago original requieren revisión en emisión,
recibo y preparación; importe inferior conserva rechazo por pago incompleto. Un pago confirmado y ajustes CHARGE/REFUND cuyo neto
coincide exactamente con el total son positivos; se conserva la unicidad del pago confirmado. Se comprueban cero llamadas/efectos fiscales y fuentes
históricas iguales después del rechazo y de commit posterior. Comparar conjunto exacto de
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

Preparación incremental de TDD-TC-384: `test_fiscal_command_preparation.py` exige confirmación
atómica de comando/vínculos/reservas/outbox, snapshot cifrado, replay con las fuentes cambiadas,
receptor explícito, clave estricta, conflicto de otro payload/clave y rollback ante fallo de audit.
RED inicial: falta `prepare_invoice`; no llega al proveedor. Las pruebas del núcleo no acreditan
HTTP/worker, payload con impuestos ni recuperación externa; esos recorridos siguen pendientes.

Evidencia local de este incremento privado, sobre baseline publicada `914679c`: 22 casos de
preparación y 9 de trazabilidad verdes (`fiscal-command-sqlite-final.xml`); 14 de migración/head,
5 PostgreSQL de concurrencia/autoridad/FK-audit, 20 regresiones de elegibilidad/gateway y 21 del
gate de evidencia verdes. Los XML residen en `output/audit-remediation/`. El RED de error SQLAlchemy
se conserva en `fiscal-command-error-red.xml`: propagaba parámetros privados; el caso verde exige
error de negocio sanitizado, contexto suprimido y rollback completo. La auditoría independiente
registra las refutaciones y los fallos anteriores en `sol-fiscal-intents/AUDIT.md`.
CI del paquete anterior PR68 está verde; este incremento 0087 no está integrado en main ni cubierto por
esa ejecución. No acredita envío al PAC, worker, impuestos ni migración productiva.

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

Transporte exacto de TDD-TC-383: `test_fiscal_exact_json.py` inspecciona bytes POST reales en
loopback, decodificados con Decimal: 19.99, seis decimales, tasa y centavos altos conservan valor
y tipo numérico aun con contexto Decimal de baja precisión. Prueba invoice/receipt, Unicode y
strings que parecen JSON, y rechaza entrada inválida antes de red sin exponer payload. Los
límites de profundidad, cifra/exponente y cuerpo son límites técnicos del serializador; no
definen catálogo SAT ni tratamientos fiscales. La cobertura del cálculo/worker sigue pendiente. RED inicial: 1 TypeError al serializar Decimal;
Primera implementación: 34 casos dirigidos y 17 regresiones JSON/TLS/documento verdes.
Tras la refutación de amplificación de strings se usa escape por bloques: 35 casos dirigidos
verdes, incluido escape idéntico al estándar en fronteras Unicode/control; cinco legacy verdes. Ruff, mypy de dos fuentes y
9 enlaces de trazabilidad verdes; auditoría independiente en
`output/audit-remediation/sol-exact-fiscal-json/AUDIT.md`. La clave literal del test es sintética,
identificada por provenance y hash/ruta exactos en el mecanismo SEC001 existente; no se altera
el scanner ni se excluyen pruebas. No acredita cálculo fiscal, PAC ni CI del nuevo incremento.

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


Evidencia focal de conciliación del neto (TDD-TC-383): el RED original conserva seis rechazos
ausentes y tres fixtures incompatibles con unicidad de pago confirmado. La primera repetición
tuvo 64 verdes y seis fallas de esos fixtures; se corrigió el diseño de la prueba, preservando
el constraint. La repetición definitiva `fiscal-net-reconciliation-retry.xml` pasó 67 casos:
seis negativos de sobrepago/cargos sucesivos y tres positivos de ajustes balanceados, más las
regresiones existentes de elegibilidad/preparación. Diez refutaciones independientes verdes
incluyen cobro real sintético 9500 con recibido 10000/cambio 500 y REFUND/CHARGE/delta cero.
`sol-fiscal-net/AUDIT.md` conserva también el intento mixto independiente de 33 verdes/seis
fixtures antiguos ya cargados. Ruff, mypy focal, nueve enlaces y diff-check verdes. No cambia
SQL/locks ni activa una nueva afirmación PostgreSQL; CI final, worker/PAC y producción pendientes.


Evidencia local de lectura histórica/corporativa (TDD-TC-382): RED inicial cuatro 403; dos
repeticiones mixtas (2 verdes/2 fallas y 72 verdes/2 fallas) retenidas por una lectura de
comparación del seed que dejaba su Session abierta antes del transporte. Se cerró esa lectura
sin modificar la guarda de I/O. Repetición final 76 verdes; auditoría independiente 29
refutaciones y combinación de 105 verdes. La fuga móvil a B cerrada no asignada tuvo RED real
y se corrigió con permiso corporativo o rol de lectura exactamente asignado; no se extiende §50.
Tres casos PostgreSQL reales V2 verdes, en dos XML: lector corporativo con sucursal activa e
inactiva, y lector de sucursal asignada inactiva. En los tres, revocador y writer del documento
quedaron observados en pg_stat_activity con wait_event_type=Lock hasta commit de auditoría.
Artefactos `fiscal-history-*.xml` y `sol-fiscal-history/AUDIT.md` bajo output/audit-remediation.
El rechazo del perfil operativo con dos roles fue un hallazgo estático; no se fabricó RED:
la refutación cargó ya la lectura por contexto persistido. Login/profile/reissue sin rama activa
y su UI siguen pendientes W04/R01; esta lectura no acredita ese recorrido ni F03/F04/PAC/producción.

Publicación PR69: CI `38496167613` sobre `6acab5b` terminó con 1892 verdes, ocho skips,
siete warnings y dos fallos en TDD-TC-384. Las carreras conservaron la intención única,
pero su expectativa de downgrade 0087 era anterior a head 0088: el rollout sintético
`clean_install` activa primero la guarda de evidencia offline. Se conservan las carreras
en head, el Lock observado y todos sus rechazos; ahora exigen el error exacto 0088,
versión intacta y conservación de las seis tablas fiscales/offline. El nuevo caso
`test_0087_fiscal_history_blocks_downgrade` aísla la revisión 0087 real, confirma ausencia
de esquema 0088, exige su error exacto y conserva comando, vínculos, reservas y outbox.
No se editan migraciones, guardas, workflow, skips ni verificador; el caso nuevo se exige
automáticamente por colección dentro de los once módulos PG obligatorios.
La primera corrida focal pasó seis casos en 239.09 s, con un warning de Starlette:
`publication-fiscal-pg-current.xml`. El módulo se cargó antes de ampliar el snapshot
de los dos casos head; su repetición final pasó dos casos en 97.13 s (cuatro deseleccionados),
`publication-fiscal-pg-head-retention.xml`, con conservación de las seis tablas.
Arquitectura/trazabilidad/verificador: 32 verdes; scanner, Ruff y diff-check verdes. La revisión
independiente de este ajuste se conserva en `sol-publication-pg-fixture/AUDIT.md`.
No cambia runtime ni el alcance parcial F03/F04/W04; CI debe confirmar el SHA posterior.

CI `38499379049` sobre `559ede8`: 1895 verdes, ocho skips y siete warnings en 965.71 s;
el gate de los once módulos PostgreSQL pasó y mypy aprobó los 81 archivos. Ruff detectó
E501 (101 caracteres) en la asignación de tablas offline de `models.py`, no incluida en
el gate focal anterior. Se dividió esa línea sin cambiar el AST (comparación con lectura
UTF-8 explícita; el primer intento decodificó la salida Git como ANSI y se conservó como
intento fallido). Ruff completo `apps/api tests`, mypy81 y diff-check locales verdes.
Frontend de ese intento agotó la espera de foco del modal en `test_catalog_classification.mjs:119`;
la prueba existente pasó localmente en escritorio1440/móvil390, sin edición de UI ni tests.
La UI y el test no tienen diff frente a main914679c, y el CI anterior pasó ese recorrido.
No se borra el timeout ni se amplía su presupuesto; requiere confirmación posterior en CI.
