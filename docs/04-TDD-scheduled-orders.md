# TDD - Pedidos programados en Caja

## TDD-TS-149 Ciclo de vida de pedidos programados

Casos:

- la migración `0107_scheduled_orders` agrega `scheduled_for`, `scheduled_released_at` y `scheduled_released_by_user_id` a `orders`, `scheduled_for` a `public_order_intents`, actualiza `ck_orders_cash_shift_required_except_public_intent` para permitir `status = 'SCHEDULED'` con `cash_shift_id IS NULL`, y es reversible;
- `POST /orders` con `scheduled_for` válido y teléfono crea una orden `SCHEDULED` sin `cash_shift_id`, sin `production_tasks` y sin movimientos `SALE_RESERVATION`;
- `POST /orders` con `scheduled_for` sin teléfono falla con `scheduled_order_phone_required`;
- `POST /orders` con `scheduled_for` en día cerrado o fuera de horario de la sucursal falla con `branch_closed_at_scheduled_time`;
- `GET /pos/pending-orders-count` devuelve `scheduled_count` y `scheduled_due_count` con ventana de 30 minutos;
- `POST /orders/{id}/release-scheduled` exige turno de caja abierto, transiciona `SCHEDULED -> ACCEPTED`, asigna `cash_shift_id`, crea `production_tasks` y registra `SALE_RESERVATION`;
- `PATCH /orders/{id}/schedule` revalida el horario de la sucursal y actualiza `scheduled_for`;
- `POST /orders/{id}/cancel` cancela un pedido `SCHEDULED` sin movimientos de merma ni inventario.
