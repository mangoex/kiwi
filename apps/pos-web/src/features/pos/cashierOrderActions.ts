/** Presentation of existing transitions only; domain revalidates permission, tasks and state. */
export interface ActionOrder {
  status: string;
  service_type: string | null;
  payment_status?: string;
  lines: Array<{ id: string }>;
  production_tasks: Array<{ order_line_id: string; status: string }>;
}
export function cashierOrderActions(order: ActionOrder, permissions: ReadonlySet<string>) {
  let fulfillment: { command: 'start_delivery' | 'deliver' | 'close'; label: string } | null = null;
  if (permissions.has('orders.fulfill')) {
    if (order.status === 'READY') fulfillment = order.service_type === 'delivery'
      ? { command: 'start_delivery', label: 'Despachar a domicilio' }
      : ['dine-in', 'takeout'].includes(order.service_type || '') ? { command: 'deliver', label: 'Entregar en caja' } : null;
    if (order.status === 'IN_DELIVERY' && order.service_type === 'delivery') fulfillment = { command: 'deliver', label: 'Confirmar entrega' };
    if (['DELIVERED', 'RETURNED'].includes(order.status)) fulfillment = { command: 'close', label: 'Cerrar pedido' };
  }
  const active = new Set(order.lines.map((line) => line.id));
  const tasks = order.production_tasks.filter((task) => active.has(task.order_line_id));
  let cancellation: 'reservation_release' | 'classification_required' | null = null;
  if (permissions.has('orders.cancel') && order.payment_status !== 'CONFIRMED'
    && ['ACCEPTED', 'IN_PRODUCTION', 'READY'].includes(order.status)) {
    if (tasks.every((task) => task.status === 'PENDING')) cancellation = 'reservation_release';
    else if (tasks.length && tasks.every((task) => task.status === 'COMPLETED')) cancellation = 'classification_required';
  }
  return { fulfillment, cancellation };
}
