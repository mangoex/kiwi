# TDD - Pago, corte e impresion simulada

## TDD-TS-020 Payments Minimal

Casos:

- registrar pago en efectivo por el total exacto,
- rechazar pago sin pedido existente,
- rechazar pago por importe distinto al total,
- rechazar pago duplicado sobre pedido cerrado,
- cerrar pedido al confirmar pago,
- registrar eventos `PAYMENT_CONFIRMED` y `ORDER_CLOSED`.

## TDD-TS-021 Cash Cut Minimal

Casos:

- resumir ventas del turno abierto,
- calcular efectivo esperado como fondo inicial mas pagos en efectivo,
- cerrar turno con efectivo contado,
- calcular diferencia de corte,
- crear registro de corte final,
- rechazar corte cuando no existe turno abierto.

## TDD-TS-022 Print Jobs Minimal

Casos:

- crear ticket simulado al confirmar pago,
- crear comanda simulada al confirmar pago,
- listar trabajos de impresion,
- reintentar trabajo pendiente,
- marcar trabajo como impreso en simulacion,
- registrar intento de impresion en auditoria.

## TDD-TC-013 Venta cobrada con corte e impresion

Given existe turno abierto  
And existe catalogo minimo  
When se crea un pedido desde POS  
And se cobra en efectivo por el total exacto  
Then el pedido queda cerrado  
And el pago queda confirmado  
And existen trabajos de impresion para ticket y comanda  
And el corte de caja calcula efectivo esperado.
