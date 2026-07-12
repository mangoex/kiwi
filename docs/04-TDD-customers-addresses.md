# TDD - Clientes, teléfonos y direcciones

## TDD-TS-039 Directorio y snapshots de pedidos

Casos:

- crear cliente con ID interno y sucursal de origen;
- normalizar teléfono mexicano sin perder el valor capturado;
- permitir la misma coincidencia telefónica en más de un cliente sin fusionarlos;
- buscar clientes por teléfono normalizado;
- agregar direcciones ilimitadas y mantener una sola predeterminada;
- mantener datos fiscales separados de domicilios;
- crear y actualizar el perfil fiscal sin modificar domicilios;
- listar en POS el teléfono principal, domicilios y presencia de datos fiscales;
- seleccionar cliente y domicilio al crear un pedido `delivery` desde POS;
- exigir que la dirección seleccionada pertenezca al cliente;
- exigir dirección en pedidos de tipo `delivery` con cliente;
- guardar snapshots JSON al aceptar el pedido;
- conservar snapshots después de modificar la dirección;
- resumir última compra, frecuencia, ticket promedio y productos frecuentes;
- repetir un pedido creando otra orden con catálogo, precio, receta y domicilio vigentes;
- rechazar la repetición cuando un producto o domicilio ya no está disponible;
- rechazar escritura sin `orders.create` o fuera del alcance de sucursal;
- aplicar y revertir la migración sin perder los clientes existentes.

## TDD-TC-032 Cliente con domicilios y snapshot

Given un cajero autorizado registra un cliente y los domicilios Casa, Oficina y Escuela
When crea un pedido delivery usando Casa
Then el pedido guarda `customer_id`, `customer_snapshot` y `delivery_address_snapshot`
And modificar Casa no cambia los snapshots guardados.
