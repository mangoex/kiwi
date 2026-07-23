# TDD - Asignación de repartidor desde el POS

## TDD-TS-072 Asignación y registro de entrega

Pruebas de dominio, API y migración:

- `0031_delivery_assignments` crea una tabla inmutable enlazada a pedido, repartidor, cliente,
  sucursal y actor;
- el downgrade funciona sin asignaciones y se bloquea cuando eliminaría registros;
- la lectura disponible exige `orders.create`, alcance de sucursal, estado activo y coincidencia de
  sucursal;
- `driver_id` se rechaza para pedidos que no son `delivery`;
- un repartidor inexistente, inactivo o de otra sucursal revierte pedido, movimientos y tareas;
- una asignación válida congela nombres, domicilio, total, moneda, líneas y unidades;
- detalle y lista de pedidos exponen la asignación;
- historial por repartidor exige `admin.manage` y conserva registros aunque el repartidor esté
  inactivo.

Pruebas frontend:

- Cobrar pedido no contiene un segundo selector de tipo de pedido;
- Asignar repartidor sólo aparece cuando `orderType === 'delivery'`;
- el selector consulta `/delivery/drivers/available` con la sucursal canónica;
- se muestran carga, error, vacío, selección y cambio de repartidor;
- el pedido envía `driver_id` sólo para entrega a domicilio;
- Administración abre el historial del repartidor y muestra folio, cliente, importe y cantidades.

## TDD-TC-068 Pedido y asignación se confirman atómicamente

Given un pedido delivery y un repartidor activo de la sucursal autorizada
When el Cajero crea el pedido con driver_id
Then existe una sola asignación ligada al pedido con snapshots y cantidades correctas
And el historial administrativo la devuelve para ese repartidor
And un repartidor ajeno o inactivo no deja pedido, reserva, tarea ni asignación parcial.
