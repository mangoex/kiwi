# BRANCH-SCOPE-001 — plan de alcance corporativo y contexto seguro de sucursal

**Estado:** implementación incremental; selección POS online básica y provider Admin disponibles, alcance
corporativo extremo a extremo, excepciones locales y workspace R3 completo pendientes.
**Riesgo:** R3 — permisos, caja, offline, migraciones, contexto multi-sucursal e historia.
**Autoridad:** PRD-FR-005/007/008/018/019/094/215/266/267/268, PRD-NFR-006/007/022/024/027/031,
SDD §58 y ADR-040, BDD-FEAT-133, TDD-TS-138.
**Autorización vigente:** incremento frontend solicitado para corregir selectores y separación visual,
con pruebas locales. Migración, despliegue, configuración y datos productivos requieren autorización
separada conforme a GOV-REL-001.

### Avance incremental — 2026-10-10

- El provider Admin inicia en alcance de configuración `organization`; el selector, la confirmación y
  la señal visible existen en código, pero permanecen detrás de `VITE_BRANCH_SCOPE_V2_ENABLED` y no
  acreditan todavía propagación de scope por módulo.
- El filtro duplicado de sucursal del panel se retiró; el mes permanece como filtro propio.
- Mientras un módulo no tenga contrato local, el alcance sucursal bloquea la edición con
  `configuration_scope_unsupported` en vez de guardar globalmente por error.
- POS muestra el selector sólo cuando la sesión canónica confirma `scope.can_select_branch`, más de
  una sucursal autorizada, conectividad central y ausencia de bundle offline. Supervisor,
  Administrador y Dueño reciben `pos.branch.select` mediante la migración forward-only; los perfiles
  branch móviles requieren `organization_branch_workspaces` y conservan su sucursal base.
- `POST /auth/branch-selections` usa `Idempotency-Key`, versión de autorización, alcance persistido,
  auditoría y bloqueo por turno `OPEN|CLOSING`; el frontend conserva el mismo intento ante fallo
  incierto y desmonta el POS al confirmar otra sucursal.
- La prueba semántica y el recorrido sintético verifican Admin/POS a 1440x900 y 1024x768.
- Admin conserva su interacción de configuración local detrás de `VITE_BRANCH_SCOPE_V2_ENABLED`;
  la movilidad POS ya no depende de ese flag y se decide exclusivamente por la sesión canónica.

Este incremento elimina el GET legado para la transición visible, pero todavía no implementa token
opaco de workspace, reemisión/rotación, fencing obligatorio en todas las rutas, registro unificado de
leases, blockers de comandos inciertos/reconciliación, reasignación ni excepciones locales por
módulo. Por tanto BRANCH-SCOPE-001 continúa como `Scaffold` y no acredita TDD-TC-351/352 completos.

### Reconciliación de implementación — 2026-10-12

El diagnóstico del Admin publicado confirma que el bundle contiene el selector corporativo, pero lo
compila apagado. En rutas distintas del dashboard, la cabecera muestra `active_branch` —por ejemplo,
**Centro**— aunque el módulo pueda estar escribiendo configuración corporativa. No debe activarse el
selector existente de forma aislada: varios módulos todavía derivan `branch_id` de `active_branch` y
no transportan `ConfigurationScope` explícito hasta Python.

La autoridad documental no cambia: PRD-FR-266, SDD §58.1, BDD-SC-630..633/644 y TDD-TC-348..350/355
ya gobiernan este comportamiento. Esta reconciliación sólo corrige el plan y su orden de ejecución.
No activa cambios en PRD, SDD/ADR, BDD, TDD ni matriz hasta que cambie el contrato, la estrategia de
prueba o el estado de evidencia.

#### Clasificación obligatoria de superficies

