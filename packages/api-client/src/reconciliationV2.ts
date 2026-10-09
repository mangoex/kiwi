export type ReportMoney = string;
export interface PhysicalCount {
  status: 'PENDING' | 'COUNTED' | 'EMPTY';
  counted_shift_ids: string[];
  pending_shift_ids: string[];
}
export interface ActivityTotals {
  total_sales_with_tax: ReportMoney;
  card_payments: ReportMoney;
  transfer_payments: ReportMoney;
  credit_sales: ReportMoney;
  cash_sales: ReportMoney;
  supplier_expenses: ReportMoney;
  fixed_expenses: ReportMoney;
  cash_withdrawals: ReportMoney;
  cash_deposits: ReportMoney;
}
export interface BalanceSummary extends ActivityTotals {
  initial_cash: ReportMoney;
  expected_cash_in_register: ReportMoney;
  physical_cash_count: ReportMoney | null;
  difference: ReportMoney | null;
}
interface SupplierRow { no: number; provider_name: string; amount: ReportMoney; observations: string }
interface FixedExpenseRow { no: number; expense_type: string; amount: ReportMoney; observations: string }
interface TransferRow { ticket_folio: string; customer_name: string; customer_phone: string; amount: ReportMoney }
interface WithdrawalRow { no: number; folio: string; amount: ReportMoney; recipient_name: string }
export interface DailyReconciliationData {
  contract_version: 2;
  branch_id: string;
  branch_name: string;
  date: string;
  population: { kind: 'shifts_opened'; shift_ids: string[]; frozen_shift_ids: string[]; timezone: string; from_utc: string; to_utc: string; breakdown_basis: 'verified_ledger' };
  physical_count: PhysicalCount;
  balance: BalanceSummary;
  activity: { kind: 'calendar_events'; totals: ActivityTotals };
  suppliers_breakdown: SupplierRow[];
  fixed_expenses_breakdown: FixedExpenseRow[];
  transfers_breakdown: TransferRow[];
  credit_clients_breakdown: TransferRow[];
  withdrawals_breakdown: WithdrawalRow[];
  audit: { reviewed: boolean; audited_by_user_id?: string | null; audited_at?: string | null; notes?: string | null };
}
export interface ConsolidatedReport {
  contract_version: 2;
  date_from: string;
  date_to: string;
  population: { kind: 'shifts_opened'; shift_ids: string[]; breakdown_basis: 'verified_ledger' };
  physical_count: PhysicalCount;
  activity: { kind: 'calendar_events'; totals: ActivityTotals };
  branches: { branch_id: string; branch_name: string; total_sales: ReportMoney; total_expenses: ReportMoney }[];
  supplier_totals: Record<string, ReportMoney>;
  fixed_expense_totals: Record<string, ReportMoney>;
  summary: {
    total_sales: ReportMoney; total_cards: ReportMoney; total_transfers: ReportMoney; total_credits: ReportMoney;
    total_suppliers: ReportMoney; total_fixed: ReportMoney; total_withdrawals: ReportMoney; total_expected_cash: ReportMoney;
    physical_cash_count: ReportMoney | null; difference: ReportMoney | null;
  };
}

