export type OperationalPeriod = 'day'|'week'|'month';
export interface OperationalReport {
  projection:'operational'; schema_version:2; policy_version:number;
  branch_id:string; period:OperationalPeriod; start:string; end:string; timezone:string;
  ticket_count:number; top_products:{position:number;name:string}[];
}
const exact = (value:unknown, keys:string[]):value is Record<string,unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).sort().join('|') === keys.sort().join('|');
export function parseOperationalReport(value:unknown, branch:string, revision:number, period:OperationalPeriod):OperationalReport {
  if(!exact(value,['projection','schema_version','policy_version','branch_id','period','start','end','timezone','ticket_count','top_products'])
    || value.projection !== 'operational' || value.schema_version !== 2 || value.policy_version !== revision
    || value.branch_id !== branch || value.period !== period || !Number.isSafeInteger(revision) || revision < 1
    || !Number.isSafeInteger(value.ticket_count) || Number(value.ticket_count) < 0
    || typeof value.start !== 'string' || !Number.isFinite(Date.parse(value.start))
    || typeof value.end !== 'string' || !Number.isFinite(Date.parse(value.end)) || Date.parse(value.start) >= Date.parse(value.end)
    || typeof value.timezone !== 'string' || !value.timezone
    || !Array.isArray(value.top_products) || value.top_products.length > 10
    || value.top_products.some((row,index) => !exact(row,['position','name']) || row.position !== index+1
      || typeof row.name !== 'string' || !row.name.trim())) throw new Error('Reporte fuera del contrato autorizado.');
  return value as unknown as OperationalReport;
}
