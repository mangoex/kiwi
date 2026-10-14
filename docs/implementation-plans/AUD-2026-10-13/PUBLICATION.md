# Publicación de incrementos revisados AUD-2026-10-13

Autorización del usuario: commit, merge y push para que él haga el redeploy. Riesgo R3.
Esta publicación entrega los incrementos implementados; no declara terminado el plan de 31 tareas.
`execution.json` conserva el estado por tarea, decisiones D02/D03/D04 y pendientes fiscales,
de sucursales, cuentas por pagar y compensaciones. No se modifica producción desde esta tarea.

## Versión de código publicada para el redeploy

PR [72](https://github.com/mangoex/kiwi/pull/72) integrada en `main` como
`758a1b1eb3f4621b594cd04d0be488a365573e3c`. El árbol completo coincide exactamente con
`f58a0015b2bb2394b51e9de34bfbe3c51a287c11`, aprobado por
[CI 38544220053](https://github.com/mangoex/kiwi/actions/runs/38544220053): 2022 pruebas aprobadas,
ocho skips existentes y siete warnings en 1608.37 s. El gate obligatorio confirmó 82 casos
ejecutados entre doce módulos PostgreSQL. Mypy API (85 archivos)/gateway (cuatro), Ruff,
frontend, Docker, políticas y dependencias aprobados. Frontend pasó en el intento 2 sobre el
mismo SHA; el timeout original de catálogo y su diagnóstico se conservan en el cierre inferior.

El esquema requerido es `0090_operational_intents`; el contenedor inicia la API sin ejecutar
Alembic. Antes de servir el nuevo código, respaldar PostgreSQL y, desde `apps/api` con la conexión
del entorno correspondiente, aplicar `python -m alembic -c alembic.ini upgrade head` y comprobar
`python -m alembic -c alembic.ini current`. Desde 0089 se agrega la tabla/índice vacíos; una base
anterior recorre la cadena pendiente. Desplegar API/POS del mismo commit y comprobar
`/health/ready` y `/health/version`, conservando el SHA desplegado. No forzar downgrade 0090 si
existe cualquier intención, incluidas terminales: la guarda conserva su historia.

Conservar `RESTAURANTOS_SIGNED_OFFLINE_AUTHORITY_ENABLED` apagado salvo activación operativa
autorizada. La nueva tabla no acredita adopción ni retirada de emisores legacy. El registro central
cubre inicialmente pedido/pago/movimiento; otros comandos, offline y adopción siguen pendientes.
W04 y el plan de 31 tareas continúan parciales. Este cierre acredita Git/CI, sin cambios productivos.

El cierre posterior es R0: actualiza sólo esta guía y la referencia de evidencia en
`execution.json`, conservando runtime, estados de tareas y decisiones. Los resultados fallidos
anteriores permanecen documentados en las secciones históricas y TDD.

## Alcance del primer paquete (PR 68)

Compras corporativas: reparto exacto de cantidad/costo, snapshots por destino, validación de
catálogo y recuperación de la intención por cuenta. Sucursales: autoridad vigente, contexto
durable y recuperación del cliente, guardas focales de caja/KDS/impresión/sync. Facturación:
capacidades propias, elegibilidad de pago completo/no cancelado, descarga autenticada,
configuración cifrada/versionada por razón social y transporte acotado con rechazo de truncación.
Las auditorías independientes y pruebas dirigidas están registradas en los TDD de cada alcance.

F03 (comando fiscal durable, recuperación e impuestos exactos) y F04 (ciclo completo de estados)
siguen pendientes. La configuración explícita no acredita CSD, SAT ni uso productivo del proveedor.

## Evidencia local de publicación

- Ruff de `apps/api tests`: verde. Mypy de los 76 archivos de backend: verde. Se corrigieron cinco
  anotaciones faltantes en Agent Tools, sin cambiar decisiones de negocio; sus 15 pruebas verdes.
- Typecheck frontend: verde. Builds Admin/POS: verdes; conservan advertencias de tamaño de bundle.
- Arquitectura/dependencias/trazabilidad: 28 pruebas verdes. Política/ratchet: 14 pruebas verdes.
- Scanner y ratchet de diff: verdes; fixtures sintéticos registrados por ruta, procedencia y hash
  exactos. Sin cambiar el scanner ni añadir exclusiones de pruebas.
- Transporte fiscal/descarga: 51 pruebas verdes; los intentos mixtos anteriores se conservan en TDD.
- La suite semántica frontend y CI se reportan por su resultado real en el cierre Git. No se
  presentan como aprobados sólo por estos gates locales. Las suites PG dirigidas previas y sus
  repeticiones constan en TDD; no se sustituye el gate PG obligatorio de CI por SQLite.

## Correcciones detectadas por CI durante la publicación

El selector E2E de conciliación identifica el desplegable por su opción de sucursales, sin asumir
su posición en la página; el recorrido real Admin/POS pasó localmente. La semilla offline ahora
selecciona todas las columnas explícitas: preserva la versión de autorización y vuelve a hidratar
el bundle exacto. Diez pruebas catálogo/gateway, E2E POS pago/KDS, Ruff y mypy verdes localmente.
Auditoría independiente: conservación 7→9 al renovar y rechazo de versión ausente/columna adicional
sin instalación parcial. Afirmación: no hay fallback de autoridad; resultado refutado con esos casos.
Riesgo residual: la fuente debe tener la migración de versión aplicada; no se habilita una fuente
anterior por tolerancia. La firma/reinicio se comprueban en la prueba de runtime existente.

Los tests funcionales PostgreSQL usan head. Sólo sus casos de reversibilidad aíslan la revisión
0055/0065/0071/0073 que verifican; el caso de combos inicia en 0082 porque la ejecución actual
requiere el esquema de modificadores compartidos posterior a 0066. Conservan los rechazos de historia y no evitan la revisión
0085 en producción. El gate estructural exige head 0086. La prueba 0077 comprueba lectura legacy
con V2 apagado y rechazo de migración incompleta al encenderlo. Crossorg conserva rechazo opaco
y cero asignación. No se cambiaron guardas, skips ni silenciamientos para obtener verde.

PostgreSQL focal: 13 verdes y un timeout local de Alembic. La primera repetición de combos en
0066 rechazó un esquema sin modificadores compartidos; con baseline 0082 pasó en 25.09 s y
conservó el rechazo exacto de historia 0066. Cada intento mantiene su XML separado.
SQLite 0077: la ejecución interrumpida se conserva y su repetición pasó
en 21.36 s. Arquitectura/perfiles: 25 verdes independientes; mypy completo de backend y Ruff verdes.
Estas evidencias no reemplazan el resultado de CI sobre el SHA final.

El siguiente gate Python de CI pasó 1761 pruebas, con ocho skips y una falla del downgrade offline:
la fixture recreaba permisos y se detenía en 0085 antes de llegar a la guarda 0067. El replay ahora
conserva una variante `head` y otra `0077`; ambas comprueban snapshot, concurrencia y revocación.
La histórica exige mensaje 0067, inbox conservado y revisión 0077 tras rollback. El primer intento
desde 0082 pasó los dos casos actuales, pero encontró la frontera autocommit del índice 0079;
su XML de 1 falla/2 verdes se conserva. La variante definitiva 0077 pasó en 26.01 s. Ruff,
trazabilidad (9 verdes) y revisión independiente focal sin bloqueantes; no cambios a migraciones,
guardas ni skips. CI debe confirmar el último SHA antes de integrar.

Frontend CI aprobó en `57313f1`: semántica, builds y E2E Admin/POS, conciliación, gastos, gateway,
catálogo, sucursales, fiscal, asistente y shells offline. La barra superior ya no se contrae en
móvil; el recorrido completo y la inspección visual local verificaron acceso al asistente.

Preguntas operativas del ajuste offline: ¿se instaló el bundle esperado? Comprobar readiness e
identidad del bundle en el estado local. ¿Por qué se rechazó la instalación? Conservar el código
`offline_bundle_catalog_invalid` y la revisión del esquema, sin registrar payloads ni credenciales.

## Preparación del redeploy del primer paquete

El esquema pasa de `0082` a `0086_fiscal_emitters` mediante cuatro revisiones aditivas. Los
Dockerfiles ejecutan uvicorn, no Alembic. Respaldar PostgreSQL y aplicar la cadena de migraciones
con el código publicado antes de habilitar las nuevas rutas (`python -m alembic -c alembic.ini
upgrade head` desde `apps/api`, usando la conexión del entorno correspondiente). Los downgrades
que eliminarían historia/configuraciones/contextos se bloquean; no forzar su eliminación.

La configuración fiscal nueva necesita un keyring explícito:
`RESTAURANTOS_FISCAL_ENCRYPTION_KEYS` (mapa de key-id a clave base64 de 32 bytes) y
`RESTAURANTOS_FISCAL_ACTIVE_ENCRYPTION_KEY_ID`. Retener las claves antiguas para leer versiones
históricas. Nunca usar la clave de sesión como sustituto ni incluir secretos en Git. Configurar
razón social/ambiente/credencial en la nueva pantalla; legacy no habilita un emisor nuevo.

Comprobar salud y recuperación de sesión/contexto de una sucursal; compras con entradas vacías y
replay; lector fiscal y configuración por razón social. Registrar el SHA desplegado. Canary,
migración, configuración y comportamiento productivos requieren su autorización operativa;
el push de Git por sí solo no prueba el redeploy.

## Segundo paquete: PR 69

La PR 69 integra el código revisado hasta `6acab5b`: preparación fiscal privada durable,
JSON decimal exacto, reconciliación del neto pagado, lectura fiscal histórica autorizada,
auditoría y rollback del replay de workspace, y registro compartido de concesiones offline.
Es un incremento del plan; `execution.json` conserva las tareas parciales y pendientes.

Las auditorías independientes de estos alcances están cerradas sin bloqueantes abiertos.
CI sobre `6acab5b` (run `38496167613`) terminó con 1892 pruebas verdes, ocho skips y dos fallos;
el gate Python falló:
la prueba de downgrade fiscal esperaba alcanzar 0087 desde head, pero 0088 protegió primero
su evidencia offline. Se conservan las carreras en head y se añade un caso aislado 0087 que
exige su rechazo exacto y conservación de las cuatro tablas fiscales. No se cambian migraciones,
guardas ni skips; el verificador obliga a ejecutar el caso nuevo. El SHA posterior necesita
confirmación de CI antes del merge. Esta guía distingue la evidencia anterior de ese resultado.

Corrección local: seis pruebas PG verdes (239.09 s) y repetición final de los dos casos head
con conservación ampliada de seis tablas (97.13 s). Arquitectura/trazabilidad/verificador:
32 verdes; scanner, Ruff y diff-check verdes. Revisión independiente focal sin hallazgos;
se conserva el resultado rojo original de CI. No cambia runtime de la versión revisada.

CI `559ede8` (run `38499379049`) aprobó 1895 pruebas, con ocho skips/siete warnings,
el gate de los once módulos PostgreSQL y mypy81. El run falló por E501 de una línea de
101 caracteres en `models.py` y por timeout de foco del modal de catálogo en frontend.
La línea se dividió con AST idéntico y Ruff completo/mypy81 locales verdes. La prueba
de navegador existente pasó localmente en escritorio/móvil sin cambiar UI ni su aserción.
Se conserva el fallo original; el SHA siguiente requiere CI final antes del merge.

### Esquema del segundo paquete

El head del segundo paquete es `0088_offline_authorization`. Si ya se aplicó el primer paquete
hasta 0086, faltan las revisiones aditivas `0087_fiscal_commands` y
`0088_offline_authorization`; si la base sigue en 0082, Alembic recorre toda la cadena.
Los contenedores no ejecutan estas migraciones al iniciar. Respaldar PostgreSQL y aplicar
`python -m alembic -c alembic.ini upgrade head` desde `apps/api`, con el código y la conexión
del entorno correspondiente. Verificar `alembic current` antes de servir rutas del nuevo esquema.
No forzar downgrades: 0087 bloquea eliminación de intención fiscal existente y 0088 bloquea
eliminación de evidencia de autoridad offline.

### Límites operativos para el redeploy

0088 deja las organizaciones existentes en `unprepared`, sin inventar fechas de cutover,
versiones de concesiones históricas ni readiness. Con V2, una transición de sucursal sin
preflight válido devuelve `branch_offline_preflight_required`; una concesión incompatible
vigente devuelve `branch_switch_offline_grant`. La revocación sólo en central no elimina
el bloqueo del TTL del token desconectado. No cambiar manualmente el estado a
`clean_install`: ese estado en las pruebas corresponde a una organización sintética recién
creada. El mecanismo de adopción controlada, la versión firmada y el registro de comandos
inciertos siguen pendientes; esta publicación no habilita movilidad de organizaciones existentes.

La preparación fiscal conserva `dispatch_ready=false`, sin ruta pública, worker ni envío al
PAC. No acredita el cierre de F03/F04, impuestos/conceptos ni recuperación de emisión externa.
La configuración cifrada continúa requiriendo el keyring explícito del primer paquete.
Comprobar salud, recuperación de sesión y lectura fiscal permitida; no emitir CFDI para
validar este incremento privado. Conservar el SHA desplegado y los códigos de rechazo.
El redeploy, las migraciones y la configuración productivos quedan a cargo del usuario.

## Cierre Git del segundo paquete

PR 69 integrada en `main` como `c81193d`; su árbol coincide exactamente con el SHA probado
`3685598`. CI [38501465928](https://github.com/mangoex/kiwi/actions/runs/38501465928)
terminó en success: 1895 pruebas verdes, ocho skips existentes y siete warnings en 1444.02 s.
El verificador confirmó 67 casos ejecutados entre los once módulos PostgreSQL obligatorios;
mypy81, Ruff, frontend completo, Docker, políticas y dependencias aprobaron. El run final
no necesitó reprise de frontend; los fallos anteriores permanecen arriba y en TDD.

Este cierre actualiza sólo la guía y la referencia de evidencia en `execution.json` (R0),
sin cambiar runtime ni el estado de las 31 tareas. No sustituye los límites del segundo
paquete: esquema 0088 requerido, organizaciones existentes unprepared, adopción offline
y cierre fiscal aún pendientes. CI acredita el código integrado; producción no fue modificada.

## Publicación de especificación W04 previa al incremento de código

La rama `codex/offline-authority-version` publica el contrato previsto de versión firmada y
recuperación de acuse mínimo: PRD-FR-185/267, SDD §58.3, BDD-SC-639 y TDD-TC-354. El diseño
distingue nueva ejecución de la lectura de un acuse confirmado, exige evidencia de autoridad sin
inferir versiones históricas y conserva el orden gobernanza → actor → dominio.

Este diff es documental: no contiene código, pruebas de runtime ni migraciones nuevas. Los
formatos publicados siguen siendo caja v2 y pedidos v3; caja v3/pedidos v4 y sus gates canónicos
siguen pendientes. La matriz conserva Scaffold y `execution.json` mantiene W04 parcial y las
31 tareas. La evidencia CI anterior corresponde al código de PR 69, no acredita el contrato nuevo.
El redeploy conserva el esquema 0088 y los límites del segundo paquete descritos arriba.

Verificación documental local: 16 pruebas de trazabilidad/scaffold verdes y nueve de
trazabilidad repetidas tras enlazar PRD-FR-185 con BDD-SC-639/TDD-TC-354. Scanner de política
y `git diff --check` verdes. La revisión independiente detectó ese enlace faltante y se corrigió
sin cambiar estado de implementación. No se ejecutó una suite de runtime ni CI nuevo para este
diff documental; el código coincide con el publicado y probado en PR 69.

## Incremento W04: versión firmada y reconciliación

Caja v3/pedidos v4 transportan `authorization_version` firmado; API y gateway mantienen formatos
legacy estrictos. La emisión nueva se activa mediante
`RESTAURANTOS_SIGNED_OFFLINE_AUTHORITY_ENABLED=true`, apagada por defecto, y exige esquema 0088.
Actualizar primero los gateways verificadores compatibles y luego habilitar el emisor dentro de
una autorización de configuración productiva. Este paquete no activa esa configuración.

El fence central se aplica también a concesiones legacy con versión registrada conocida: actor,
hash/bindings y versión actual se comprueban antes del efecto. Ausencia, NULL histórico, revocación
o versión obsoleta generan rechazo sin inferir autoridad. Un acuse mínimo exacto ya confirmado
se recupera sin renovar permiso humano; pedidos exige transporte técnico vigente propio para
recuperar tras cambio de época/clave. No se ejecuta otra vez dinero, pedidos ni inventario.

SQL y limpieza fallidos devuelven un error redactado HTTP 503 y conservan la misma intención para
reintento. Si se perdió el acuse tras un commit real, se recupera la historia persistida; no se
declara ausencia de efectos ni se genera una compensación. La evidencia y los intentos originales
se concentran en TDD-TC-354. Auditoría independiente cerró dos P2 reproducidos y corregidos,
con refutaciones de bindings/checkpoint, rollback/invalidate y pérdida de acuse tras commit real.

Verificación local: 110 pruebas dirigidas verdes, cuatro carreras PostgreSQL con Lock/advisory
observado, cuatro fallos SQL/rollback probados en SQLite persistente y HTTP real redactado/retry.
Ruff completo de API/tests y gateway, mypy81 y 36 pruebas de arquitectura verdes. CI del SHA final
permanece pendiente; los batches anteriores no lo sustituyen. No hay nueva migración respecto
a 0088, ni cambio de UI que requiera QA visual de este incremento.
Gateway focal: mypy de cuatro módulos verde en Linux; CI lo incorpora junto con lint del gateway.
En Windows, cuatro diagnósticos de atributos POSIX en helpers sin cambios se reprodujeron también
en `main` bc55e2b; no se silencian ni se presentan como un gate Windows verde.

W04 continúa parcial: faltan adopción controlada y registro completo de comandos inciertos.
`execution.json` conserva las 31 tareas y decisiones; no habilita movilidad de organizaciones
existentes `unprepared`, emisión productiva fiscal, canary, migraciones ni despliegue.

### Corrección del primer CI de W04

Run [38514602872](https://github.com/mangoex/kiwi/actions/runs/38514602872), SHA `f6f79ed`:
1954 pruebas verdes y dos fallos de expectativa en replay PostgreSQL, ocho skips existentes y
siete warnings. Las variantes actual/histórica esperaban denegar un acuse ya confirmado tras
desactivar al actor. Se ajustan al contrato aprobado y comprueban separadamente rechazo de un
comando firmado nuevo, recuperación exacta del conflicto y conservación de efectos/historia.
No cambia runtime, migraciones ni skips. El gate obligatorio de once módulos PG confirmó 71 casos;
frontend, Docker, políticas y dependencias pasaron. CI del SHA corregido queda pendiente.
Corrección local: módulo PostgreSQL completo con tres casos verdes en 138.76 s, un warning
existente; Ruff y nueve pruebas de trazabilidad verdes. Revisión independiente focal sin hallazgos.

## Incremento W04 en revisión: preparación controlada

`codex/offline-authority-adoption` agrega el recibo aditivo 0089 y un comando privado de operador
para preparar una organización existente. Requiere autoridad organizacional protegida, evidencia
externamente verificada de retiro de emisores sin registro y confirmación explícita. El servidor
inicia dos horas de drenado; replay recupera el mismo acuse. Importa identidad legacy con versión
NULL y deja el origen intacto; no copia tokens ni convierte la importación en permiso.
Una selección de organización `draining` exige el recibo consistente; cambiar sólo el estado o
las fechas del rollout no reemplaza el recibo. No existe transición a `clean_install` en este comando.

Local: 41 pruebas dirigidas y cinco negativas adicionales; dos carreras PG con downgrade 0089 y
tres tablas conservadas, dos regresiones fiscales head con siete tablas conservadas; mypy83,
Ruff y arquitectura/trazabilidad verdes. Auditoría independiente cerrada, con tres refutaciones
originales conservadas y corregidas. TDD-TC-355 concentra los tiempos y límites exactos.
CI/publicación de este SHA quedan pendientes; `main` publicado arriba sigue siendo c00d483/0088.

La ejecución productiva del operador, migración 0089 y flags necesitan autorización separada.
Este incremento no activa movilidad ni emisión firmada; registro de comandos inciertos y restante
adopción/rollback siguen pendientes. `execution.json` mantiene las 31 tareas y sus decisiones.

## Cierre Git de la preparación controlada: PR 71

PR 71 integrada en `main` como `51a0ea288709301c7fa55e9c07130e1888b7a2ab`.
El árbol completo del merge coincide con el SHA probado
`e09c18e69790086c58f10275ed3723e1de1f0296`; el checkout principal quedó sincronizado.
CI [38525175265](https://github.com/mangoex/kiwi/actions/runs/38525175265)
terminó en success: 1985 pruebas aprobadas, ocho skips existentes y siete warnings en 1529.45 s.
El verificador confirmó 73 casos aprobados entre los once módulos PostgreSQL obligatorios;
mypy83 API/mypy4 gateway, Ruff, frontend, Docker, políticas y dependencias aprobaron.
La auditoría independiente del incremento quedó sin hallazgos bloqueantes abiertos.

El head de esquema publicado es `0089_offline_cutovers`. Desde 0088 falta esa revisión
aditiva; desde una base anterior Alembic recorre la cadena pendiente. Los contenedores no
ejecutan Alembic al arrancar. Para el redeploy, respaldar PostgreSQL, aplicar
`python -m alembic -c alembic.ini upgrade head` desde `apps/api` con la conexión del entorno
correspondiente y comprobar `alembic current`. La migración crea el recibo vacío y no prepara
organizaciones. El downgrade 0089 se bloquea cuando existe evidencia de cutover; no forzarlo.

Conservar `RESTAURANTOS_SIGNED_OFFLINE_AUTHORITY_ENABLED` apagado salvo activación operativa
autorizada. La ejecución del operador de adopción conserva su autorización separada y exige
evidencia real del retiro de emisores sin registro. La publicación no acredita esa retirada ni
habilita por sí sola movilidad de organizaciones existentes. Comprobar salud, recuperación de
sesión y lecturas permitidas; conservar el SHA desplegado y los códigos de rechazo.

Este cierre es R0: actualiza únicamente PUBLICATION y la evidencia de `execution.json`, sin
cambiar runtime, las 31 tareas ni sus estados parciales. El registro de comandos inciertos y
la adopción/rollback restante continúan pendientes. No se ejecutó redeploy, migración,
configuración, CLI de adopción ni canary productivo; esas acciones quedan a cargo del usuario.

## Evidencia local previa del incremento W04: registro central de comandos

`codex/uncertain-command-registry` agrega 0090 y el protocolo previo al envío para pedido,
pago y movimiento de caja centrales. Con V2 estas tres rutas exigen intención registrada;
applied se confirma junto con el dominio y prepared/applied bloquean un contexto nuevo.
La recuperación autenticada propia entrega sólo identidad/estado/recurso mínimo, sin renovar
capacidad financiera. NoEffect se prueba bajo el fence, sin borrar historia ni admitir envío tardío.
El panel POS está disponible también ante error de contexto o pérdida de permiso POS.
El cliente conserva pendientes y evita fallback al gateway después de registrar intención.

Local: 60 regresiones, ocho casos PostgreSQL con seis carreras observadas y dos downgrades;
cuatro regresiones fiscales/cutover de historia en head0090. Auditoría independiente cerrada
con un P1 y tres P2 corregidos. TDD-TC-354 conserva intentos originales, fases y límites;
scanner/ratchet/diff locales verdes. En esa fase CI/publicación estaban pendientes y `main`
seguía en 47a7f79/0089; el cierre siguiente registra la validación y publicación finales.

La nueva revisión crea tabla/índice vacíos; no declara adopción ni fabrica ausencia histórica.
0090 no permite downgrade con ninguna intención, incluso terminal. Aplicación productiva de
migración/configuración/despliegue conserva autorización separada. Apertura/cierre de caja,
compensaciones, otros comandos, journals restantes y reconciliación/outbox offline siguen
pendientes. El manifiesto conserva el plan completo de 31 tareas y W04 parcial.

## Cierre Git/CI del registro central (PR 72)

Commits `4b40483` y `f58a001` publicados en la PR 72; merge `758a1b1` sincronizado en el
checkout principal. Comparación completa con el head probado: sin diferencias.
El CI inicial de 4b40483 aprobó 2012 pruebas, ocho skips existentes y siete warnings en
1574.34 s; los cinco jobs aprobaron. Antes de merge se corrigió incompatibilidad del registro
con claves de caja 1–180, normalización de sucursal/tipo y NBSP del SDK. Pedidos/pagos conservan
12–160 y cuerpo/hash originales. RED, pruebas dirigidas y auditoría independiente están en
TDD-TC-354; no hay bloqueadores abiertos en este incremento.

CI final f58a001: Python 2022 aprobadas, ocho skips existentes y siete warnings en 1608.37 s;
82 casos entre doce módulos PostgreSQL, incluidos nueve del registro central. El primer job
frontend falló por timeout del botón Crear grupo deshabilitado en catálogo. La prueba original
pasó localmente en 1440/390 tanto con desarrollo como con bundles de producción, sin cambios
de runtime/prueba. Tras terminar Python se repitió sólo frontend sobre el mismo SHA; pasó el
recorrido original de catálogo y todos sus gates, incluida recuperación de intención en ambos
tamaños sin envío financiero ni adquisición de contexto. CI terminó en success, intento 2;
no se agregaron skips ni se relajaron verificaciones.

El cierre posterior R0 modifica sólo esta guía y evidencia de `execution.json`: conserva runtime,
las 31 tareas, sus estados parciales y D02/D03/D04. No se ejecutó redeploy, migración, configuración,
CLI ni canary productivos. Los pasos de redeploy superiores quedan a cargo del usuario.
