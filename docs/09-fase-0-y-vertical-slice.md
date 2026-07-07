# Fase 0 y primer vertical slice

## Fase 0: plataforma verificable

### Objetivo

Preparar el monorepo para construir RestaurantOS con PRD + SDD + BDD + TDD como fuente de verdad, sin implementar ventas, inventario o rutas completas.

### Entregables

| Entregable | Resultado esperado | Verificacion |
|---|---|---|
| Monorepo | Estructura `apps/`, `packages/`, `infra/`, `docs/`, `tests/` | Prueba de arquitectura |
| API central | Health check versionado | Pytest |
| Gateway minimo | Contrato y placeholder operativo | Prueba de arquitectura |
| Contratos | JSON Schema base para health, command envelope y event envelope | Validacion de schemas |
| Docker local | PostgreSQL, Redis, API y worker | `docker compose config` |
| CI | Workflow con pruebas documentales y backend | GitHub Actions |
| Easypanel | Plantilla inicial sin secretos | Revision documental |
| Trazabilidad | Requisitos enlazados con SDD, BDD y TDD | Pytest documental |

### Stack exacto inicial

- Python `3.12`.
- FastAPI `>=0.115,<1.0`.
- Pydantic `>=2.8,<3.0`.
- SQLAlchemy `>=2.0,<3.0`.
- Alembic `>=1.13,<2.0`.
- Pytest `>=8.0,<9.0`.
- Ruff `>=0.6,<1.0`.
- MyPy `>=1.10,<2.0`.
- Node.js `22 LTS`.
- pnpm `10`.
- React `19`.
- TypeScript `5.8`.
- Vite `7`.
- PostgreSQL `16`.
- Redis `7`.
- Playwright `>=1.45`.

### Gates de fase 0

1. El repositorio clona y ejecuta pruebas sin secretos.
2. La API responde health check.
3. La matriz de trazabilidad no tiene requisitos criticos sin mapeo.
4. No hay dependencia directa del dominio con proveedores externos.
5. Docker Compose valida sintaxis.
6. CI queda listo para pull requests.

## Primer vertical slice de fase 1

### Nombre

`VS-001 Venta local offline minima`

### Alcance funcional

1. Abrir turno de caja.
2. Crear pedido de mostrador con catalogo minimo.
3. Asignar folio local.
4. Enviar tareas a KDS local.
5. Generar trabajo de impresion.
6. Marcar produccion completada.
7. Registrar pago en efectivo.
8. Cerrar turno.
9. Sincronizar comando con nube cuando vuelva la conexion.
10. Descargar eventos remotos pendientes desde el ultimo checkpoint confirmado.
11. Mostrar estado de sincronizacion para detectar rezago operativo.

### Requisitos principales

- `PRD-FR-020`, `PRD-FR-027`, `PRD-FR-030`.
- `PRD-FR-040`, `PRD-FR-043`, `PRD-FR-046`, `PRD-FR-048`.
- `PRD-FR-050`, `PRD-FR-051`, `PRD-FR-053`, `PRD-FR-054`, `PRD-FR-057`.
- `PRD-FR-180` a `PRD-FR-188`.

### Escenarios BDD iniciales

- `BDD-SC-001`.
- `BDD-SC-002`.
- `BDD-SC-004`.
- `BDD-SC-011`.
- `BDD-SC-018`.

### Pruebas TDD iniciales

- `TDD-TC-002`.
- `TDD-TC-003`.
- `TDD-TC-006`.
- suites `TDD-TS-003`, `TDD-TS-004`, `TDD-TS-005`, `TDD-TS-006`, `TDD-TS-011`.

## Plan por commits y pull requests

### PR-001 Harness y plataforma base

- docs de consistencia, ADRs y fase 0,
- matriz expandida,
- scaffold monorepo,
- health check API,
- contratos base,
- CI,
- Docker Compose,
- plantilla Easypanel.

### PR-002 Dominio base sin persistencia completa

- errores de negocio,
- value objects para dinero, cantidades y timestamps,
- maquinas de estado puras para pedido, caja e impresion,
- pruebas unitarias iniciales.

### PR-003 Gateway local minimo

- SQLite WAL,
- outbox local,
- folio local,
- WebSocket local,
- pruebas de dos cajas offline.

### PR-004 POS + KDS minimo

- pantalla POS interna,
- tablero KDS,
- envio de tareas,
- impresion simulada,
- Playwright smoke.

### PR-005 Sincronizacion nube-gateway

- command envelope,
- idempotencia,
- checkpoints,
- reintentos,
- reconciliacion basica.
