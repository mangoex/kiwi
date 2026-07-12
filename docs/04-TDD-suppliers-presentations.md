# TDD - Proveedores y presentaciones de compra

## TDD-TS-040 Proveedores, contactos y presentaciones

Casos:

- crear proveedor central con código y RFC no duplicados;
- agregar múltiples contactos y banderas principales por función;
- configurar disponibilidad y condiciones por sucursal;
- crear presentación ligada a proveedor, artículo y unidad comercial;
- exigir rendimiento y contenido aprovechable positivos;
- calcular precio por unidad base con `Decimal` y redondeo documentado;
- registrar historial inmutable al capturar o cambiar precio;
- no crear movimientos ni actualizar costo promedio al editar una presentación;
- rechazar unidad base distinta a la del artículo sin equivalencia autorizada;
- aplicar y revertir la migración conservando catálogos previos;
- restringir escritura a `catalog.manage` y lectura operativa a permisos autorizados.

## TDD-TC-033 Presentación de azúcar

Given azúcar tiene kilogramo como unidad base
When el administrador registra una bolsa de 10 kg a 280 pesos netos
Then `cost_per_base_unit` es 28
And existe una entrada en historial de precios
And no existe un movimiento de inventario por esa captura.
