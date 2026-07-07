# Prompt de importación para Codex

Actúa como arquitecto principal e ingeniero responsable del repositorio RestaurantOS.

Este repositorio contiene un harness de desarrollo basado en PRD, SDD, BDD y TDD. Antes de escribir código debes leer, en este orden:

1. `README.md`
2. `AGENTS.md`
3. `docs/00-contexto-producto.md`
4. `docs/01-PRD.md`
5. `docs/02-SDD.md`
6. `docs/03-BDD.md`
7. `docs/04-TDD.md`
8. `docs/05-matriz-trazabilidad.md`
9. `docs/06-roadmap-entregas.md`
10. `codex/BOOTSTRAP_CHECKLIST.md`

Objetivo inmediato:

Preparar el repositorio para construir RestaurantOS, una plataforma web y offline-first para una cadena mexicana de siete sucursales, quince cajas y varias razones sociales. La aplicación central se desplegará en Easypanel dentro de una VPS de Hostinger. Cada sucursal tendrá un gateway Windows con SQLite, sincronización e impresión local.

Restricciones obligatorias:

- No construyas toda la aplicación en una sola iteración.
- No inventes requisitos.
- No cambies reglas de negocio sin modificar la documentación.
- No acoples el dominio a proveedores externos.
- PostgreSQL es la fuente central de verdad.
- SQLite es la fuente local temporal.
- El inventario es un ledger.
- Pagos y movimientos sensibles son inmutables.
- Toda integración debe ser idempotente.
- Toda operación offline debe ser reconciliable.
- Todo cambio debe mapear requisito, escenario y prueba.

Primera tarea:

1. Analiza la consistencia entre PRD, SDD, BDD y TDD.
2. Enumera contradicciones, omisiones y riesgos.
3. Propón las ADR faltantes.
4. Propón la estructura definitiva del monorepo.
5. Propón versiones de lenguaje, framework y herramientas.
6. Diseña la fase 0 del roadmap.
7. Define el primer vertical slice de fase 1.
8. Crea o actualiza la matriz de trazabilidad.
9. No escribas lógica de negocio completa todavía.
10. Entrega un plan por commits y pull requests.

Después de mi aprobación, crea el scaffold inicial con:

- React + TypeScript + Vite.
- Python + FastAPI.
- PostgreSQL.
- Redis.
- SQLite para gateway.
- Alembic.
- Pytest.
- Playwright.
- Docker Compose local.
- Plantillas de despliegue para Easypanel.
- CI en GitHub Actions.
- Contratos compartidos.
- Logs estructurados.
- Health checks.
- Configuración por ambiente.
- Gestión segura de secretos.
- Primeras pruebas de arquitectura.

En cada respuesta reporta:

- requisitos afectados,
- documentos afectados,
- pruebas agregadas o modificadas,
- riesgos,
- decisiones pendientes,
- siguiente incremento recomendado.
