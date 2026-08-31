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

## TDD-TS-070 Navegación concentrada y categorías agrupadas

Casos frontend:

- el menú lateral no contiene Panel Principal ni Inventario;
- Administración continúa condicionada por `branch.admin.access`;
- el centro de Administración contiene Inventario y enlaza a `/administration/inventory`;
- `/dashboard` redirige a `/pos` y `/inventory` a `/administration/inventory`;
- la franja superior presenta exactamente Todo, Alimentos, Bebidas, Otros y Favoritos;
- Todo proyecta todas las categorías concretas con productos elegibles;
- Alimentos, Bebidas y Otros filtran por `kitchen`, `drinks` y las estaciones restantes;
- Favoritos proyecta directamente sólo productos concretos elegibles cuyos `product_id` marcó el
  usuario en ese navegador, sin modelar categorías favoritas;
- una categoría sin productos activos/disponibles queda fuera del panel intermedio;
- las tarjetas intermedias conservan icono, tamaño táctil, nombre accesible y foco visible;
- no existen controles Siguiente o Regresar;
- cambiar de grupo conserva búsqueda y carrito, y limpia la personalización transitoria;
- si la categoría activa deja de existir en la proyección, se vuelve al agregado del grupo;
- los productos corresponden al grupo o categoría concreta seleccionada.

## TDD-TC-066 Proyección agrupada del menú de productos

Given un POS con productos de cocina, bebidas y otras estaciones
When el Cajero abre el menú superior
Then aparecen exactamente los cinco grupos operativos
And Todo muestra todas las categorías elegibles en el panel intermedio
When cambia entre Alimentos, Bebidas y Otros
Then cambian las categorías y productos según la estación
When marca y desmarca un producto concreto favorito
Then Favoritos refleja directamente sólo los productos elegibles marcados en ese navegador
And no muestra categorías antes de esos productos
And las tarjetas del panel intermedio conservan iconos y una altura táctil mínima
And no se muestran controles de paginación
And búsqueda y carrito se conservan al cambiar de grupo.