| Clase | Superficies | Alcance inicial | Regla de escritura |
|---|---|---|---|
| Configuración corporativa heredable | identidad de insumos, proveedores, presentaciones, recetas, productos y precios | `organization` | scope discriminado explícito; nunca `active_branch` implícito |
| Excepción local | umbrales/almacén, términos de proveedor, condiciones de presentación, receta, disponibilidad y precio local | `branch` sólo tras confirmación | contrato local propio, versionado e idempotente; módulo sin contrato falla cerrado |
| Consulta corporativa | dashboard ejecutivo, conciliación consolidada, clientes y reportes autorizados | todas las sucursales | filtro opcional no cambia configuración ni POS |
| Operación de sucursal | pedidos, caja, compras, gastos, producción, conteos, merma, transferencias e impresión | `active_branch` concreta | no admite “todas”; reautoriza sucursal y conserva historia |

La cabecera debe nombrar el contexto correspondiente: **Vista de todas las sucursales** para consulta,
**Configuración para todas las sucursales** o **Sólo {Sucursal}** para configuración y **Operando en
{Sucursal}** para operación. No se reutiliza una etiqueta ambigua de sucursal para los tres casos.

#### Brechas verificadas que ordenan el siguiente incremento

| Brecha | Estado observado | Riesgo que debe cerrar |
|---|---|---|
| Build/rollout Admin | `VITE_BRANCH_SCOPE_V2_ENABLED` no se propaga en el Dockerfile y el bundle publicado queda apagado | una variable de runtime no puede corregir un valor Vite compilado; activación no observable |
| Productos | catálogo principal lee/escribe sin `branch_id`, pero cabecera y disponibilidad local usan `active_branch` | el usuario no distingue identidad corporativa de excepción local |
| Recetas | soporta `branch_id=NULL`, pero inicializa desde `resolveBranchId()` | contradice el default corporativo y puede iniciar en Centro |
| Insumos/proveedores/presentaciones | varias consultas y mutaciones construyen `branch_id` desde `resolveBranchId()` | mezcla identidad central, dato efectivo y operación local |
| Dashboard | el frontend omite `branch_id` para consolidado organizacional | una cuenta Dueño que siga mostrando Centro requiere verificar `/auth/session`, rol, grant y migración; el nombre del rol no acredita autoridad |
| Módulos operativos | usan `active_branch` de forma intencional | no deben convertirse a globales; sólo deben etiquetar y reautorizar claramente la sucursal |
| Verificación | prueba semántica cubre la cabecera, pero no la propagación de scope de cada mutación | el flag podría mostrar una UX correcta sobre escrituras ambiguas |

#### Incremento ejecutable propuesto: BS-ADMIN-001

Este incremento cierra primero PRD-FR-266 sin ampliar por accidente la autoridad de Pedidos/POS. La
movilidad durable, reasignación y offline de PRD-FR-267/268 continúan en BS-003..008 y BS-015..018.

1. **BS-A01 — inventario contractual y RED.** Registrar para cada endpoint de los seis módulos si la
   identidad es corporativa, qué excepciones locales existen y qué DTO de lectura/escritura las
   representa. Agregar RED que prohíba `resolveBranchId()`/`active_branch` como fallback de
   configuración y demuestre que hoy Recetas inicia en Centro y otros módulos no envían scope.
2. **BS-A02 — contrato compartido.** Exponer en `packages/contracts`/API client la unión
   `{kind:"organization", branch_id:null} | {kind:"branch", branch_id:UUID}`. Toda escritura de
   configuración la recibe explícitamente; combinación ausente/incompatible responde
   `configuration_scope_invalid` sin mutación. Lecturas efectivas distinguen `requested_scope`,
   `effective_source` y `source_branch_id` sin otorgar autoridad al cliente.
3. **BS-A03 — autoridad Python.** Centralizar validación y resolución efectiva por dominio. Verificar
   permiso corporativo para `organization`, permiso y sucursal autorizada para `branch`, y
   `configuration_scope_unsupported` cuando no exista excepción local. Controladores sólo validan la
   frontera; no contienen reglas de herencia.
4. **BS-A04 — migración módulo por módulo.** Ejecutar en este orden para reducir dependencia:
   Productos/disponibilidad → Recetas → Insumos/umbrales → Proveedores/términos →
   Presentaciones/condiciones e historial → Precios/versiones. Cada módulo queda GREEN antes de
   habilitar el siguiente; no se clonan identidades ni se recalculan snapshots históricos.
