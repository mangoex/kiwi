export type UserCashCutState = 'loading' | 'empty' | 'ready' | 'counting' | 'finalizing' | 'conflict' | 'error';

export interface UserCashCutView {
  id: string; organization_id: string; branch_id: string; cash_shift_id: string; cashier_user_id: string;
  register_code_snapshot: string; period_start: string; period_end: string;
  timezone: string; created_by_user_id: string; finalized_by_user_id: string | null;
  status: 'DRAFT' | 'COUNTED' | 'FINALIZED'; opening_cash_cents: number;
  cash_payment_cents: number | null; deposit_cents: number | null; withdrawal_cents: number | null;
  expected_cash_cents: number | null; counted_cash_cents: number | null;
  difference_cents: number | null; tolerance_cents: number; version: number;
  created_at: string; counted_at: string | null; finalized_at: string | null;
}

export interface UserCashCutCreatePayload {
  branch_id: string;
  register_id: string;
  cash_shift_id: string;
  cashier_user_id: string;
  period_start: string;
  period_end: string;
}

export interface UserCashCutCountedPayload {
  counted_cash_cents: number;
  version: number;
}

export interface UserCashCutFinalizePayload {
  version: number;
}

export interface UserCashCutReopenRequestPayload {
  counted_cash_cents: number;
  reason: string;
  evidence_refs: string[];
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const integer = (value: unknown): value is number => Number.isSafeInteger(value);
const exact = (value: Record<string, unknown>, keys: string[]) => {
  if (Object.keys(value).sort().join('|') !== [...keys].sort().join('|')) throw new Error('Respuesta de corte inválida.');
};

export function parseUserCashCut(value: unknown): UserCashCutView {
  if (!record(value)) throw new Error('Respuesta de corte inválida.');
  const keys = ['id','organization_id','branch_id','cash_shift_id','register_code_snapshot','cashier_user_id','timezone','period_start','period_end','status','opening_cash_cents','cash_payment_cents','deposit_cents','withdrawal_cents','expected_cash_cents','counted_cash_cents','difference_cents','tolerance_cents','created_by_user_id','finalized_by_user_id','version','created_at','counted_at','finalized_at'];
  exact(value, keys);
  const version = value.version;
  if (!['id','organization_id','branch_id','cash_shift_id','cashier_user_id','register_code_snapshot','timezone','period_start','period_end','created_by_user_id','created_at'].every(key => typeof value[key] === 'string') || !['DRAFT','COUNTED','FINALIZED'].includes(String(value.status)) || !['opening_cash_cents','tolerance_cents'].every(key => integer(value[key])) || !integer(version) || !['cash_payment_cents','deposit_cents','withdrawal_cents','expected_cash_cents','counted_cash_cents','difference_cents'].every(key => value[key] === null || integer(value[key])) || !['counted_at','finalized_at','finalized_by_user_id'].every(key => value[key] === null || typeof value[key] === 'string') || version < 1) throw new Error('Respuesta de corte inválida.');
  return value as unknown as UserCashCutView;
}

export const userCashCutCapabilities = (permissions: readonly string[]) => ({
  create: permissions.includes('cash.user_cut.create'), read: permissions.includes('cash.user_cut.read'),
  reopenRequest: permissions.includes('cash.user_cut.reopen.request'), reopenAuthorize: permissions.includes('cash.user_cut.reopen.authorize'),
});

export function parseUserCashCutCents(value: string): number | null {
  const match = value.trim().match(/^(0|[1-9]\d*)(?:\.(\d{1,2}))?$/);
  if (!match) return null;
  const whole = Number(match[1]);
  const cents = whole * 100 + Number((match[2] || '').padEnd(2, '0'));
  return Number.isSafeInteger(whole) && Number.isSafeInteger(cents) ? cents : null;
}

export const buildUserCashCutCreatePayload = (
  payload: UserCashCutCreatePayload,
): UserCashCutCreatePayload => Object.freeze({ ...payload });

export const buildUserCashCutCountedPayload = (
  countedCashCents: number,
  version: number,
): UserCashCutCountedPayload => Object.freeze({ counted_cash_cents: countedCashCents, version });

export const buildUserCashCutFinalizePayload = (
  version: number,
): UserCashCutFinalizePayload => Object.freeze({ version });

export const buildUserCashCutReopenRequestPayload = (
  countedCashCents: number,
  reason: string,
  evidenceRefs: string[],
): UserCashCutReopenRequestPayload => Object.freeze({
  counted_cash_cents: countedCashCents,
  reason: reason.trim(),
  evidence_refs: [...evidenceRefs],
});

export const createUserCashCutIntent = <T>(command: string, key: string, payload: T) => (
  Object.freeze({ command, key, payload: Object.freeze(payload) })
);
export const keepUserCashCutIntent = <T>(intent: T, code: string): T | null => code === 'idempotency_conflict' ? null : intent;
export const formatCashCutMxn = (cents: number) => new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(cents / 100);
