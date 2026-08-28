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

## TDD-TS-070 Navegación concentrada y categorías a todo el ancho

Casos frontend:

- el menú lateral no contiene Panel Principal ni Inventario;
- Administración continúa condicionada por `branch.admin.access`;
- el centro de Administración contiene Inventario y enlaza a `/administration/inventory`;
- `/dashboard` redirige a `/pos` y `/inventory` a `/administration/inventory`;
- las categorías con productos disponibles ocupan una cuadrícula adaptable a todo el ancho;
- una categoría sin productos activos/disponibles queda fuera de la navegación;
- Todo el menú queda fuera si no existe ningún producto disponible;
- no existen controles Siguiente o Regresar;
- si la categoría activa deja de existir en la proyección, se activa la primera visible;
- las opciones o productos de la categoría activa permanecen inmediatamente debajo.

## TDD-TC-066 Proyección visible del menú de productos

Given un POS con categorías que tienen y no tienen productos disponibles
When el Cajero abre el menú superior
Then sólo aparecen Todo el menú y las categorías con al menos un producto elegible
And los controles ocupan todo el ancho y fluyen a nuevas filas cuando es necesario
And no se muestran controles de paginación
And las opciones o productos corresponden a la categoría visible seleccionada.
