import {assertProjectionContract} from '@restaurantos/api-client';
import pageSchema from '../../../../../packages/contracts/schemas/purchase-receiving-page-v2.schema.json';
import receiptSchema from '../../../../../packages/contracts/schemas/purchase-receipt-operational-v2.schema.json';

export interface ReceivingLine {allocation_id:string;warehouse_id:string;item_id:string;item_name:string;presentation_id:string;presentation_name:string;presentation_quantity:string;received_quantity:string;pending_quantity:string}
export interface ReceivingOrder {id:string;folio:string;status:string;version:number;lines:ReceivingLine[]}
export interface ReceivingPage {projection:'operational';schema_version:2;policy_version:number;branch_id:string;items:ReceivingOrder[];next_cursor:string|null}
export function receivingRejectedBeforeEffects(error:{status:number;code:string;operationalIntentPending:boolean}):boolean {
  return !error.operationalIntentPending && (error.status===400 || error.status===422 || (error.status===409 && [
    'corporate_purchase_version_conflict','corporate_purchase_not_receivable','corporate_purchase_over_receipt',
    'corporate_purchase_difference_reason_required','corporate_purchase_destination_invalid',
    'corporate_purchase_quantity_below_base_precision',
  ].includes(error.code)));
}
export function parseReceivingPage(value:unknown,branch:string,revision:number):ReceivingPage {
  assertProjectionContract(value,pageSchema);const page=value as ReceivingPage;
  if(page.branch_id!==branch || page.policy_version!==revision)throw new Error('Recepción fuera de alcance.');
  return page;
}
export function parseReceivingReceipt(value:unknown,branch:string,revision:number,order:string):string {
  assertProjectionContract(value,receiptSchema);
  const data=value as {policy_version:number;receipt:{branch_id:string;order_id:string;id:string}};
  if(data.policy_version!==revision || data.receipt.branch_id!==branch || data.receipt.order_id!==order)throw new Error('Acuse fuera de alcance.');
  return data.receipt.id;
}
function micros(raw:string):bigint {
  if(!/^\d+(\.\d{1,6})?$/.test(raw))throw new Error('Cantidad inválida.');
  const [whole,fraction='']=raw.split('.');return BigInt(whole)*1000000n+BigInt(fraction.padEnd(6,'0'));
}
export function receivingLines(lines:ReceivingLine[],values:Record<string,string>) {
  return lines.flatMap(line=>{
    const raw=(values[line.allocation_id] || '').trim();if(!raw)return [];
    if(!/^\d+(\.\d{1,2})?$/.test(raw))throw new Error('Captura cantidades positivas con máximo dos decimales.');
    const value=micros(raw);if(value===0n)return [];
    if(value>micros(line.pending_quantity))throw new Error('La cantidad supera lo pendiente.');
    return [{allocation_id:line.allocation_id,quantity:raw}];
  });
}