function invalid(): never { throw new Error('Respuesta de conciliación incompatible o incompleta.'); }
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  return value as Record<string, unknown>;
}
function ids(value: unknown): string[] {
  if (!Array.isArray(value) || value.some(id => typeof id !== 'string') || new Set(value).size !== value.length) invalid();
  return value as string[];
}
function amounts(value: unknown, keys: string[]) {
  const data = record(value);
  for (const key of keys) if (typeof data[key] !== 'string' || !/^-?(0|[1-9]\d*)\.\d{2}$/.test(data[key] as string)) invalid();
}
function strings(value: unknown, keys: string[]) {
  const data = record(value);
  for (const key of keys) if (typeof data[key] !== 'string') invalid();
}
function rows(value: unknown, stringKeys: string[], moneyKeys: string[], numbered = false) {
  if (!Array.isArray(value)) invalid();
  for (const row of value) { strings(row, stringKeys); amounts(row, moneyKeys); if (numbered && (!Number.isInteger(record(row).no) || Number(record(row).no) < 1)) invalid(); }
}
const activityKeys = ['total_sales_with_tax', 'card_payments', 'transfer_payments', 'credit_sales', 'cash_sales', 'supplier_expenses', 'fixed_expenses', 'cash_withdrawals', 'cash_deposits'];
function validate(value: unknown, consolidated: boolean) {
  const data = record(value), population = record(data.population), activity = record(data.activity);
  if (data.contract_version !== 2 || population.kind !== 'shifts_opened' || population.breakdown_basis !== 'verified_ledger' || activity.kind !== 'calendar_events') invalid();
  const selected = ids(population.shift_ids), count = record(data.physical_count);
  const counted = ids(count.counted_shift_ids), pending = ids(count.pending_shift_ids);
  if (counted.length + pending.length !== selected.length || new Set([...counted, ...pending]).size !== selected.length || [...counted, ...pending].some(id => !selected.includes(id))) invalid();
  const status = pending.length ? 'PENDING' : counted.length ? 'COUNTED' : 'EMPTY';
  if (count.status !== status) invalid();
  const balance = record(consolidated ? data.summary : data.balance);
  const physical = balance.physical_cash_count, difference = balance.difference;
  if (status === 'COUNTED') {
    amounts(balance, ['physical_cash_count', 'difference']);
    if (reportMoneyCents(physical as string) < 0n) invalid();
  } else if (physical !== null || difference !== null) invalid();
  amounts(activity.totals, activityKeys);
  if (Object.keys(record(activity.totals)).some(key => !activityKeys.includes(key))) invalid();
  amounts(balance, consolidated
    ? ['total_sales', 'total_cards', 'total_transfers', 'total_credits', 'total_suppliers', 'total_fixed', 'total_withdrawals', 'total_expected_cash']
    : [...activityKeys, 'initial_cash', 'expected_cash_in_register']);
  if (consolidated) {
    strings(data, ['date_from', 'date_to']);
    rows(data.branches, ['branch_id', 'branch_name'], ['total_sales', 'total_expenses']);
    for (const key of ['supplier_totals', 'fixed_expense_totals']) {
      const totals = record(data[key]); amounts(totals, Object.keys(totals));
    }
  } else {
    strings(data, ['branch_id', 'branch_name', 'date']);
    strings(population, ['timezone', 'from_utc', 'to_utc']);
    if (!Number.isFinite(Date.parse(String(population.from_utc))) || !Number.isFinite(Date.parse(String(population.to_utc)))) invalid();
    if (ids(population.frozen_shift_ids).some(id => !selected.includes(id))) invalid();
    rows(data.suppliers_breakdown, ['provider_name', 'observations'], ['amount'], true);
    rows(data.fixed_expenses_breakdown, ['expense_type', 'observations'], ['amount'], true);
    rows(data.transfers_breakdown, ['ticket_folio', 'customer_name', 'customer_phone'], ['amount']);
    rows(data.credit_clients_breakdown, ['ticket_folio', 'customer_name', 'customer_phone'], ['amount']);
    rows(data.withdrawals_breakdown, ['folio', 'recipient_name'], ['amount'], true);
    if (typeof record(data.audit).reviewed !== 'boolean') invalid();
  }
}
export function parseDailyReconciliation(value: unknown): DailyReconciliationData {
  validate(value, false); return value as DailyReconciliationData;
}
export function parseConsolidatedReconciliation(value: unknown): ConsolidatedReport {
  validate(value, true); return value as ConsolidatedReport;
}
export function physicalCountLabel(count: PhysicalCount): string {
  return count.status === 'PENDING' ? 'Pendiente de arqueo' : count.status === 'EMPTY' ? 'Sin turnos' : 'Conteo completo';
}

export function reportMoneyCents(value: ReportMoney): bigint {
  if (!/^-?(0|[1-9]\d*)\.\d{2}$/.test(value)) invalid();
  const negative = value.startsWith('-');
  const [whole, fraction] = (negative ? value.slice(1) : value).split('.');
  const cents = BigInt(whole)*100n+BigInt(fraction);
  return negative ? -cents : cents;
}
export function sumReportMoney(values: ReportMoney[]): ReportMoney {
  const cents = values.reduce((sum, value) => sum+reportMoneyCents(value), 0n);
  const absolute = cents < 0n ? -cents : cents;
  return `${cents < 0n ? '-' : ''}${absolute/100n}.${String(absolute%100n).padStart(2, '0')}`;
}
export function formatReportMoney(value: ReportMoney): string {
  const cents = reportMoneyCents(value), absolute = cents < 0n ? -cents : cents;
  const parts = new Intl.NumberFormat('es-MX', {style: 'currency', currency: 'MXN'}).formatToParts(absolute/100n);
  return (cents < 0n ? '-' : '')+parts.map(part => part.type === 'fraction' ? String(absolute%100n).padStart(2,'0') : part.value).join('');
}
