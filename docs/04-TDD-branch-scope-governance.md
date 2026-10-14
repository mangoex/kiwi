# TDD - Alcance corporativo y contexto seguro de sucursal

## TDD-TS-138 BRANCH-SCOPE-001

Estrategia RED -> GREEN:

1. agregar primero pruebas de dominio/API que fallen porque hoy Admin deriva una sucursal concreta,
   Supervisor no tiene movilidad gobernada y no existe el comando de reasignación;
2. implementar el cambio mínimo por incremento, sin debilitar guardas existentes;
3. ejecutar pruebas focales SQLite/TypeScript durante desarrollo;
4. validar locks, idempotencia y migraciones en PostgreSQL aislado;
5. validar gateway SQLite, E2E de dos sucursales, QA visual y suite completa aplicable una sola vez
   en CI antes de integrar.

Fixtures reproducibles: una organización, sucursales A/B/C activas, una inactiva, productos/precios
corporativos y locales, Cajero, Cajero jefe, Líder, Supervisor, Administrador y Dueño; turno
abierto/cerrado, comando incierto, lease offline vigente/expirada, grant legacy y dos pestañas/sesiones
concurrentes. Ningún fixture usa datos productivos ni secretos.

## TDD-TC-348 Scope corporativo explícito

Pruebas puras y API verifican la unión `organization|branch`: Admin inicia en organización; las rutas
global-only no muestran selector ni etiqueta redundante y las rutas con excepción muestran el alcance; payload
ausente, branch en organización, branch faltante, sucursal ajena o módulo sin excepción fallan sin
escritura; nunca existe fallback a `active_branch` o primera sucursal.

## TDD-TC-349 Confirmación y señal visual de alcance

Prueba semántica Admin y Playwright verifican ausencia del control en global-only y, donde exista
excepción local, selector **Todas las sucursales**, diálogo con nombre,
Cancelar/Escape, foco contenido, banner **Sólo {Sucursal}**, scope de la mutación, separación mínima y
ausencia de overflow a 1440x900 y 1024x768.

## TDD-TC-350 Herencia y resolución efectiva por módulo

SQLite y PostgreSQL verifican que una sucursal existente o nueva sin excepción hereda configuración
corporativa; proveedor, receta, disponibilidad, presentación y precio resuelven su excepción válida y
vuelven a heredar al retirarla. Precio local solapado, moneda distinta o dos versiones efectivas falla
cerrado. Replay idéntico recupera el resultado y misma key con scope/payload distinto falla. Ninguna
operación clona identidad ni reescribe snapshots históricos. Confirmar una compra de presentación en A
crea historial/proyección de A con `Decimal` y no altera costo, último precio ni preferencia efectiva de
B; una sucursal nueva usa el baseline corporativo hasta tener historia propia.

## TDD-TC-351 Matriz de perfiles y sesión canónica

API prueba que Cajero, Cajero jefe y Líder tienen una sucursal, `can_select_branch=false` y rechazo por URL,
storage o payload; Supervisor, Administrador y Dueño reciben `can_select_branch=true` sólo mediante
permiso/grant persistido. Cero o múltiples asignaciones de un perfil fijo fallan
`operational_branch_scope_ambiguous`. El nombre de rol alterado no cambia autoridad y ninguna cuenta
cruza organización. Supervisor/Administrador inician en su base válida; Dueño sin preferencia y con
varias sucursales queda en selección obligatoria, nunca en la primera. Crear/editar roles no puede fabricar un authority grant, y los roles con grant
activo no pueden cambiar scope, borrarse o perderlo por una ruta administrativa ordinaria.
`test_branch_authority_remediation.py` prueba ambas clases de grant, incluso rol no asignado;
compara versiones y assignments en rechazo. Reemplazo efectivo de permisos incrementa sólo los
usuarios del rol; añadir una asignación incrementa una vez y su replay no incrementa; suspensión
incrementa en el mismo commit. Nombre/permisos idénticos no introducen cambios de autoridad.
La regresión crossorg exige rechazo opaco y cero assignment/versión; esquema legacy exige lectura
v1 compatible y error de migración previo al incremento. PostgreSQL agrega
`test_branch_authority_postgres.py` con barrera y comprobación de wait_event advisory: una nueva
asignación no cruza la enumeración de un rol cuyos permisos están cambiando.

## TDD-TC-352 Cambio seguro e idempotente de sucursal

