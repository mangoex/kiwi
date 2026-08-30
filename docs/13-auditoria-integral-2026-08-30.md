# Auditoría integral del sistema — 2026-08-30

## Dictamen

**Estado: NOT READY para declarar preparación general de piloto o producción.** Las once brechas del
primer corte quedaron contenidas, corregidas o acotadas en el checkout local. La revisión
independiente encontró una migración histórica destructiva (`0049`) y ya existe una contención
forward-only local, pero cualquier estado que no coincida con la huella limpia aún requiere una
decisión explícita de datos. Las migraciones nuevas ya pasaron sus oráculos focales en PostgreSQL 16
local y aislada. CI remoto ya fue observado en el PR #56, pero continúa rojo porque Dependency Review
requiere habilitar Dependency Graph en el repositorio; tampoco existe evidencia de despliegue,
migración productiva ni comportamiento productivo.

Snapshot base: `0b11c1e80e9f0ccbab9943e91080685f5ccaf5eb` en `main`, alineado con `origin/main`
al iniciar. No se consultó ni modificó una base productiva, no se ejecutaron migraciones contra datos
reales, no se desplegó, no se hizo commit/push y no se instalaron dependencias. Los archivos no
rastreados preexistentes se preservaron.

## Método y decisión sobre `security-guidance`

La revisión comparó PRD, SDD, BDD, TDD, matriz, reglas, runtime, migraciones, CI y pruebas. Del plugin
de Anthropic se adoptó únicamente este complemento liviano en `AGENTS.md`: seguir entrada a destino
sensible, comparar guardas hermanas, comprobar que la condición validada corresponde a la acción,
buscar fallos abiertos y revisar exposición de datos.

**Decisión: no instalar el plugin.** RestaurantOS ya exige clasificación R0..R3, trazabilidad,
RED/GREEN, gates dirigidos e inspección independiente para R3. Los hooks automáticos del plugin
duplicarían ese ciclo, son específicos de Claude Code, pueden producir falsos positivos y transmiten
diffs/contenido relevante al endpoint del modelo configurado. Su propia documentación los considera
asesoría best-effort, no sustituto de revisión humana, SAST/DAST, análisis de dependencias o pentest.
El aporte no redundante quedó como una sola regla de revisión, sin hook, agente, prompt copiado ni
dependencia nueva.

Como complemento técnico distinto se agregó **un solo** gate de Dependency Review por pull request,
con severidad alta y la acción oficial fijada a SHA. No se agregaron scanners redundantes. Su check
remoto sólo será evidencia si GitHub Dependency Review está habilitado y realmente lo ejecuta.

## Resultado de hallazgos originales

| ID | Severidad | Estado local | Evidencia y límite |
|---|---:|---|---|
| AUD-001 Pedido público heredado | Crítica | Contenido | `POST /public/orders` siempre responde `503 public_order_unavailable`; el flujo `PublicOrderIntent` conserva gate propio. Sin despliegue observado. |
| AUD-002 Reparación RBAC 0047 | Crítica | Reparación local | `0056_repair_0047_canonical_roles` usa identidades reservadas, preflight estricto, perfil exacto, no escalación, auditoría y rollback forward-only. SQLite y oráculo focal PostgreSQL 16 verdes; CI no observado. |
| AUD-003 Traversal SPA | Alta | Corregido | Resolución canónica, pertenencia a raíz y regresiones para traversal codificado/symlink. |
| AUD-004 Compra cash sin caja | Alta | Corregido | Admin y POS exigen/envían `register_id` sólo para efectivo y retienen la misma idempotency key hasta éxito; backend conserva atomicidad. |
| AUD-005 Gates locales rojos | Alta | Corregido local | Allowlist revisada, Ruff y política del repositorio verdes. CI remoto no observado. |
| AUD-006 Migración en arranque web | Alta | Corregido | Se eliminó `auto_migrate`, lifespan y todo llamado Alembic del proceso web; el runbook exige promoción separada y fallo de release. |
| AUD-007 Scope humano KDS/print/sync | Alta | Corregido | Sucursal reautorizada por actor, ambigüedad fail-closed y permiso `sync.events.read` en `0057`; el shell HTML heredado sin scope fue retirado y quedó cubierto por un guard. |
| AUD-008 Almacenes | Media | Corregido | Navegación visible; listado sin campo inexistente, incluye inactivos y aplica scope; exactamente uno por sucursal; una sucursal activa no puede inactivar su almacén. |
| AUD-009 Precio/costo ambiguo | Media | Corregido | Precio por presentación antes de descuento; impuesto fuera del costo inventariable; promedio por sucursal/almacén y sólo tras recepción confirmada. |
| AUD-010 Dependencias | Media | Gate bloqueado por configuración | Un Dependency Review de severidad alta, acción fijada a SHA. El PR #56 lo ejecutó, pero GitHub lo rechazó porque Dependency Graph no está habilitado; no equivale a análisis verde ni a vulnerabilidad detectada. |
| AUD-011 Historia/estado documental | Media | Corregido | `docs/07-analisis-consistencia.md` conserva el hallazgo histórico y agrega vigencia fechada para CONS-030/031. |

