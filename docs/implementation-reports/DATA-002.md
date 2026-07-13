# DATA-002 — bandeja accionable de importaciones

## Problema observado

La primera versión mostraba los 793 pendientes ordenados por tipo y fila, pero no ofrecía filtros,
identidad legible ni una acción. Las primeras 100 filas eran presentaciones con la misma causa, por
lo que la pantalla parecía repetir un error sin explicar cómo resolverlo.

## Solución

- El API corporativo agrega conteos por tipo y estado a cada lote.
- La consulta de registros acepta `entity_type` y mantiene límite y desplazamiento.
- La pantalla separa Presentaciones, Productos y Recetas mediante tarjetas con totales.
- Cada flujo explica qué dato falta, qué no debe inventarse y cuál es el editor canónico.
- Cada fila muestra nombre, SKU y metadatos heredados útiles, nunca el payload crudo.
- Se muestran 25 registros por página con navegación y búsqueda sobre la página visible.
- Los productos enlazan al catálogo con `?search=<sku>` y el catálogo aplica el filtro.

No hay migración ni cambio de reglas de negocio. La bandeja no activa productos, no crea proveedores
y no genera recetas; las mutaciones continúan en los contratos canónicos con sus permisos y
auditoría.

## Trazabilidad

- Requisitos: PRD-FR-192, PRD-FR-193 y PRD-FR-196.
- Escenarios: BDD-FEAT-054, BDD-SC-152 a BDD-SC-155.
- Pruebas: TDD-TS-054, TDD-TC-047, `apps/api/tests/test_legacy_import.py` y
  `tests/architecture/test_actionable_import_review.py`.

## Evidencia

- `python3 -m pytest`: 112 pruebas aprobadas.
- `python3 -m pytest apps/api/tests/test_legacy_import.py tests/architecture/test_actionable_import_review.py tests/architecture/test_traceability.py -q`: 12 aprobadas.
- `python3 -m ruff check apps/api tests tools`: sin hallazgos.
- `pnpm typecheck`: UI, Admin, POS y KDS aprobados.
- Builds de producción de Admin, POS y KDS aprobados.
- `git diff --check`: limpio.
- Node local 20 muestra la advertencia esperada frente al requisito 22; CI utiliza Node 22.
