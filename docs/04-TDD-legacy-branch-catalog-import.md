# TDD - Importación de catálogos heredados por sucursal

## TDD-TS-053 Lotes, alcance y revisión de datos heredados

Casos:

- la migración `0025_legacy_branch_catalog_import` crea tablas de lote y fila con llaves idempotentes y agrega alcance explícito a productos e insumos;
- upgrade, downgrade y upgrade conservan una sola head y funcionan en SQLite de prueba;
- un manifiesto repetido devuelve el mismo lote;
- un chunk repetido no duplica fila, cliente, insumo, producto ni precio;
- productos sin estación quedan `needs_review` y no aparecen en el catálogo vendible;
- los costos heredados sólo se conservan en el payload de importación;
- presentaciones sin proveedor y recetas sin componentes no crean registros operativos incompletos;
- clientes e insumos se filtran por sucursal autorizada;
- el directorio de clientes usa una consulta paginada y agregados por lote, no N+1;
- un actor de otra sucursal recibe 403 o una colección sin registros fuera de alcance;
- toda mutación de revisión registra auditoría.

## TDD-TC-046 Importación Constitución idempotente y aislada

Given un conjunto representativo de las cinco fuentes de Constitución
When se crea el lote, se cargan dos veces los mismos chunks y se finaliza
Then existe un solo destino por clave de fuente
And productos sin estación, presentaciones sin proveedor y recetas inválidas permanecen en revisión
And clientes e insumos son visibles en Constitución pero no en otra sucursal
And no existen movimientos de inventario generados por los costos heredados.
