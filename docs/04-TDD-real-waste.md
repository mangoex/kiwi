# TDD - Merma real

## TDD-TS-044 Documentos y movimientos de merma

Casos:

- sembrar motivos configurables sin duplicarlos;
- crear borrador con cantidad Decimal, unidad base, etapa, evidencia y fecha;
- rechazar motivo o artículo inactivo, unidad incompatible y cantidad no positiva;
- comprobar que el borrador no genera movimientos;
- limitar lectura y escritura al alcance de sucursal del actor;
- confirmar solo con `inventory.waste` e idempotency key;
- rechazar existencia insuficiente sin persistencia parcial;
- congelar costo promedio, costo total, capturista y autorizador;
- crear exactamente un `WASTE_REAL` negativo y actualizar estado de costo;
- repetir confirmación con la misma clave sin duplicar;
- rechazar segunda confirmación con clave distinta;
- revertir mediante `WASTE_REVERSAL` positivo y `reversal_of_id`;
- exigir motivo de reversa y preservar ambos movimientos;
- repetir reversa idempotentemente;
- conservar costo promedio unitario al confirmar y revertir;
- aplicar y revertir migración sin afectar el kardex existente.

## TDD-TC-037 Merma y reversa inmutables

Given una sucursal tiene 10 kg con costo promedio de 25 pesos
When confirma una merma de 2 kg
Then existe WASTE_REAL por -2 kg y -50 pesos
And quedan 8 kg al mismo costo promedio
When revierte la merma
Then existe WASTE_REVERSAL por 2 kg y 50 pesos referenciado
And vuelven a existir 10 kg al costo promedio de 25 pesos.
