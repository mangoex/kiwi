import {assertProjectionContract,type DeliverySelection} from '@restaurantos/api-client';
import pageSchema from '../../../../../packages/contracts/schemas/operational-order-accounts-page-v2.schema.json';
import detailSchema from '../../../../../packages/contracts/schemas/attended-order-detail-v2.schema.json';

export interface OperationalOrder {
  id:string; folio:string;branch_id:string;cash_shift_id:string|null;register_code:string|null;
  status:string;service_type:string;created_at:string;customer_label:string|null;is_public_intent:boolean;version:number;
  schema_version:2;projection:'operational';policy_version:number;
}
export interface AttendedOrder {
  id:string;branch_id:string;folio:string;status:string;order_type:string;version:number;total_cents:number;
  schema_version:2;projection:'order';policy_version:number;payment_status:string;editable:boolean;edit_block_reason:string|null;
  payment_method_intent:string|null;customer_label:string|null;
  read_context:{order_version:number;authorization_version:number;source_kind:string;source_id:string};
  lines:{id:string;product_id:string;product_name:string;quantity:number;unit_price_cents:number;line_total_cents:number;station:string;line_notes:string|null;selected_modifiers:Record<string,unknown>[]}[];
  production_tasks:{id:string;order_line_id:string;status:string;quantity:number;product_name:string}[];
  delivery_charge:{state:string;charged_cents:number;tariff_name:string|null;selection:DeliverySelection}|null;
}
export function parseOperationalOrders(value:unknown,branch:string,revision:number) {
  assertProjectionContract(value,pageSchema);
  const page=value as {items:OperationalOrder[];next_cursor:string|null};
  if(page.items.some(row=>row.branch_id!==branch || row.policy_version!==revision || row.version<1)) throw new Error('Pedido fuera de alcance.');
  return page;
}
export function parseAttendedOrder(value:unknown,branch:string,revision:number,id:string,version:number,authorityVersion:number):AttendedOrder {
  assertProjectionContract(value,detailSchema);
  const row=value as AttendedOrder;
  if(row.branch_id!==branch || row.policy_version!==revision || row.id!==id || row.version!==version
    || row.read_context.order_version!==version || row.read_context.authorization_version!==authorityVersion) throw new Error('El contexto del pedido cambió.');
  return row;
}