## Hallazgos de la auditoría independiente

### AUD-012 — Crítico — Contenido local; reconciliación histórica no inferible

- Busca “La Primavera” con coincidencia parcial por nombre/código y, si no encuentra, crea razón
  social, unidad, sucursal y almacén con datos fiscales sintéticos.
- Para `caja01laprimavera@kiwi.com`, si no encuentra el rol `Cajero`, toma el primer rol de la
  organización sin comprobar autoridad.
- Ejecuta `DELETE FROM user_roles WHERE user_id = :user_id`, por lo que puede retirar asignaciones
  corporativas o de otras sucursales antes de insertar una sola relación.
- `downgrade()` es vacío y no conserva snapshot de asignaciones previas.

**Impacto:** pérdida o escalación de autoridad y creación de datos organizacionales no aprobados.
En una instalación nueva el rol canónico normalmente existe por 0035, pero esa coincidencia no hace
seguro ejecutar el mismo código sobre estados heredados o parcialmente migrados.

**Contención implementada localmente:** 0049 permanece intacta. La revisión forward-only
`0058_verify_0049_la_primavera_seed` sólo acepta la huella limpia conjunta de sucursal, almacén,
cuenta, rol Cajero reservado y una única asignación. Conserva `user_roles` sin mutarlo, guarda su
snapshot en `audit_events` y bloquea coincidencia parcial, cuenta preexistente, identidad alterada o
asignaciones adicionales antes de escribir. SQLite cubre base limpia, replay, downgrade bloqueado y
tres estados ambiguos. El oráculo focal de PostgreSQL 16 pasó sobre una base local descartable:
verificó la huella limpia, preservación de asignaciones, auditoría y downgrade bloqueado. El gate de
CI sigue configurado pero no observado. La huella exacta es la condición conservadora admitida por
esta revisión, no prueba retroactiva de procedencia histórica.

**Límite residual:** 0049 no guardó las asignaciones eliminadas; 0058 no puede reconstruirlas y no
declara haberlo hecho. Un preflight ambiguo debe detener el release en 0057 hasta comparar un respaldo
anterior y aprobar una compensación separada. No se ejecutó contra producción ni se tomó una decisión
de negocio/datos sobre esa cuenta.

### AUD-013 — Medio — Corregido localmente

El archivo `platform_shell.py` conservaba llamadas KDS, impresión y sync sin sucursal explícita, pero
la revisión de consumidores confirmó que no era fallback ni runtime activo: no tenía imports y
`main.py` sirve exclusivamente los bundles SPA. Su mera presencia contradecía además el snapshot
histórico de RBAC que ya lo declaraba retirado.

**Corrección y evidencia:** se eliminó el archivo muerto en vez de agregar complejidad a una segunda
UI. Un guard de arquitectura exige su ausencia y que `main.py` no lo referencie; arquitectura y
trazabilidad quedaron `15 passed`, y la contención/fallback de las SPAs quedó `2 passed`. Las SPAs
modernas continúan sujetas a sus pruebas propias de autenticación y scope.

### AUD-014 — Bajo — Medido; optimización diferida

