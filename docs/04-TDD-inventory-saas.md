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

## TDD-TC-021 Saldo inicial y kardex

Given existe un insumo `Carne molida`  
When se registra un saldo inicial de `25000` gramos  
Then `/api/v1/inventory/stock` devuelve existencia teorica de `25000`  
And `/api/v1/inventory/kardex` muestra el movimiento `OPENING_BALANCE`.