API y frontend prueban `POST /auth/branch-selections`: destino válido, no autorizado/inactivo,
versión obsoleta, replay idéntico, key con payload distinto, turno OPEN/CLOSING, comando incierto,
grant offline y reconciliación pendiente. Fallo conserva contexto anterior; éxito cancela respuestas
tardías, recalcula permisos y aísla carrito, borrador, caja, dispositivo y consultas. Cambiar
asignación, estado, permiso o grant incrementa la versión y vuelve obsoleto un intento previo. Cada
operación scoped exige `X-Branch-Context` vigente: branch distinto en payload, token supersedido,
segunda pestaña y dos selecciones concurrentes no pueden saltar blockers ni dejar dos contextos
activos. `GET /auth/session?branch_id=...` recibe `branch_selection_requires_command`. Antes de
devolver un replay guardado se revalidan actor, permiso, workspace y versión; revocar autoridad entre
intentos impide recuperar el resultado como nueva autorización. Una respuesta A→B perdida se recupera
con el mismo actor/key sólo si B continúa como contexto activo del comando; el replay rota un secreto
nuevo sin exigir A. Tras recarga, `POST /auth/branch-context-reissues` recupera el contexto vigente
sin secreto persistido; contexto/versión/permiso cambiados deniegan y nunca reviven B.
Cada replay de selección registra su rotación con versiones y lineage del comando, sin secreto ni
idempotency key. La regresión inserta auditoría y luego inyecta una excepción en selección,
reemisión y ambos replays; exige rollback propiedad del servicio y reutiliza la misma sesión para
commit sin rollback manual, comparando contextos, commands y auditoría exactos. PostgreSQL fuerza
dos replays de selección concurrentes y verifica una auditoría por versión, un solo contexto y
rechazo del secreto anterior.
Dos reemisiones concurrentes fuerzan respuestas v3→v2: el frontend aplica fencing por context ID y
`branch_workspace_secret_version`, conserva v3, descarta v2 y no emite ninguna operación con el
secreto tardío ya inválido.

`test_branch_workspace_memory.mjs` ejecuta el almacén de secretos en memoria con respuestas
v3→v2, cambio de context ID, credencial A→B, ticket previo, hidratación GET sin secreto y rotación
externa. Exige cero escrituras persistentes; un contexto/versión no coincidente deja de habilitar
el header. El transporte central usa sólo el secreto confirmado para la credencial actual y
descarta el header provisto por formularios; el transporte gateway conserva su grant independiente.
El enriquecimiento central opcional de apariencia/capacidades usa exclusivamente GET de sesión:
401, timeout o desconexión devuelven ausencia de enriquecimiento y no revocan el grant firmado
del gateway ni dejan el proveedor en carga perpetua. Las operaciones centrales conservan el manejo
normal de 401 y la administración continúa requiriendo autenticación central vigente.

`test_branch_workspace_provider.mjs` ejecuta los proveedores reales: gateway 200/central opcional
401 publica sesión local, 409 por turno conserva A/captura, callback durante selección conserva
`validating`, 503 bloquea y retiene journal; Admin de catálogo sin `pos.operate` no solicita reissue.
`test_branch_workspace_recovery.mjs` recorre en navegador construido la selección obligatoria de
Dueño sin base, efecto confirmado con respuesta perdida, recarga/replay exacto y rotación posterior;
comprueba headers actuales, cero secreto persistido y una búsqueda capturada intacta tras 409.

`test_branch_workspace_authority.py` verifica la primera emisión sin secreto en GET, persistencia
tras seleccionar, rotación monotónica con replay, rechazo del contexto anterior, payload cruzado,
versión modificada y replay de una selección supersedida. El índice parcial se intenta refutar
insertando un segundo contexto operativo del mismo actor. La prueba negativa inyecta fallo tardío
de auditoría y exige que el rollback conserve el contexto anterior y no registre el comando.
La regresión API de apertura recorre ambos aliases `/cash/shifts/open` y `/cash-shifts/open`:
abre A con contexto A, comprueba selección B bloqueada y rechaza apertura directa B con el mismo
contexto, sin turno B. Apertura sin contexto o con secreto supersedido falla antes del ledger.

