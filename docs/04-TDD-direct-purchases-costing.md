# TDD - Compras directas, caja y costo promedio

## TDD-TS-041 Compra, recepción, caja y costeo

Casos:

- crear compra en borrador con documento y renglones convertidos;
- recalcular subtotal, descuento, impuestos y total en backend;
- impedir flete u otros gastos mientras no exista política aprobada;
- confirmar con `purchases.manage`, turno abierto y `cash.withdraw` cuando usa caja;
- crear un solo retiro vinculado y una entrada por renglón;
- calcular costo promedio ponderado con existencias positiva y cero;
- mostrar el precio de presentación antes de descuento sin llamarlo precio neto;
- aclarar que el costo de inventario excluye impuesto y se presenta por sucursal/almacén;
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

## TDD-TC-212 Payload de confirmación distingue efectivo y otros métodos

- Archivo: `tests/frontend/test_pos_purchases_and_reprint.mjs`
- Backend: `apps/api/tests/test_branch_purchases_and_courtesies.py`

Given borradores equivalentes en Administración corporativa y Administración de sucursal
When se confirma una compra `paid_from_cash=true`
Then ambas UI exigen `pos_register_id` no vacío y envían `register_id` junto con una clave idempotente
estable hasta éxito. Para `paid_from_cash=false` envían un body sin `register_id`; el backend confirma
la recepción sin crear retiro. La prueba API conserva el caso negativo de efectivo sin caja/turno y
la atomicidad de inventario, costo y ledger.
