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

Pruebas puras y API verifican la unión `organization|branch`: Admin inicia en organización; payload
ausente, branch en organización, branch faltante, sucursal ajena o módulo sin excepción fallan sin
escritura; nunca existe fallback a `active_branch` o primera sucursal.

## TDD-TC-349 Confirmación y señal visual de alcance

Prueba semántica Admin y Playwright verifican selector **Todas las sucursales**, diálogo con nombre,
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
Dos reemisiones concurrentes fuerzan respuestas v3→v2: el frontend aplica fencing por context ID y
`branch_workspace_secret_version`, conserva v3, descarta v2 y no emite ninguna operación con el
secreto tardío ya inválido.

## TDD-TC-353 Reasignación transaccional y auditable

Dominio/API prueban permiso en actor, target Cajero/Cajero jefe, origen/destino autorizados, versión,
motivo, lock y actualización atómica de todas las asignaciones branch-scoped. Casos negativos: actor
sin permiso, target móvil, destino ajeno/inactivo, asignaciones ambiguas, turno/grant/comando activo y
fallo inyectado después del primer update. Se verifica cero parcialidad, incremento único de versión,
auditoría redactada, replay e inmutabilidad de historia. Reasignación y emisión de lease concurrentes
usan el mismo lock canónico: sólo una confirma y la otra reevalúa el nuevo estado.

## TDD-TC-354 Offline y autorización obsoleta

Gateway SQLite verifica que el bundle A rechaza branch B, que no existe selector offline y que una
lease registrada vigente bloquea selección/reasignación. PostgreSQL fuerza carreras de emisión contra
ambos comandos bajo el lock común. Tras expirar/revocar y reasignar, el `authorization_version`
anterior no obtiene nuevos grants ni confirma comandos centrales; los comandos previamente
confirmados conservan resultado e historia. La activación se bloquea mientras sobreviva un grant
legacy no importado; el test acepta únicamente importación verificable, drenado por TTL o rotación de
época/clave que lo invalide.

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
