export type ShiftFailureKind = 'network' | 'server' | 'idempotency_conflict';

export interface CloseIntent {
  readonly shiftId: string;
  readonly key: string;
  readonly payload: Readonly<Record<string, never>>;
}

export interface CashShiftView {
  id: string;
  organization_id: string;
  branch_id: string;
  register_code: string;
  status: string;
  opening_cash_cents: number;
  opened_at: string;
  closed_at: string | null;
  created_at: string;
  cashier_user_id?: string | null;
}

export interface ClosureView {
  id: string;
  organization_id: string;
  branch_id: string;
  cash_shift_id: string;
  register_code_snapshot: string;
  closed_by_user_id: string;
  closed_at: string;
  summary_snapshot: Record<string, number>;
  created_at: string;
}

export interface CurrentShiftView {
  cash_shift: CashShiftView | null;
  closure: ClosureView | null;
}

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
);

function parseCashShift(value: unknown): CashShiftView {
  if (!isRecord(value)
      || !['id', 'organization_id', 'branch_id', 'register_code', 'status', 'opened_at', 'created_at'].every((key) => typeof value[key] === 'string')
      || !Number.isSafeInteger(value.opening_cash_cents)
      || (value.opening_cash_cents as number) < 0
      || !(value.closed_at === null || typeof value.closed_at === 'string')) {
    throw new Error('Respuesta de turno de caja inválida.');
  }
  return {
    id: String(value.id),
    organization_id: String(value.organization_id),
    branch_id: String(value.branch_id),
    register_code: String(value.register_code),
    status: String(value.status),
    opening_cash_cents: Number(value.opening_cash_cents),
    opened_at: String(value.opened_at),
    closed_at: value.closed_at ? String(value.closed_at) : null,
    created_at: String(value.created_at),
    cashier_user_id: value.cashier_user_id ? String(value.cashier_user_id) : null,
  };
}

export function parseOpenShiftResponse(value: unknown): CashShiftView {
  return parseCashShift(value);
}

function parseClosure(value: unknown): ClosureView {
  if (!isRecord(value)
      || !['id', 'organization_id', 'branch_id', 'cash_shift_id', 'register_code_snapshot',
        'closed_by_user_id', 'closed_at', 'created_at'].every((key) => typeof value[key] === 'string')
      || !isRecord(value.summary_snapshot)
      || !Object.values(value.summary_snapshot).every((item) => Number.isSafeInteger(item))) {
    throw new Error('Respuesta de cierre operativo inválida.');
  }
  return {
    id: String(value.id),
    organization_id: String(value.organization_id),
    branch_id: String(value.branch_id),
    cash_shift_id: String(value.cash_shift_id),
    register_code_snapshot: String(value.register_code_snapshot),
    closed_by_user_id: String(value.closed_by_user_id),
    closed_at: String(value.closed_at),
    summary_snapshot: value.summary_snapshot as Record<string, number>,
    created_at: String(value.created_at),
  };
}

export function parseCurrentShiftResponse(value: unknown): CurrentShiftView {
  if (!isRecord(value)
      || !Object.prototype.hasOwnProperty.call(value, 'cash_shift')
      || !Object.prototype.hasOwnProperty.call(value, 'closure')) {
    throw new Error('Respuesta actual de turno de caja inválida.');
  }
  return {
    cash_shift: value.cash_shift === null ? null : parseCashShift(value.cash_shift),
    closure: value.closure === null ? null : parseClosure(value.closure),
  };
}

export function parseCloseResponse(value: unknown): { cash_shift: CashShiftView; closure: ClosureView } {
  if (!isRecord(value)) throw new Error('Respuesta de cierre operativo inválida.');
  return { cash_shift: parseCashShift(value.cash_shift), closure: parseClosure(value.closure) };
}

export function parseExactCents(value: string): number | null {
  const match = value.trim().match(/^(0|[1-9]\d*)(?:\.(\d{1,2}))?$/);
  if (!match) return null;
  const whole = Number(match[1]);
  const fraction = Number((match[2] || '').padEnd(2, '0'));
  if (!Number.isSafeInteger(whole)) return null;
  const cents = whole * 100 + fraction;
  return Number.isSafeInteger(cents) ? cents : null;
}

export function normalizeRegisterId(value: string): string {
  return value.trim();
}

export function isPersistedCashConfiguration(
  branchId: string,
  activeBranchId: string,
  draftRegisterId: string,
  persistedRegisterId: string,
  persistedBranchId: string,
): boolean {
  return Boolean(
    branchId
    && branchId === activeBranchId
    && persistedBranchId === activeBranchId
    && normalizeRegisterId(draftRegisterId)
    && normalizeRegisterId(draftRegisterId) === normalizeRegisterId(persistedRegisterId),
  );
}

export function createCloseIntent(shiftId: string, key: string): CloseIntent {
  return Object.freeze({ shiftId, key, payload: Object.freeze({}) });
}

export function keepIntentAfterFailure<T>(
  intent: T,
  failure: ShiftFailureKind,
): T | null {
  return failure === 'idempotency_conflict' ? null : intent;
}

export function isIdempotencyConflict(error: unknown): boolean {
  return Boolean(
    error
    && typeof error === 'object'
    && 'code' in error
    && error.code === 'idempotency_conflict',
  );
}
