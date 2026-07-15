# TDD - Depuración y catálogo corporativo compartido

## TDD-TS-062 Migración reversible y política canónica de catálogos

Casos:

- la política considera numérico sólo `[0-9]+`, elimina comillas iniciales de productos y conserva
  ceros iniciales;
- creación, actualización e importación rechazan SKU, nombre de producto o categoría fuera de la
  política canónica;
- la migración archiva insumos no numéricos y categorías no mayúsculas sin tocar movimientos,
  existencias ni costos;
- productos con SKU no numérico o nombre no mayúsculo quedan archivados; colisiones normalizadas
  conservan una sola identidad canónica;
- categorías mayúsculas equivalentes se reutilizan o crean antes de reasignar productos válidos;
- bebidas, comida y empaques reciben `drinks`, `kitchen` y `packing` según la tabla documentada;
- productos e insumos válidos quedan activos, `organization` y sin `source_branch_id`;
- las excepciones locales de productos válidos se respaldan y eliminan para heredar disponibilidad;
- productos sin precio positivo siguen visibles en administración, no en el menú cobrable;
- productos resueltos actualizan sus filas y resumen de importación sin resolver presentaciones ni
  recetas incompletas;
- `catalog_cleanup_runs`, `catalog_cleanup_records` y `catalog.cleanup.applied` conservan resumen y
  valores previos sin datos privados;
- downgrade restaura exactamente los campos mutados y las excepciones locales, y upgrade puede
  ejecutarse otra vez en SQLite y PostgreSQL;
- el endpoint de estado requiere `catalog.manage` y sólo devuelve conteos.

## TDD-TC-057 Depuración de Constitución y visibilidad entre sucursales

Given una base en `0026_ingredient_variations` con datos válidos de Constitución y registros legacy
When se ejecuta `alembic upgrade head`
Then `01001`, `02001` y `13001` quedan activos, corporativos y en estaciones de bebidas, cocina y empaque
And los SKU no numéricos, nombres no mayúsculos y categorías no mayúsculas quedan archivados
And el catálogo válido aparece en una segunda sucursal sin una excepción local heredada
And inventario, costos, pedidos y snapshots históricos conservan sus conteos y valores
When se ejecuta `alembic downgrade 0026_ingredient_variations`
Then los valores previos y la excepción local quedan restaurados.