5. **BS-A05 — experiencia de alcance.** Conectar `configurationScope` únicamente a rutas de
   configuración, iniciar Dueño/autoridad corporativa en organización, sustituir `window.confirm`
   por diálogo accesible con foco contenido y mantener banner persistente. Dashboard conserva su
   filtro independiente; rutas operativas muestran etiqueta de `active_branch`, no selector global.
6. **BS-A06 — sesión y datos productivos fail-closed.** Antes de canary, verificar en sólo lectura que
   Dueño tenga role scope/grant organizacional, que 0077 y la head integrada estén aplicadas y que no
   existan asignaciones ambiguas. Cualquier reparación se hace mediante migración/command auditable,
   nunca edición directa; requiere autorización productiva separada.
7. **BS-A07 — rollout controlado.** Sustituir la dependencia exclusiva del flag Vite por una capacidad
   de release confirmada por servidor/organización, manteniendo el build compatible default-off.
   Activar primero lectura, después escritura corporativa y finalmente excepciones locales por
   módulo. Un módulo no habilitado permanece corporativo o lectura, pero nunca cae a `active_branch`.

Dependencias: A02 depende de A01; A03 de A02; A04 de A03; A05 de A02 y de que cada ruta de A04 pueda
transportar scope; A06 puede avanzar en paralelo sólo como diagnóstico de lectura; A07 depende de
A01..A06 verdes. BS-010 no se considera terminado hasta A04/A05; BS-018 continúa siendo el gate de
integración y auditoría.

#### Pruebas y criterios de aceptación de BS-ADMIN-001

- **Dominio/API — TDD-TC-348/350:** matriz `organization|branch` para cada módulo; scope ausente,
  branch ajena/inactiva, actor branch intentando organization, excepción no soportada, replay con
  body/scope diferente y herencia de sucursal nueva. Se comparan conteos/hash antes-después en todos
  los rechazos.
- **Regresión operativa:** Pedidos, compras, gastos, caja, producción, inventario operativo e
  impresión siguen exigiendo una `active_branch` concreta; omitirla o enviar “todas” falla cerrado.
- **Frontend semántico:** ninguna ruta de configuración listada obtiene su default desde
  `resolveBranchId()`; Dashboard no comparte estado con `configurationScope`; las mutaciones incluyen
  la unión discriminada.
- **Playwright — TDD-TC-349/644:** Dueño abre cada uno de los seis módulos en Todas las sucursales,
  Cancelar/Escape no cambia scope, confirmar Centro muestra señal persistente, cambiar ruta conserva
  sólo el contexto permitido y una respuesta tardía no restaura Centro. Validar 1440x900, 1024x768 y
  móvil Admin soportado.
- **Persistencia — TDD-TC-350/355:** SQLite acredita compatibilidad funcional; PostgreSQL aislado
  acredita constraints, versiones, no solape y concurrencia. Crear una sucursal después de la
  configuración demuestra herencia sin filas copiadas.
- **Calidad:** pruebas focales API/frontend, Ruff y mypy del backend modificado, typecheck Admin,
  builds por cambio de empaquetado/flags, trazabilidad, `git diff --check` y suite aplicable una vez en
  CI. Por ser R3, auditoría Sol independiente sobre el diff fresco antes de release.

Criterio de aceptación visible: una autoridad corporativa entra a los seis módulos viendo
**Configuración para todas las sucursales**; guardar produce una definición heredable. Sólo después de
confirmar una sucursal aparece **Sólo {Sucursal}**, y únicamente los dominios con excepción soportada
permiten guardar local. Pedidos y demás operaciones continúan mostrando y usando una sucursal concreta.

#### Operación, señales y rollback de BS-ADMIN-001

Preguntas operativas que las señales deben responder:

1. ¿Qué módulo, scope y resultado tuvo cada intento de configuración, sin incluir payload sensible?
2. ¿Aumentan `configuration_scope_invalid`, `configuration_scope_unsupported` o denegaciones después
   de habilitar un módulo?
3. ¿Alguna escritura corporativa produjo filas locales o alguna escritura local alteró otra sucursal?
4. ¿Qué versión/flag de release recibió la organización cuando ocurrió el intento?

