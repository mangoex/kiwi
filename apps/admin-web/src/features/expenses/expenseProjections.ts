import {assertProjectionContract} from '@restaurantos/api-client';
import pageSchema from '../../../../../packages/contracts/schemas/expense-operational-page-v2.schema.json';
import draftSchema from '../../../../../packages/contracts/schemas/expense-draft-v2.schema.json';
import receiptSchema from '../../../../../packages/contracts/schemas/expense-command-receipt-v2.schema.json';
import type {ExpenseDocument} from '../../../../../packages/contracts/operating-expenses-v1';
export type ExpenseMetadata=Pick<ExpenseDocument,'id'|'branch_id'|'concept_id'|'document_date'|'payment_method'|'status'|'version'> & {created_by:string};
export type ExpenseDetail=Omit<ExpenseDocument,'confirmed_at'|'cash_movement_id'|'compensation_movement_id'|'cancellation_reason'> & Partial<Pick<ExpenseDocument,'cancellation_reason'>>;
export interface ExpenseReceipt {projection:'operational';policy_version:number;id:string;branch_id:string;status:string;version:number|null}
export function expensePage(value:unknown,branch:string,revision:number) {
  assertProjectionContract(value,pageSchema);const page=value as {policy_version:number;items:ExpenseMetadata[];next_cursor:string|null};
  if(page.policy_version!==revision || page.items.some(row=>row.branch_id!==branch))throw new Error('Gastos fuera de alcance.');return page;
}
export function expenseDraft(value:unknown,branch:string,revision:number,id:string,version:number):ExpenseDetail {
  assertProjectionContract(value,draftSchema);const row=value as ExpenseDetail & {policy_version:number};
  if(row.policy_version!==revision || row.branch_id!==branch || row.id!==id || row.version!==version)throw new Error('El borrador cambió.');return row;
}
export function expenseReceipt(value:unknown,branch:string,revision:number):ExpenseReceipt {
  assertProjectionContract(value,receiptSchema);const row=value as ExpenseReceipt;
  if(row.policy_version!==revision || row.branch_id!==branch)throw new Error('Acuse fuera de alcance.');return row;
}
