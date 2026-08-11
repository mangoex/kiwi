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