Los builds actuales son correctos. Admin genera `625.94 kB` minificados / `167.31 kB` gzip y POS
`531.69 kB` / `154.80 kB` gzip; Vite advierte por superar 500 kB antes de compresión. No existe un
presupuesto de carga aprobado ni medición de usuarios que demuestre impacto, y convertir todas las
rutas eager a carga diferida introduciría estados de carga/error y una superficie de regresión mayor
que el hallazgo.

**Decisión:** no cambiar el runtime sólo para silenciar la advertencia. Registrar métricas de carga en
la red objetivo y definir un presupuesto antes de dividir rutas; el riesgo de rendimiento permanece
aceptado y no bloquea seguridad o consistencia funcional.

### AUD-015 — Medio — Corregido localmente

SDD-ADR-015 describe `catalog.manage` como permiso para administrar sucursales y almacenes; el alta de
sucursal usa ese permiso, pero crear/editar almacenes exige `admin.manage`. El listado usa
`catalog.manage`. El estado anterior era conservador (bloqueaba más), no una escalación, pero un rol
corporativo personalizado con `catalog.manage` podía listar el módulo y no guardar cambios que la
descripción del permiso promete.

**Corrección y evidencia:** PRD-FR-018 y SDD-ADR-015 ya resolvían la decisión: almacenes pertenecen al
catálogo corporativo, mientras `admin.manage` queda para usuarios, roles y permisos. Alta y edición
ahora exigen `catalog.manage`; navegación y ruta directa ocultan/rechazan el módulo sin ese permiso.
Una regresión prueba un actor organization-scoped con sólo `catalog.manage` y otro con sólo
`admin.manage`; el paquete de almacenes quedó `2 passed`, el test semántico frontend pasó y Admin
typecheck quedó verde. No se cambiaron grants semilla ni se concedió autoridad nueva a Supervisores.

### AUD-016 — Medio — Corregido localmente

Se retiró `create_public_online_order` de `operations.py`; ninguna fuente API o prueba conserva el
símbolo. Las tres regresiones antiguas ahora ejercen directamente
`create_public_order_intent`/`accept_public_order_intent`: teléfono inválido/normalizado, captura sin
turno ni orden y aceptación autenticada con tarea productiva y reserva exacta de 240 g. Un guard AST
exige que el escritor no exista y que `public_create_order` conserve como único cuerpo la denegación
`public_order_unavailable` 503.

**Evidencia y límite:** `52 passed, 3 skipped` en arquitectura, intención/aceptación pública, rate
limit, GPS/sucursal y PostgreSQL opt-in; los skips corresponden a PostgreSQL no disponible. Ruff
`apps/api tests`, política y whitespace están verdes. No hay CI remoto, despliegue ni evidencia
productiva; por ello la corrección sólo aplica al checkout.

### AUD-017 — Crítico — Corregido localmente

La evaluación genérica de permisos aceptaba `admin.manage` desde un rol branch-scoped si su asignación
coincidía con la sucursal por defecto. Una regresión demostró que ese actor podía listar y crear roles
organization-scoped, aunque PRD-FR-005/018 y SDD-ADR-015 reservan administración de identidad al
ámbito corporativo. Esto convertía una concesión personalizada o heredada mal configurada en una vía
de escalación organizacional.

**Corrección y evidencia:** `require_permission` ahora considera exclusivamente roles
organization-scoped cuando la capacidad solicitada es `admin.manage`; los demás permisos conservan
su semántica existente. RED reprodujo respuestas 200 para listado/alta de roles; GREEN las convirtió
en `403 permission_denied` y preservó el acceso del administrador corporativo. El módulo completo
`test_platform_api.py` quedó `81 passed` y Ruff focal está verde. No se migraron perfiles, no se
editaron asignaciones ni se consultó una base real; CI y despliegue siguen pendientes.

## Evidencia ejecutada

