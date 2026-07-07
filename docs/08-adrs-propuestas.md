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