Usar métricas de cardinalidad acotada por módulo, `scope_kind`, resultado y código estable; logs de
auditoría con actor, organización, branch opcional, comando/idempotency hash y versión de release,
sin secretos ni cuerpos libres. Alertar por tasa de rechazo o violación de invariantes, no por cada
evento individual.

Rollback: apagar nuevas excepciones locales y dejar el módulo en corporativo/lectura fail-closed;
conservar tablas, versiones, commands y auditoría. No volver a interpretar `active_branch` como scope,
no borrar excepciones aplicadas y no hacer downgrade si ya existe historia. Corregir una excepción
equivocada con una nueva versión/compensación autorizada. Despliegue, migración, configuración del
flag, canary y cualquier reparación de datos conservan autorización separada.

## 1. Objetivo verificable

Entregar un Admin que configure por defecto **Todas las sucursales** mediante herencia corporativa y
que sólo entre a una excepción local tras confirmación visible; y un POS donde Cajero/Cajero jefe/Líder
permanezcan vinculados a una sucursal, mientras Supervisor/Administrador/Dueño seleccionen un contexto
autorizado o reasignen personal mediante comandos separados, fail-closed, idempotentes y auditables.

Interpretaciones fijadas por este paquete:

- “Jefe de sucursal” corresponde al perfil canónico `Cajero jefe`; `Líder` permanece fijo a una
  sucursal y no se incluye en la reasignación de este paquete.
- Supervisor, Administrador y Dueño pueden trabajar en cualquier sucursal activa autorizada de su
  organización; la capacidad se persiste y no se infiere del nombre.
- “Todas las sucursales” es una definición corporativa heredable por sucursales actuales y futuras,
  no una copia por sucursal.
- Elegir sucursal para trabajar no cambia la adscripción de una persona.

## 2. Alcance y exclusiones

Incluye:

- selector y señal de alcance en Admin;
- contratos de scope explícito para insumos, proveedores, presentaciones, recetas, productos y precios;
- herencia corporativa y excepciones locales sin duplicar identidades;
- sesión canónica, permisos/grants y selector POS por perfil;
- cambio seguro de sucursal y aislamiento de captura/caja/gateway;
- reasignación de Cajero/Cajero jefe con locks, versión, idempotencia y auditoría;
- migraciones aditivas, compatibilidad offline, observabilidad, pruebas y rollout.

Excluye:

- cambiar permisos funcionales de catálogo/caja más allá de selección y reasignación;
- convertir Supervisor o Administrador en Dueño;
- copiar catálogos o reescribir historia;
- permitir selección offline entre sucursales;
- migrar, desplegar o modificar datos productivos dentro de este paquete documental;
- rediseñar módulos no relacionados o ejecutar un big bang.

## 3. Secuencia de implementación

### I0 — baseline y RED

1. Confirmar head Alembic integrada, roles/permisos efectivos y estado de CI sin tocar datos.
2. Crear fixtures sintéticos de seis perfiles, tres sucursales y bloqueadores R3.
3. Implementar primero TDD-TC-348..356 en RED por la razón esperada.
4. Congelar evidencia baseline de sesión, selector Admin, turno, grants y contratos efectivos.

Salida: tests focales fallan por scope implícito, falta de movilidad/comandos o contrato local; no por
errores de fixture.

### I1 — modelo de autoridad y migraciones

5. Añadir `pos.branch.select`, `staff.branch.reassign` y
   `organization_branch_workspaces` mediante revisión forward-only con preflight.
   Extender las guardas de roles para que el API ordinario no cree, retire ni altere grants o scope.
6. Añadir `users.authorization_version`, `branch_workspace_sessions`,
   `offline_authorization_leases`, `branch_selection_commands` y `branch_reassignment_commands`;
   conectar el incremento a toda mutación de autoridad y unificar el lock de usuario para emitir
   leases, seleccionar workspace o reasignar.
7. Añadir `branch_price_versions`, la relación versionada de condiciones locales de presentación y
   `branch_configuration_commands` sólo donde no exista ya un command log canónico; volver
   branch-scoped el historial/proyección de costos de presentación sin sobrescribir valores efectivos
   de otra sucursal.
