/** Closed operational contracts. Financial fields are never fabricated for legacy parsers. */
interface Projection { projection: 'operational'; schema_version: 2; policy_version: number }
export interface OperationalShift extends Projection {
  id: string; organization_id: string; branch_id: string; register_id: string;
  responsible_user_id: string | null; status: string; opened_at: string;
  closed_at: string | null; version: number; closure_id: string | null;
}
export interface OperationalCut extends Projection {
  id: string; organization_id: string; branch_id: string; register_id: string;
  cash_shift_id: string; responsible_user_id: string; capturer_user_id: string | null;
  status: string; version: number; created_at: string; counted_at: string | null;
  finalized_at: string | null;
}
export interface CashReceipt extends Projection {
  command_id: string; resource_id: string; action: string; status: string;
  version: number; accepted_at: string; replay: boolean; correlation_id: string;
}
export function cashRecord(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).sort().join('|') !== [...keys].sort().join('|')) throw new Error('Contrato de caja inválido.');
  return value as Record<string, unknown>;
}
const projectionKeys = ['projection','schema_version','policy_version'];
function operational(value: unknown, keys: string[], revision: number, strings: string[], nullable: string[]) {
  const row = cashRecord(value, [...projectionKeys, ...keys]);
  if (row.projection !== 'operational' || row.schema_version !== 2 || row.policy_version !== revision
    || !Number.isSafeInteger(revision) || revision < 1
    || !strings.every(key => typeof row[key] === 'string' && (row[key] as string).length > 0)
    || !nullable.every(key => row[key] === null || typeof row[key] === 'string')
    || !Number.isSafeInteger(row.version) || Number(row.version) < 1) throw new Error('Contrato de caja inválido.');
  return row;
}
export function parseOperationalShift(value: unknown, branch: string, revision: number): OperationalShift {
  const strings = ['id','organization_id','branch_id','register_id','status','opened_at'];
  const nullable = ['responsible_user_id','closed_at','closure_id'];
  const row = operational(value, [...strings,...nullable,'version'],revision,strings,nullable);
  if (row.branch_id !== branch || !['OPEN','OPERATIVELY_CLOSED'].includes(String(row.status))) throw new Error('Turno fuera de alcance.');
  return row as unknown as OperationalShift;
}
export function parseOperationalCut(value: unknown, branch: string, revision: number): OperationalCut {
  const strings = ['id','organization_id','branch_id','register_id','cash_shift_id','responsible_user_id','status','created_at'];
  const nullable = ['capturer_user_id','counted_at','finalized_at'];
  const row = operational(value, [...strings,...nullable,'version'],revision,strings,nullable);
  if (row.branch_id !== branch || !['DRAFT','COUNTED','FINALIZED'].includes(String(row.status))) throw new Error('Corte fuera de alcance.');
  return row as unknown as OperationalCut;
}
export function parseCashReceipt(value: unknown, revision: number, action: 'open'|'close', resource?: string): CashReceipt {
  const strings = ['command_id','resource_id','action','status','accepted_at','correlation_id'];
  const row = operational(value,[...strings,'version','replay'],revision,strings,[]);
  if (typeof row.replay !== 'boolean' || row.action !== action
    || row.status !== (action === 'open' ? 'OPEN' : 'OPERATIVELY_CLOSED')
    || (resource !== undefined && row.resource_id !== resource)) throw new Error('Acuse de caja inválido.');
  return row as unknown as CashReceipt;
}
export function parseOperationalCutPage(value: unknown, branch: string, revision: number) {
  const page = cashRecord(value,['items','next_cursor']);
  if (!Array.isArray(page.items) || !(page.next_cursor === null || typeof page.next_cursor === 'string')) throw new Error('Página de cortes inválida.');
  return {items:page.items.map(row => parseOperationalCut(row,branch,revision)),next_cursor:page.next_cursor as string|null};
}
