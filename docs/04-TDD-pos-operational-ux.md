# TDD - POS operativo en español, clientes y domicilios

## TDD-TS-055 Experiencia operativa del POS

Casos:

- la búsqueda de clientes encuentra por nombre, correo y teléfono sin fusionar coincidencias,
- la búsqueda telefónica no fusiona clientes distintos,
- se conserva aislamiento por sucursal,
- `legacy_address_reference` sólo aparece para el cliente vinculado y `raw_payload` nunca se expone,
- sólo se devuelven domicilios con `status == "active"`,
- el POST de domicilio conserva auditoría y alcance,
- un pedido delivery rechaza una dirección de otro cliente,
- el cliente seleccionado se conserva aunque cambien los resultados,
- no quedan cadenas inglesas señaladas en `PointOfSale.tsx`,
- no queda `fetch()` directo para órdenes ni pagos en `PointOfSale.tsx`,
- la búsqueda de clientes usa `q`, debounce y `AbortController`,
- `Inventario` usa `session.active_branch.id` y consulta sólo `/inventory/stock`,
- no existe el umbral arbitrario `< 20` en Inventario,
- `Tables`, `Discount` y `Save Bill` no se renderizan.

## TDD-TC-048 El POS operativo respalda búsqueda, domicilios e inventario en español

Given un POS con sesión canónica y sucursal activa
When la prueba automatizada ejercita búsqueda, selección, domicilio e inventario
Then comprueba que la búsqueda cubre nombre, correo y teléfono
And comprueba que el cliente seleccionado se conserva
And comprueba que el domicilio heredado no se usa directamente para entrega
And comprueba que el inventario usa la sucursal canónica
And comprueba que no hay controles muertos ni cadenas inglesas.