8. Implementar constraints, índices, FKs y resolución efectiva sin cambiar historia.

Salida: migración SQLite/PostgreSQL aislada, seed exacto, no escalación, sin asignaciones ni copias.

### I2 — backend de sesión y cambio de sucursal

9. Extraer un resolver Python único de `allowed_branch_ids`, sucursal base, movilidad y roles
   efectivos; usarlo en login, `/auth/session`, permisos y grants offline.
10. Ampliar DTO/contrato de sesión de forma aditiva.
11. Implementar `POST /auth/branch-selections` con idempotencia, blockers, rotación de workspace y
    auditoría; mantener `GET /auth/session` exclusivamente como hidratación y agregar reemisión
    autenticada/rotatoria para recarga o respuesta perdida, sin persistir secretos planos.
12. Asegurar que todas las rutas de caja/POS reautoricen bearer, `X-Branch-Context`, branch concreto
    y versión; rechazar bypass por payload, token supersedido, replay sin autoridad o segunda pestaña.

Salida: TDD-TC-351/352 GREEN en API; ataques URL/storage y respuesta tardía no cambian contexto.

### I3 — reasignación gobernada

13. Implementar el comando Python y endpoint estricto de reasignación.
14. Bloquear objetivo/asignaciones y comprobar turno, comandos inciertos, grants y organización.
15. Actualizar asignaciones y versión en una transacción; auditar resultado/denegación redactados.
16. Exponer la acción sólo a `staff.branch.reassign` en la administración canónica de usuarios.

Salida: TDD-TC-353/356 GREEN, carrera PostgreSQL con un ganador e historia intacta.

### I4 — configuración corporativa y excepciones

17. Introducir `ConfigurationScope` compartido y un provider Admin independiente de `active_branch`.
18. Iniciar en `organization`, implementar diálogo/banner accesible y bloquear scope incompatible.
19. Refactorizar por módulo, sin fallback:
    - Insumos: identidad central; umbral/almacén local existente.
    - Proveedores: central + `supplier_branch_terms`.
    - Presentaciones: central + relación local versionada.
    - Recetas: `branch_id=NULL` corporativo + versión local.
    - Productos: central + `branch_product_availability`.
    - Precios: central + `branch_price_versions`.
20. Centralizar resolución efectiva Python y snapshots; retirar únicamente fallbacks cubiertos por RED.

Salida: TDD-TC-348/350 GREEN; sucursal nueva hereda; scope sin soporte no guarda.

### I5 — POS, gateway y experiencia

21. Adaptar `PosSessionProvider`, Settings y layout para `can_select_branch`, selección obligatoria y
    comando POST.
22. Aislar query caches, formularios, borradores, caja, dispositivo y grants por branch; abortar stale
    responses.
23. Mantener selector ausente para Cajero/Cajero jefe/Líder y encabezado de sucursal siempre visible.
24. Incluir `authorization_version` en grants/bundles, registrar todas las leases, drenar o invalidar
    grants legacy y rechazar cambio offline.

Salida: TDD-TC-349/352/354 GREEN y recorridos E2E por rol/sucursal.

### I6 — integración, auditoría y release

25. Ejecutar pruebas focales, PostgreSQL, gateway, typecheck, builds, E2E y QA visual.
26. Ejecutar suite completa aplicable una vez en CI; revisar que no existan skips de gates requeridos.
27. Auditoría Sol independiente R3 sobre permisos, historia, concurrencia, offline y reversibilidad.
28. Corregir hallazgos, actualizar matriz/evidencia y preparar dry-run de migración.
29. Solicitar por separado autorización de migración/despliegue/canary; activar default-off, observar y
    promover sólo con evidencia.

## 4. Catálogo de tareas atómicas

