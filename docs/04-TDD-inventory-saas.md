# TDD - Inventario SaaS inicial

## TDD-TS-028 Inventory Ledger Minimal

Casos:

- listar insumos con unidad base,
- registrar movimiento `OPENING_BALANCE` con cantidad positiva,
- rechazar cantidades cero o negativas,
- conservar movimientos como apend-only,
- calcular existencia teorica desde movimientos,
- listar kardex por insumo y almacen,
- registrar auditoria del movimiento.

## TDD-TS-029 Recipe Read Model Minimal

Casos:

- listar recetas vigentes por producto,
- mostrar componentes con unidad base y cantidad exacta,
- mantener version de receta vigente.

## TDD-TS-030 Inventory Reservation Consumption

Casos:

- crear pedido registra `SALE_RESERVATION` por componente de receta,
- la cantidad reservada multiplica componente por cantidad vendida,
- completar tarea KDS registra `RESERVATION_RELEASE`,
- completar tarea KDS registra `SALE_CONSUMPTION`,
- la existencia teorica final no se descuenta dos veces,
- movimientos quedan vinculados a pedido o tarea.

## TDD-TS-031 Reservation Release Cancellation

Casos:

- cancelar pedido `ACCEPTED` con tarea `PENDING`,
- registrar `RESERVATION_RELEASE` por componente,
- marcar pedido como `CANCELLED`,
- marcar tareas pendientes como `CANCELLED`,
- rechazar cancelacion si la tarea ya inicio produccion,
- rechazar cancelacion si el pedido esta cerrado.

## TDD-TS-032 Post Production Cancellation

Casos:

- cancelar pedido `ACCEPTED` con tarea `COMPLETED`,
- exigir clasificacion `waste` o `recovery`,
- conservar movimientos `SALE_CONSUMPTION` historicos,
- registrar `WASTE` con delta cero cuando la produccion se pierde,
- registrar `RECOVERY` positivo cuando la produccion se recupera,
- rechazar pago posterior a cancelacion producida,
- registrar evento y auditoria con clasificacion.

## TDD-TC-021 Saldo inicial y kardex

Given existe un insumo `Carne molida`
When se registra un saldo inicial de `25000` gramos
Then `/api/v1/inventory/stock` devuelve existencia teorica de `25000`
And `/api/v1/inventory/kardex` muestra el movimiento `OPENING_BALANCE`.

## TDD-TC-022 Reserva y consumo desde POS/KDS

Given existe receta de `Hamburguesa Kiwi` con `120g` de carne
When se crea un pedido de dos hamburguesas
Then el kardex registra `SALE_RESERVATION` de `-240g`
When KDS completa la tarea
Then el kardex registra `RESERVATION_RELEASE` de `240g`
And registra `SALE_CONSUMPTION` de `-240g`
And la existencia teorica de carne queda en `24760g`.

## TDD-TC-023 Cancelacion libera reserva

Given existe un pedido aceptado de una hamburguesa
And su tarea KDS sigue pendiente
When se cancela el pedido
Then el kardex registra `RESERVATION_RELEASE` de `120g`
And la existencia teorica de carne vuelve a `25000g`.

## TDD-TC-024 Cancelacion posterior clasificada

Given existe un pedido aceptado de una hamburguesa
And su tarea KDS ya esta completada
When se cancela el pedido como `waste`
Then el kardex conserva `SALE_CONSUMPTION` de `-120g`
And registra `WASTE` de `0g`
And la existencia teorica permanece en `24880g`.

Given existe otro pedido producido
When se cancela el pedido como `recovery`
Then el kardex registra `RECOVERY` de `120g`
And la existencia teorica vuelve al nivel previo al pedido recuperado.
