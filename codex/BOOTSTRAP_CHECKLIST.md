# Checklist de bootstrap para Codex

## Antes de escribir código

- [x] Leer `AGENTS.md`.
- [x] Leer PRD, SDD, BDD y TDD.
- [x] Confirmar el alcance de la fase 0.
- [x] Detectar contradicciones.
- [x] Crear un registro de decisiones abiertas.
- [x] Proponer estructura del monorepo.
- [x] Proponer stack exacto y versiones.
- [ ] Proponer estrategia de migraciones.
- [x] Proponer contrato entre nube y gateway.
- [x] Proponer primer vertical slice.
- [x] Actualizar trazabilidad.

Ver:

- `docs/07-analisis-consistencia.md`.
- `docs/08-adrs-propuestas.md`.
- `docs/09-fase-0-y-vertical-slice.md`.
- `docs/05-matriz-trazabilidad.md`.

## Primer entregable esperado

Un pull request inicial que contenga:

- estructura del monorepo,
- configuración de herramientas,
- API health check,
- PostgreSQL y migraciones,
- Redis,
- frontend mínimo,
- gateway mínimo,
- contratos compartidos,
- CI,
- tests,
- docker compose local,
- plantilla Easypanel,
- documentación de ejecución.

No debe contener todavía lógica completa de ventas, inventarios o rutas.
