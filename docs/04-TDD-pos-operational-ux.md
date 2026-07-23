# TDD - POS operativo en español, clientes y domicilios

## TDD-TS-055 Experiencia operativa del POS

Casos:

- la búsqueda del checkout encuentra por teléfono exacto sin fusionar coincidencias,
- la búsqueda telefónica no fusiona clientes distintos,
- se conserva aislamiento por sucursal,
- `legacy_address_reference` sólo aparece para el cliente vinculado y `raw_payload` nunca se expone,
- sólo se devuelven domicilios con `status == "active"`,
- el POST de domicilio conserva auditoría y alcance,
- un pedido delivery rechaza una dirección de otro cliente,
- el cliente seleccionado se conserva aunque cambien los resultados,
- no quedan cadenas inglesas señaladas en `PointOfSale.tsx`,
- no queda `fetch()` directo para órdenes ni pagos en `PointOfSale.tsx`,
- la búsqueda de clientes usa `phone`, la sucursal canónica, debounce y `AbortController`,
- `Inventario` usa `session.active_branch.id` y consulta sólo `/inventory/stock`,
- no existe el umbral arbitrario `< 20` en Inventario,
- `Tables`, `Discount` y `Save Bill` no se renderizan.
- menú y accesos de productos se renderizan en franjas horizontales,
- complementos se renderizan debajo del catálogo y la cuenta permanece a la derecha.

## TDD-TC-048 El POS operativo respalda búsqueda, domicilios e inventario en español

Given un POS con sesión canónica y sucursal activa
When la prueba automatizada ejercita búsqueda, selección, domicilio e inventario
Then comprueba que la búsqueda del checkout usa el teléfono exacto
And comprueba que el cliente seleccionado se conserva
And comprueba que el domicilio heredado no se usa directamente para entrega
And comprueba que el inventario usa la sucursal canónica
And comprueba que no hay controles muertos ni cadenas inglesas.

## TDD-TC-064 Jerarquía visual del POS de venta rápida

Given la pantalla de Punto de Venta
When se inspecciona su estructura visible
Then existe un menú horizontal seguido por accesos a productos
And existe una zona inferior de complementos
And la cuenta se conserva como panel lateral derecho.

## TDD-TS-070 Navegación concentrada y categorías paginadas

Casos frontend:

- el menú lateral no contiene Panel Principal ni Inventario;
- Administración continúa condicionada por `branch.admin.access`;
- el centro de Administración contiene Inventario y enlaza a `/administration/inventory`;
- `/dashboard` redirige a `/pos` y `/inventory` a `/administration/inventory`;
- cinco o menos categorías no muestran controles de paginación;
- la primera página de un catálogo extenso termina con Siguiente;
- una página intermedia comienza con Regresar y termina con Siguiente;
- la última página comienza con Regresar y no muestra Siguiente;
- al cambiar de página se activa su primera categoría y los controles conservan nombre accesible.

## TDD-TC-066 Paginación visible del menú de productos

Given un POS con doce categorías
When el Cajero navega entre las páginas del menú superior
Then ninguna página presenta más de cinco categorías de producto
And Siguiente ocupa el último lugar mientras quedan categorías
And Regresar ocupa el primer lugar después de abandonar la primera página
And los productos corresponden a la primera categoría visible después de cada cambio.
