# ADRs propuestas

Estas ADRs complementan las decisiones ya registradas en `docs/02-SDD.md`. Deben promoverse a ADR formal cuando el equipo apruebe el alcance tecnico.

## SDD-ADR-016 Versiones base del stack

- Frontend: Node.js 22 LTS, pnpm 10, React 19, TypeScript 5.8, Vite 7.
- Backend: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic.
- Pruebas: Pytest, Playwright, Ruff, MyPy, Vitest.
- Infraestructura local: Docker Compose con PostgreSQL 16 y Redis 7.

Justificacion: fija reproducibilidad sin introducir dependencias de negocio prematuras.

## SDD-ADR-017 Contratos compartidos por JSON Schema

Los contratos entre apps, API, gateway y workers se versionaran en `packages/contracts/schemas`.

Reglas:

- todo contrato publico incluye `schema_version`,
- los cambios incompatibles crean version nueva,
- las pruebas de contrato validan ejemplos deterministas,
- los adaptadores externos traducen hacia el modelo canonico.

## SDD-ADR-018 Health checks y readiness

Cada servicio expone:

- `GET /health/live`: proceso vivo,
- `GET /health/ready`: dependencias minimas disponibles,
- `GET /health/version`: version, commit y entorno.

Fase 0 implementa health sin dominio. Fases posteriores agregan dependencias reales.

## SDD-ADR-019 Gateway Windows instalable

El gateway local se implementara como servicio instalable para Windows con:

- SQLite WAL,
- outbox/inbox persistente,
- spool persistente de impresion,
- WebSocket local,
- logs JSON,
- actualizacion controlada y rollback.

El gateway no se despliega en Easypanel.

## SDD-ADR-020 Modelo inicial de errores

Los errores de negocio usaran codigos estables:

- `VALIDATION_ERROR`,
- `PERMISSION_DENIED`,
- `STATE_TRANSITION_DENIED`,
- `IDEMPOTENCY_CONFLICT`,
- `OFFLINE_CONFLICT`,
- `EXTERNAL_PROVIDER_UNAVAILABLE`,
- `AUDIT_REQUIRED`.

Los controladores HTTP solo traducen errores; no contienen reglas de dominio.

## SDD-ADR-021 Auditoria append-only

La auditoria se modela como eventos append-only con:

- actor,
- alcance,
- accion,
- entidad,
- antes/despues cuando aplique,
- correlation id,
- causation id,
- timestamp UTC.

No se elimina auditoria para simplificar pruebas o migraciones.

## SDD-ADR-022 Services como limites logicos iniciales

El directorio `services/` representa limites de dominio y pruebas, no procesos desplegables independientes durante fase 0 y fase 1.

Esto preserva monolito modular y evita un big bang de microservicios.

## SDD-ADR-023 Propuesta — transición reversible a perfiles acumulativos

**Estado: aprobada el 2026-08-10.** Alternativas evaluadas: (A) mapear cada rol semilla explícitamente a un
perfil nuevo y requerir decisión para Administrador corporativo; (B) convertir Administrador
corporativo automáticamente en Dueño; (C) conservar permisos efectivos y presentar nuevos perfiles
sólo como plantillas. Se recomienda A con dry-run, tabla de mapeo, reporte de diferencias,
aprobación por organización y downgrade que restaure asignaciones. B queda descartada porque concede
todo/todas las sucursales sin decisión individual verificable. PCO-001 siembra perfiles/permisos y
registro de mapeo, pero no asigna Dueño automáticamente ni altera permisos legacy de Cajero.

El registro conserva ciclos históricos append-only: sólo puede existir un mapping activo
`pending|mapped` por usuario/perfil; los `reversed` anteriores coexisten. La concesión
`organization_all_permissions` es un invariante estructural de `scope=organization`: no se borra,
reduce por permisos ni convierte a branch. Renombrar no modifica autoridad y exige al mismo nivel de
autoridad; `access.organization.all_branches` ordinario no sustituye el grant.