`test_branch_workspace_route_guard.py` recorre humanos de KDS, impresión y sincronización:
falta de contexto, branch cruzado y secreto supersedido rechazan antes de consultar el recurso;
la omisión de branch en query resuelve el workspace persistido después de seleccionar B, no su base A.
Las credenciales de dispositivo mantienen su alcance persistido independiente.
El mismo recorrido incluye transición KDS y reintento de impresión; observa cero llamadas de
dominio ante rechazo. FK activas prueban auditabilidad de actor/sucursal inexistentes sin secretos.
Cambiar permisos invalida el contexto anterior y un contexto reemitido no restaura la capacidad
retirada. La carrera PostgreSQL de `OperationalRouteGuard` observa wait_event de selección
esperando al actor y verifica que el recurso conserva A hasta terminar su transacción.

Evidencia del incremento de auditoría de replay: `workspace-replay-audit-red.xml` conserva cinco
fallas esperadas (cero auditorías en replay y ausencia de rollback propio en cuatro caminos).
`workspace-replay-audit-current.xml`: 41 verdes de autoridad, selección y rutas; la prueba previa de
fallo de auditoría ahora también confirma sin rollback manual y pasó por separado
(`workspace-replay-audit-existing-rollback.xml`, 1 verde).
`workspace-replay-audit-postgres.xml`: 1 verde de dos replays concurrentes, versiones 2/3 con
auditorías ligadas al mismo comando, un contexto y rechazo de v2. Mypy de un archivo, Ruff, nueve
pruebas de trazabilidad, scanner, ratchet de diff y whitespace verdes. Auditoría Sol independiente
cerrada sin bloqueantes: 30 pruebas canónicas y cuatro refutaciones propias (20 fallos inyectados,
lineage/privacidad, denegación confirmada y matriz de autoridad) verdes. El primer intento de su
matriz exigía incorrectamente ausencia de toda auditoría de denegación; su reporte conserva la
corrección y la repetición verde, sin atribuir ese error al runtime. Reporte:
`output/audit-remediation/sol-workspace-replay/AUDIT.md`. CI del SHA definitivo pendiente;
esta evidencia no completa W02/W04.

Afirmación: cada replay exitoso conserva causalidad y privacidad de su rotación, y un error previo
al commit no deja una operación parcial. Refutación: dos replays, fallo después del INSERT de
auditoría y commit posterior en la misma sesión; resultado verde SQLite/PostgreSQL focal.
Riesgo residual: pérdida de confirmación de un commit requiere recuperar con la misma key; rollback
no deshace un commit que el servidor ya confirmó. La auditoría no prueba salud del dispositivo ni
los bloqueadores offline/comandos inciertos todavía pendientes.

Preguntas operativas: ¿por qué cambió la versión del secreto? Consultar el evento por contexto,
versiones y `selection_command_id`, sin secretos ni keys. ¿Se confirmó una operación cuya respuesta
se perdió? Recuperar por el mismo actor/key y comprobar contexto vigente/lineage del command log;
un error o ausencia de respuesta no autoriza otra selección ni prueba ausencia de commit.

## TDD-TC-353 Reasignación transaccional y auditable

Dominio/API prueban permiso en actor, target Cajero/Cajero jefe, origen/destino autorizados, versión,
motivo, lock y actualización atómica de todas las asignaciones branch-scoped. Casos negativos: actor
sin permiso, target móvil, destino ajeno/inactivo, asignaciones ambiguas, turno/grant/comando activo y
fallo inyectado después del primer update. Se verifica cero parcialidad, incremento único de versión,
auditoría redactada, replay e inmutabilidad de historia. Reasignación y emisión de lease concurrentes
usan el mismo lock canónico: sólo una confirma y la otra reevalúa el nuevo estado.

## TDD-TC-354 Offline y autorización obsoleta

Cobertura prevista, pendiente de implementación y ejecución canónica: el contrato de versión
firmado cubre caja v3/pedidos v4 y su compatibilidad legacy estricta. No se presenta como evidencia
verde del runtime publicado.
Vectores API/gateway rechazan bool, float, string, 0, negativo, int32+1, claim ausente y mezcla de
header/payload. Emisores reales registran la misma versión firmada bajo lock; bundle/semilla
operacional con versión distinta impide emisión/aceptación nueva, sin inferir un valor histórico.
Reconciliación prueba claim→hash/registro→usuario, ausencia/NULL/revocación y rechazo sin efecto
financiero. Carreras PG de revocación contra comandos de caja/pedidos observan el lock real y
conservan el fence hasta commit; no agregan actor/gobernanza después de sucursal/agregado.
El replay conserva acuse mínimo pese a versión/permiso humano retirados; caja no lee claves
retiradas. API pedidos exige dispositivo autenticado propio, hash/intención exactos y ningún
resultado privado para recuperar tras cambio de época o clave; el caller interno sin ese
transporte sigue verificando la firma. Firma alterada en un comando nuevo y dispositivo ajeno
nunca aprovechan el camino de lectura de acuse. Los RED, gates y límites se registran al ejecutarse.