| ID | Cambio | Componentes previstos | Depende de | RED → GREEN / terminado |
|---|---|---|---|---|
| BS-001 | Fixtures y RED de scope | `tests/architecture`, API tests, fixtures | — | TC-348/351 fallan por fallback/autoridad vigente |
| BS-002 | Migración de permisos/grants | nueva revisión Alembic, `models.py` | BS-001 | preflight, seed exacto, no escalación, SQLite+PG |
| BS-003 | Versión, workspace, leases y command log | Alembic, `models.py`, contratos | BS-002 | versión >=1, un workspace activo, lease registry, unique key/hash, replay reautorizado |
| BS-004 | Excepciones de precio/presentación | Alembic, dominio catálogo/compras y consumidores Admin AI | BS-001 | resolver único, no solape, herencia, moneda, historial branch-scoped; compra/diagnóstico A no cambia B |
| BS-005 | Resolver de alcance | `operations.py` o servicio nuevo | BS-002 | matriz de seis perfiles y cross-org GREEN |
| BS-006 | Sesión y workspace canónicos v2 | API auth, contratos, clientes TS | BS-003/005 | aditiva, GET sólo hidrata, reemisión sin secreto persistido, fencing monotónico ante respuesta invertida, branch_selection_required verificable |
| BS-007 | Comando de selección | API Python, router, auditoría | BS-003/006 | blockers, respuesta perdida, rotación, dos pestañas, replay reautorizado GREEN |
| BS-008 | Comando de reasignación | API Python, router, auditoría | BS-003/005 | lock común con leases, atomicidad, no historia mutada GREEN |
| BS-009 | Scope provider Admin | `adminSession.tsx`, `branchContext.ts`, API client | BS-006 | organization default sin fallback GREEN |
| BS-010 | Selector/dialog/banner | `AdminLayout.tsx`, estilos compartidos | BS-009 | TC-349 semántico/visual GREEN |
| BS-011 | Insumos y umbrales | `ItemsList`, `StockThresholds`, API | BS-009 | identidad global/override local GREEN |
| BS-012 | Proveedores/presentaciones | `SuppliersList`, `PresentationsList`, API | BS-004/009 | términos/versiones locales GREEN |
| BS-013 | Productos/precios | `ProductsList`, pricing Python/API | BS-004/009 | disponibilidad/precio efectivos GREEN |
| BS-014 | Recetas | `RecipesWorkspace`, `RecipeManager`, API | BS-009 | corporate/local versionado GREEN |
| BS-015 | Selector POS seguro | `session.ts`, `Settings.tsx`, `PosLayout.tsx` | BS-006/007 | perfiles, blocker, stale response GREEN |
| BS-016 | Reasignación UI | usuarios/roles Admin, API client | BS-008 | confirmación, error estable, no éxito falso |
| BS-017 | Gateway/offline | grant/bundle API, edge gateway | BS-003/005 | registry completo, carrera, legacy drenado, version stale y branch mismatch GREEN |
| BS-018 | E2E, QA, rollback y auditoría | Playwright, PostgreSQL, CI | BS-010..017 | TC-356, rollback recovery_only/allowlist/drenado, QA, CI y auditoría sin críticos |

## 5. Gates y evidencia exigida

| Gate | Condición | Evidencia |
|---|---|---|
| G0 Especificación | IDs únicos y contrato coherente | traceability, diff-check, revisión R3 |
| G1 RED | pruebas dirigidas fallan por razón esperada | salidas TC-348..356 |
| G2 Datos | migraciones y locks reales | SQLite + PostgreSQL aislado, preflight y huella |
| G3 Backend | autoridad/selección/reasignación | API/domain negativos, replay, carrera, auditoría |
| G4 Frontend/offline | contextos aislados y UX accesible | typecheck, builds, gateway, Playwright, QA visual |
| G5 Integración | suite aplicable completa una vez | CI por SHA y auditoría Sol fresca |
| G6 Release | activación controlada | backup, migración, canary y rollback autorizados |

Un gate no configurado o saltado queda pendiente. Verde local no prueba CI, despliegue, migración ni
producción.

## 6. Rollout, reversibilidad y compensación

1. Desplegar lectura compatible y tablas inertes con flag apagado.
2. Ejecutar dry-run de roles, grants, asignaciones ambiguas, turnos y grants offline; sin PII.
3. Migrar sólo con backup verificable y una head integrada.
4. Activar backend para una organización/canary sintético; después UI Admin/POS.
5. Verificar selección/reasignación y una excepción de precio compensable sin venta real.
6. Promover gradualmente; observar denegaciones, conflictos, versiones stale y scope writes.

