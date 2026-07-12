# TDD - Traspasos entre sucursales

## TDD-TS-045 Envío, tránsito y recepción

Casos:

- rechazar origen igual a destino, sucursal inactiva, artículo inválido o cantidad no positiva;
- crear borrador multi-línea sin movimientos;
- limitar creación y envío a `inventory.transfer.send` en origen;
- cancelar únicamente borradores sin movimientos;
- validar todas las existencias antes de confirmar para evitar efectos parciales;
- congelar costo promedio y costo total de origen por línea;
- crear `TRANSFER_OUT` y actualizar estado de costo de origen;
- repetir envío con la misma clave sin duplicar y rechazar una clave distinta;
- limitar recepción a `inventory.transfer.receive` en destino;
- rechazar cantidad recibida negativa o superior a enviada;
- exigir motivo cuando exista diferencia;
- crear `TRANSFER_IN` solo por la cantidad recibida;
- incorporar costo transferido al promedio ponderado del destino;
- conservar cantidad y costo en tránsito y de diferencia;
- repetir recepción con la misma clave sin duplicar;
- distinguir recepción completa y con diferencia;
- aplicar y revertir migración conservando movimientos existentes.

## TDD-TC-038 Recepción parcial valorizada

Given origen envía 10 kg a 25 pesos por kg
When destino recibe 9.5 kg y reporta 0.5 kg dañados
Then origen contiene TRANSFER_OUT por -10 kg y -250 pesos
And destino contiene TRANSFER_IN por 9.5 kg y 237.50 pesos
And el tránsito se cierra con diferencia de 0.5 kg y 12.50 pesos
And ninguno de los movimientos se clasifica como compra.