Gateway SQLite verifica que el bundle A rechaza branch B, que no existe selector offline y que una
lease registrada vigente bloquea selección/reasignación. PostgreSQL fuerza carreras de emisión contra
ambos comandos bajo el lock común. Tras expirar/revocar y reasignar, el `authorization_version`
anterior no obtiene nuevos grants ni confirma comandos centrales; los comandos previamente
confirmados conservan resultado e historia. La activación se bloquea mientras sobreviva un grant
legacy no importado; el test acepta únicamente importación verificable, drenado por TTL o rotación de
época/clave que lo invalide.
El preflight sin preparar, ausente o con drenado pendiente bloquea selección. Un fixture de
instalación limpia declara su procedencia antes de toda emisión; no parchea la guarda. Registrar
caja/pedidos persiste sólo hash, bindings y versión bajo lock compartido, con auditoría atómica.
Lease revocada sin acuse continúa bloqueando hasta TTL; lease de otra persona no bloquea al actor.
Un grant legacy retenido con versión desconocida nunca recibe la versión actual por inferencia.
La migración conserva tokens/historia originales, parte de `unprepared` y bloquea downgrade con
evidencia de emisión o adopción. PostgreSQL fuerza grant contra selección y confirma que el perdedor
revalida el estado; SQLite no acredita esos locks.

Evidencia incremental W04: registro RED 4 fallas y pedidos RED 1 (`offline-authority-registry-red.xml`,
`offline-authority-orders-red.xml`); primer GREEN 4 y segundo 5 conservados. `offline-authority-directed.xml`
pasó 17 de registro/límites/migración y contratos legacy reales de caja/pedidos. Paridad de organización
ajena: 2 verdes (`offline-authority-foreign-organization.xml`). `offline-authority-postgres.xml` pasó
3 casos: emisión contra selección en ambas direcciones con `Lock/advisory` observado y auditoría FK
compatible mientras el actor seguía bloqueado. `offline-authority-workspace-postgres.xml`: 5 verdes
de carreras/replays existentes tras ajustar el modo del lock. Arquitectura: 32 verdes, incluidas
negativas del verificador que ahora exige 11 módulos PG, agregando `offline_authorization` sin
eliminar ninguno. Es evidencia focal; no prueba ejecución local de los 11 módulos.
`offline-authority-cash-sync-first.xml` conserva 12 verdes y una falla por mock cuya firma no
aceptaba el nuevo argumento de contexto; se amplió estrictamente y se comprueba que el transporte
legacy sin header entregue `None`, sin cambiar guardas. `offline-authority-cash-sync-head.xml`
pasó 25 de sync de caja y capacidad/cadena Alembic SQLite. Ruff y mypy de seis archivos verdes;
scanner de cambios/archivos nuevos, ratchet y whitespace verdes. Dos fixtures modificados y el
nuevo fixture de migración se registran por procedencia/ruta/hash LF exactos; no cambian reglas
del scanner ni exclusiones de pruebas. CI del SHA definitivo del incremento pendiente.
Revisión estática identificó timestamp de pedidos capturado antes de locks; se corrigió a reloj
posterior a actor/gateway/dispositivo. `offline-authority-clock-current.xml`: 3 verdes, reloj t0→t3
con recurso expirando en t2; prohíbe leer signer y deja cero grants para gateway, bundle y device.
Sol ejecutó los mismos tres y dos refutaciones propias de iat/registro/dedup con reloj posterior;
sin RED histórico fabricado ni repetición PG innecesaria. Mypy de dos módulos y Ruff verdes tras
este ajuste. Esto no acredita clocks o logs de infraestructura productiva.
`offline-authority-clock-positive.xml`: 6 verdes de registro y recorrido HTTP legacy tras usar
el reloj fresco; Sol agregó 2 positivas propias de timestamp y deduplicación.