Rollback de aplicación primero bloquea nuevas selecciones/reasignaciones y mantiene contextos no base
en modo de recuperación. Un inventario verifica que contextos no base, turnos abiertos/cerrando,
comandos inciertos, leases y reconciliaciones lleguen a cero; sólo entonces rota al contexto base y
apaga movilidad. Si el drenado no concluye, no se fuerza el contexto fijo: se corrige hacia adelante.
No borra commands, auditoría ni versiones locales. Si ya existe historia, no se fuerza downgrade: se
conserva esquema inerte. Reasignación errónea se corrige con otro comando auditable hacia la sucursal
anterior después de cerrar bloqueadores; nunca editando historia.

## 7. Afirmaciones R3 a refutar

| Afirmación | Evidencia esperada | Intento de refutación | Riesgo residual |
|---|---|---|---|
| Un perfil fijo no cruza sucursal | API + E2E | URL/storage/payload/contexto B | dispositivo offline hasta TTL |
| Selección no amplía permisos | matriz por perfil, workspace y branch | API directa, dos pestañas, token supersedido, replay tras revocación | mala configuración de grants productivos |
| Reasignación es atómica | PG locks + fallo inyectado | dos destinos, carrera con lease y caída entre updates | operación humana incorrecta autorizada |
| Configuración global no se vuelve local | scope tests + auditoría | active_branch/primera sucursal/stale response | módulo legacy no migrado |
| Historia no cambia | conteos/hash antes-después | reasignar con ventas/cortes previos | consulta legacy que use branch actual del usuario |
| Offline no cambia branch | gateway SQLite + registro PG | bundle A con payload B, carrera de lease, grant legacy y versión stale | revocación no instantánea durante TTL acotado |
| Rollback no abandona operaciones | dry-run + E2E de drenado | turno/comando/contexto no base al apagar flag | forward-fix si no puede drenarse |

## 8. Auditoría independiente R3 de la especificación — 2026-10-10

La primera revisión independiente encontró seis bloqueadores P1: elusión por API sin contexto durable,
dos contratos distintos para cambiar sucursal, grants offline no registrados ni serializados,
autoridad financiera ambigua de presentaciones, reportes contradictorios y rollback capaz de dejar
una caja abierta fuera de contexto. El paquete se corrigió para:

- exigir workspace opaco activo en cada operación scoped, reautorizar replays y reemitir un secreto
  rotado ante respuesta perdida/recarga sin persistirlo plano;
- reservar `POST /auth/branch-selections` como única transición y dejar GET sólo para hidratación;
- registrar todas las leases y compartir lock entre emisión, selección y reasignación;
- aislar costo/preferencia e historial de presentaciones por sucursal;
- limitar los reportes operativos POS de Supervisor/Administrador a `active_branch`, sin alterar el
  consolidado corporativo explícito ya gobernado por PRD-FR-226;
- usar `recovery_only` con allowlist de cierre/recuperación y drenar contextos, turnos, comandos y
  leases antes de volver al contexto fijo.

La evidencia de esta fase es documental y de trazabilidad; no acredita runtime, migración, PostgreSQL,
gateway, E2E, CI, despliegue ni producción. La aceptación de implementación sigue condicionada a
TDD-TC-348..356 y a una auditoría independiente fresca sobre el diff ejecutable.

## 9. Definición de terminado

- PRD/SDD/ADR/BDD/TDD/matriz continúan coherentes y sin IDs huérfanos.
- Cada tarea activada tiene RED por causa correcta y GREEN focal ejecutado.
- PostgreSQL acredita locks/concurrencia; SQLite acredita compatibilidad local, no la sustituye.
- Admin inicia en Todas las sucursales; POS respeta la matriz de perfiles.
- Reasignación, selección y scope writes son idempotentes/auditables y no alteran historia.
- Typecheck, builds, E2E, QA visual, CI y auditoría independiente están verdes.
- Gates omitidos y riesgo residual se reportan; release/migración/producción no se infieren.