El bootstrap inicial queda fuera de Alembic y HTTP: es un comando interno idempotente que sólo acepta
organización, actor operacional, procedencia y la configuración explícita de los dos usuarios
confirmados. La validación de ambos usuarios/rol/conflictos precede cualquier inserción. El mapeo pasa
por `PENDING -> MAPPED -> REVERSED`, guarda snapshot mínimo sin PII y sólo añade/retira la asignación
destino creada por él; no elimina historial ni convierte por nombre o automáticamente a un legacy.

## SDD-ADR-024 Aprobada — identidad y versiones de conceptos de caja

**Estado: aprobada por el Dueño de producto para PCO-002 el 2026-08-11 mediante la instrucción
“Sí, adelante”.** No sustituye ni revoca otro ADR. Se separa la identidad corporativa con código
inmutable de sus versiones publicadas. La alternativa de sobrescribir una sola fila se descarta
porque pierde la configuración histórica que los movimientos de PCO-003 deberán congelar. La
alternativa de activar el ledger en la misma entrega se descarta para conservar un incremento
reversible sin escrituras financieras.

Cada mutación se registra en una tabla de comandos con clave idempotente organizacional, hash del
payload canónico y resultado estable. Archivar conserva identidad/versiones y sólo la excluye de la
proyección efectiva. El downgrade de esquema sólo elimina tablas vacías; si existe historia queda
bloqueado y el rollback de aplicación desactiva rutas conservando datos.

La aprobación autoriza especificación e implementación aislada de PCO-002; no autoriza PCO-003,
commit, push, despliegue, migración productiva ni modificación de datos reales. La implementación
queda a cargo de Terra y sólo cambia de `Disenado` después de evidencia técnica auditada por Sol.

## SDD-ADR-025 Aprobada — ledger de caja compatible y compensatorio

**Estado: aprobada por el Dueño de producto para PCO-003 el 2026-08-11 mediante la instrucción
“Adelante con el PCO-003 completamente”.** No sustituye ni revoca `SDD-ADR-024`: consume el catálogo
versionado que ese ADR dejó como precondición y conserva identidad e historia de conceptos.

PCO-003 amplía en sitio la tabla legacy `cash_movements` sin reescribir ni borrar sus filas. Los
movimientos nuevos conservan importe positivo en centavos, tipo persistido `deposit|withdrawal`,
snapshot de la versión efectiva del concepto para comandos manuales, referencia, evidencias opacas,
actor, turno, sucursal, procedencia e identidad de compensación. Las filas legacy `withdrawal` y
`cash_reversal` continúan legibles; la proyección Python interpreta `cash_reversal` como entrada
compensatoria y no lo duplica. La alternativa de crear un segundo ledger se descarta porque dividiría
la fuente financiera y duplicaría compras; la alternativa de normalizar destructivamente la historia
legacy se descarta porque impediría una reversión verificable.

Una tabla de comandos separada aplica idempotencia por `(organization_id, idempotency_key)` y guarda
hash canónico y resultado estable. La clave técnica de la fila legacy puede ser un derivado SHA-256,
pero nunca sustituye la identidad de comando ni se expone como autoridad. La compensación crea un
movimiento opuesto, exacto y único; no actualiza ni elimina el original. El efectivo esperado se
calcula sólo en Python como fondo inicial más pagos `cash` confirmados más depósitos menos retiros,
incluidas compras y compensaciones exactamente una vez.

La aprobación autoriza especificación, implementación aislada por Terra, auditoría iterativa por Sol
y, sólo después de todos los gates verdes, commit, PR/merge y push. No autoriza despliegue,
`alembic upgrade` productivo, datos reales, PCO-004+, corte final, cierre operativo nuevo ni
sincronización offline. El edge gateway permanece fail-closed para movimientos manuales hasta PCO-008.