Sol independiente cerró un bloqueante de exposición SQL/token en commit: su RED y repetición
original GREEN se conservan en `output/audit-remediation/sol-offline-authority/AUDIT.md`. Registro,
permisos mínimos, depósito sin retiro, TTL, deduplicación, denegación FK nullable y migración se
refutaron con 22 casos propios, 6 de migración y 2 adicionales de organización ajena verdes. El
reporte conserva sus errores de fixture y el batch que cargó código durante una edición; no se
presenta como una corrida completa verde. PG recibido se distingue de sus ejecuciones propias.

Afirmación: grant y selección no confirman autoridad incompatible, y un fallo previo al commit no
publica token ni persistencia parcial. Refutación: ambos ganadores bajo barrera/espera PG observada,
insert de audit seguido de error y commit con marcador sintético sensible; resultado verde. Riesgo
residual: no hay revocación inmediata del dispositivo desconectado, ni prueba de commit realmente
confirmado con respuesta perdida. Claim firmado de versión, reconciliación, adopción controlada y
registro de comandos inciertos/reconciliación local aún pendientes; W04 permanece parcial.

Preguntas operativas: ¿qué concesión impide seleccionar y hasta cuándo? Estado/timestamps del
preflight y leases incompatibles por actor responden sin mostrar token. ¿Cada emisión tiene
evidencia y audit confirmados? Correlacionar lease ID/evento/source grant. ¿Se deniega por contexto
obsoleto? Agrupar `authorization.denied` por permission `offline.grant` y reason. No usar secretos,
tokens ni IDs de actores como etiquetas de métricas.

## TDD-TC-355 Migración forward-only y compatibilidad

SQLite y PostgreSQL aislado prueban upgrade desde la head integrada, preflight de IDs/códigos/roles,
constraint ampliado de authority grants, defaults de `authorization_version`, índice de un workspace
activo, registro de leases, historial de presentación con branch, seeds exactos y ausencia de
asignaciones o copias de catálogo. `upgrade -> app rollback -> re-upgrade` conserva historia; un
downgrade con comandos o versiones locales se bloquea. El preflight impide activar movilidad con
grants legacy sin resolver. No se modifican `0035`, `0047` ni `0056`.

## TDD-TC-356 Concurrencia PostgreSQL y recorrido E2E

Dos transacciones que reasignan la misma versión producen un ganador y un `version_conflict`; dos
selecciones dejan un workspace activo; emitir lease contra selección/reasignación produce un solo
ganador; dos precios locales concurrentes no dejan vigencias solapadas. El E2E recorre dos sucursales
y los seis perfiles: selección permitida/denegada, bypass API, dos pestañas, reasignación, sesión
antigua, turno bloqueador, configuración global/local e historia intacta. El test de rollback inicia
con contexto no base, turno abierto y comando incierto: deshabilita nuevas transiciones, mantiene la
recuperación bajo estado `recovery_only`, permite sólo los comandos allowlist del estado ya existente
y rechaza nuevas ventas, pedidos, pagos, movimientos, aperturas, compras, recepciones, ajustes y
configuración. Sólo vuelve al contexto base después del drenado; si no drena, exige forward-fix. Se
exige evidencia PostgreSQL real; SQLite no acredita locks.
El verificador CI exige también las suites `test_branch_authority_postgres.py` y
`test_branch_workspace_postgres.py`: una suite no colectada o un caso skipped/ausente/fallido impide
aprobar el gate. `test_dependency_runtime.py` prueba la omisión y el skip de cada suite en negativo;
la presencia del job o el éxito de SQLite no sustituyen esta evidencia.

Gates focales previstos:

```bash
python -m pytest apps/api/tests/test_branch_scope_governance.py -q
python -m pytest apps/api/tests/integration/test_branch_scope_postgres.py -q
python -m pytest apps/edge-gateway/tests/test_branch_scope_offline.py -q
python -m pytest tests/architecture/test_branch_scope_governance.py -q
pnpm typecheck
pnpm --filter @restaurantos/admin-web build
pnpm --filter @restaurantos/pos-web build
pnpm exec playwright test tests/e2e/branch-scope-governance.spec.ts
python -m pytest tests/architecture/test_traceability.py -q
git diff --check
```

Los nombres representan objetivos de implementación; una prueba inexistente o no ejecutada se reporta
como pendiente, nunca como verde. Migración productiva, canary, despliegue y comportamiento real son
gates separados.