| Gate | Resultado local |
|---|---|
| Política del repositorio | PASS |
| Ruff `apps/api tests` | PASS |
| Arquitectura/trazabilidad | `138 passed` |
| Arquitectura y migraciones tras 0058 | `213 passed, 4 skipped` en 386.97 s; skips PostgreSQL opt-in |
| AUD-016 escritor público retirado | `52 passed, 3 skipped`; invariantes antiguas migradas al flujo canónico |
| AUD-015 almacenes y permiso canónico | Backend focal `2 passed`; frontend semántico y Admin typecheck PASS |
| AUD-017 alcance organizacional de `admin.manage` | RED reproducido; GREEN `81 passed` en módulo completo de plataforma |
| AUD-013 retiro de shell legacy | Arquitectura/trazabilidad `15 passed`; contención SPA `2 passed` |
| Frontend semántico completo | PASS después de actualizar la expectativa KDS al scope nuevo |
| TypeScript del workspace | PASS en 6 proyectos |
| Builds Admin/POS | PASS; Admin 625.94/167.31 kB y POS 531.69/154.80 kB minificado/gzip |
| Regresión pública posterior al full run | `32 passed` |
| Suite Python integral | `657 passed, 49 skipped, 4 failed` en 654.25 s |
| Falla funcional de la integral | Un test heredado esperaba el endpoint público prohibido; fue corregido y su paquete quedó `32 passed` |
| Fallas ambientales restantes | 2 por `pandas` y 1 por `jsonschema` ausentes localmente; están declarados en `apps/api/pyproject.toml` |
| Migraciones 0056/0057/0058 SQLite | PASS dentro de suite focal/integral |
| PostgreSQL 0056/0058 focal | `2 passed in 13.05s` sobre PostgreSQL 16.15 y dos DBs locales descartables; `DATABASE_URL` ausente y variables aisladas `RBAC0056_TEST_POSTGRES_URL`/`SEED0058_TEST_POSTGRES_URL` |
| Suite PostgreSQL ampliada | No ejecutada localmente; CI no observado |
| Revalidación de trazabilidad tras registrar evidencia | `8 passed in 0.14s` |
| Dependency Review | Configurado, no ejecutable como gate local |
| `git diff --check` | PASS |
| CI remoto | PR #56 ejecutado: frontend, Docker y política/whitespace verdes; Dependency Review bloqueado por Dependency Graph deshabilitado; Python detectó una fixture histórica que intentaba cruzar 0058 en downgrade y activó esta corrección dirigida |
| Despliegue, migración y producción | No observados |

Node local es `20.20.2`; el proyecto y CI requieren Node 22. Typecheck, pruebas semánticas y builds
pasaron, pero esa evidencia local no sustituye el runtime autoritativo de CI.

## Respuesta operativa sobre inventario y precio

- La organización puede tener **varios almacenes**, porque tiene varias sucursales.
- El contrato actual exige **exactamente un almacén por sucursal**. Se crea junto con la sucursal y
  no puede sustituirse por otro mientras el registro exista.
- El precio de compra se captura en el borrador como **precio por presentación antes de descuento**;
  el último precio de la presentación sólo precarga una referencia editable.
- Al confirmar, backend calcula `cantidad de presentaciones × precio − descuento`, convierte a la
  unidad base con `Decimal` y actualiza el costo promedio ponderado de esa
  sucursal/almacén/insumo. El impuesto no integra costo; flete continúa rechazado hasta aprobar una
  política. Editar la presentación sin confirmar una recepción no mueve existencia ni promedio.

## Próximo paquete recomendado

1. Para cualquier instalación histórica candidata, ejecutar primero 0058 sobre una restauración
   aislada; si su preflight es ambiguo, obtener la decisión explícita sobre la cuenta y construir una
   compensación separada antes de producción. El caso limpio ya está verde en PostgreSQL 16 local.
2. Abrir PR y exigir Python/PostgreSQL, frontend, Dependency Review y CI completos; esto requiere
   restaurar la autenticación de GitHub y, sólo entonces, crear la rama ya autorizada condicionalmente.
3. AUD-013, AUD-015, AUD-016 y AUD-017 ya están corregidos localmente; AUD-014 queda medido y diferido
   hasta contar con presupuesto/telemetría, sin presentarlos como integración aprobada.
4. Mantener despliegue, migración y datos productivos bajo autorización separada.
