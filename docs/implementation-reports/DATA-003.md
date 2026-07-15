# DATA-003 — depuración y catálogo corporativo compartido

## Alcance implementado

- Productos: se elimina la comilla de importación inicial, se conserva el SKU como texto con ceros
  iniciales y sólo se retienen identidades con SKU `[0-9]+` y nombre en mayúsculas.
- Categorías: únicamente las categorías en mayúsculas permanecen visibles; cuando un producto válido
  proviene de una categoría heredada se crea o reutiliza primero su equivalente canónico.
- Insumos: sólo se retienen SKU numéricos; `PLASTICOS Y DESECHABLES` se clasifica como empaque.
- Estaciones: bebidas usan `drinks`, servicios y vocabulario de empaque usan `packing`, y el resto
  usa `kitchen`.
- Alcance: productos, categorías e insumos retenidos quedan activos y corporativos. Clientes,
  almacenes, existencias y movimientos conservan el alcance de sucursal.
- Precio: no se inventa ni corrige. Un producto sin precio vigente positivo sigue disponible para
  revisión administrativa, pero no para cobro.

## Seguridad histórica y reversibilidad

La revisión `0027_catalog_cleanup` no elimina físicamente registros canónicos. Archiva los inválidos,
respalda cada campo mutado en `catalog_cleanup_records`, registra un resumen en
`catalog_cleanup_runs` y emite `catalog.cleanup.applied`. Esto conserva referencias de pedidos,
recetas, costos y movimientos.

El downgrade a `0026_ingredient_variations` restaura SKU, categoría, estación, estado, alcance y
excepciones de disponibilidad local. La prueba de integración ejecuta
`upgrade -> downgrade -> upgrade` sobre SQLite temporal y compara los conteos históricos.

## Trazabilidad

- Requisitos: PRD-FR-191, PRD-FR-192, PRD-FR-196 y PRD-FR-202.
- Escenarios: BDD-FEAT-061, BDD-SC-196 a BDD-SC-202.
- Pruebas: TDD-TS-062, TDD-TC-057 y `apps/api/tests/test_catalog_cleanup.py`.
- Operación: `docs/10-operacion-easypanel.md`, sección DATA-003.

## Evidencia local

- Política y migración reversible: aprobadas.
- Suite enfocada de catálogo, importación, migraciones, trazabilidad e invariantes dependientes:
  32 pruebas aprobadas.
- Suite completa final sobre el diff depurado: 163 pruebas aprobadas.
- Validación local del importador: 34,168 filas y checksum de manifiesto esperado, sin carga.
- `python3 -m ruff check apps/api tests`: sin hallazgos.
- `pnpm typecheck`: UI, Admin, POS y KDS aprobados; Node local 20.20.2 está por debajo del `>=22`
  declarado, mientras CI usa Node 22.
- `git diff --check`: limpio.
- Los Excel privados, `.zcode/` y las imágenes de WhatsApp permanecen fuera del cambio.

## Pendiente operativo

El estado es `Probado` localmente. Para declararlo implementado en producción falta respaldo,
redeploy, `alembic upgrade head`, confirmación de `0027_catalog_cleanup`, `/health/ready` y revisión
del resumen autenticado en `/api/v1/catalog/cleanup-status`.
