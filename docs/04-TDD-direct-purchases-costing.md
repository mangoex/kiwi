# TDD - Compras directas, caja y costo promedio

## TDD-TS-041 Compra, recepción, caja y costeo

Casos:

- crear compra en borrador con documento y renglones convertidos;
- recalcular subtotal, descuento, impuestos y total en backend;
- impedir flete u otros gastos mientras no exista política aprobada;
- confirmar con `purchases.manage`, turno abierto y `cash.withdraw` cuando usa caja;
- crear un solo retiro vinculado y una entrada por renglón;
- calcular costo promedio ponderado con existencias positiva y cero;
- excluir reservas de venta del saldo físico usado para costeo;
- rechazar existencia negativa sin producir efectos parciales;
- devolver el mismo resultado ante reintento con idempotency key;
- cancelar con contramovimientos, sin editar ni eliminar originales;
- auditar actor, sucursal, documento, motivo y referencias;
- aplicar y revertir migración conservando movimientos anteriores;
- probar precisión Decimal y ausencia de `float` en dominio.

## TDD-TC-034 Compra desde caja y promedio

Given existen 10 kg de azúcar a 20 pesos por kg
And existe un turno de caja abierto
When el supervisor confirma 10 kg a 30 pesos por kg pagados desde caja
Then crea un retiro por el total una sola vez
And crea una recepción por 10 kg
And el costo promedio queda en 25 pesos por kg.
