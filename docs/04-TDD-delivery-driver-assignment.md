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
- aceptar una intención pública con `driver_id` crea pedido y asignación atómicamente, y un conductor
  inválido no deja pedido, reserva, tarea, evento ni asignación parcial;
- el comando idempotente conserva sólo la referencia de asignación, no duplica PII, y la primera
  respuesta y el replay exacto se rehidratan desde la fila inmutable;
- `PUT /orders/{order_id}/delivery-assignment` bloquea el pedido y sólo crea su primera asignación en
  estados previos al despacho; repetir el mismo conductor devuelve la misma fila y otro falla;
- PostgreSQL serializa tanto la primera asignación competida como la baja o cambio concurrente del
  repartidor; después de adquirir el bloqueo se vuelve a exigir que siga activo y en la sucursal;
- CI crea una base aislada `delivery_assignment_*`, exporta
  `DELIVERY_ASSIGNMENT_TEST_POSTGRES_URL` y rechaza el paquete si esos casos se omiten o saltan;
- después de migrar, la fixture vacía las tablas de datos sólo dentro de esa base local validada,
  conserva `alembic_version` y aplica `_seed` una vez, sin duplicar la organización bootstrap;
  CI ejecuta primero estos tres casos focales y después conserva la suite completa;
- detalle y lista de pedidos exponen la asignación;
- historial por repartidor exige `admin.manage` y conserva registros aunque el repartidor esté
  inactivo.

Pruebas frontend:

- Cobrar pedido no contiene un segundo selector de tipo de pedido;
- Asignar repartidor sólo aparece cuando `orderType === 'delivery'`;
- el selector consulta `/delivery/drivers/available` con la sucursal canónica;
- se muestran carga, error, vacío, selección y cambio de repartidor;
- el pedido envía `driver_id` sólo para entrega a domicilio;
- Pedidos permite seleccionar repartidor al aceptar una intención web y recuperar un pedido delivery
  aceptado sin asignación, mostrando carga, vacío, error y resultado confirmado;
- un pedido operacional `PENDING` que no es intención pública no ofrece selección durante aceptación;
  después de quedar `ACCEPTED` usa el flujo de primera asignación;
- Administración abre el historial del repartidor y muestra folio, cliente, importe y cantidades.

## TDD-TC-068 Pedido y asignación se confirman atómicamente

Given un pedido delivery y un repartidor activo de la sucursal autorizada
When el Cajero crea el pedido con driver_id
Then existe una sola asignación ligada al pedido con snapshots y cantidades correctas
And el historial administrativo la devuelve para ese repartidor
And un repartidor ajeno o inactivo no deja pedido, reserva, tarea ni asignación parcial.

## TDD-TC-430 Aceptación pública y asignación son atómicas

Given una intención pública delivery y un repartidor activo de su sucursal
When el Cajero acepta con `driver_id`
Then existe exactamente un pedido y una asignación con snapshots completos
And el replay devuelve el mismo resultado
And el endpoint de aceptación usado por el POS conserva la versión original para ese replay
And un repartidor no disponible deja la intención pendiente sin efectos operativos.

## TDD-TC-431 Primera asignación posterior no reescribe historia

Given un pedido delivery aceptado sin asignación
When el Cajero ejecuta dos veces la misma asignación
Then ambas respuestas identifican una sola fila, un evento y una auditoría
And un conductor distinto, otra sucursal, un pedido no delivery o un estado ya despachado falla
cerrado sin modificar la asignación existente.

## TDD-TC-432 Estado concurrente del repartidor falla cerrado

Given una baja o cambio de sucursal del repartidor mantiene bloqueada su fila en PostgreSQL
When otro proceso intenta crear la primera asignación para ese repartidor
Then la asignación espera la resolución concurrente y revalida la fila bloqueada
And si el repartidor queda inactivo o ajeno no crea asignación, evento ni auditoría.

## TDD-TC-433 Asignación y despacho conservan el orden global de bloqueos

Given una transacción de despacho conserva el fence de sucursal de un pedido `READY`
When compite con la primera asignación del mismo pedido
Then la asignación espera sin retener primero el pedido
And el despacho confirma sin deadlock
And la asignación posterior falla por estado sin crear historia parcial.
