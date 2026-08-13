export function parseCashCents(value: string): number | null {
  const normalized = value.trim();
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  const [whole, fraction = ''] = normalized.split('.');
  const cents = Number(`${whole}${fraction.padEnd(2, '0')}`);
  return Number.isSafeInteger(cents) && cents > 0 ? cents : null;
}

export function nextCashIdempotencyKey(current: string | null): string {
  return current || crypto.randomUUID();
}

export type CashCompensationState =
  | 'eligible'
  | 'compensated'
  | 'compensation'
  | 'ineligible';

export function cashMovementTypeLabel(movementType: string): string {
  switch (movementType) {
    case 'deposit':
      return 'Depósito';
    case 'withdrawal':
      return 'Retiro';
    case 'cash_reversal':
      return 'Reversión de efectivo';
    default:
      return 'No disponible';
  }
}

export function cashCompensationStateLabel(compensationState: string): string {
  switch (compensationState) {
    case 'eligible':
      return 'Elegible para compensación';
    case 'compensated':
      return 'Compensado';
    case 'compensation':
      return 'Compensación';
    case 'ineligible':
      return 'No elegible';
    default:
      return 'No disponible';
  }
}

export function canCompensateLedgerItem(
  canCompensate: boolean,
  compensationState: CashCompensationState,
): boolean {
  return canCompensate && compensationState === 'eligible';
}

export function buildCashCompensationPayload(reason: string, evidence: string) {
  return {
    reason: reason.trim(),
    evidence_refs: [evidence.trim()],
  };
}

export type CashCompensationIntent<T> = {
  target: T;
  reason: string;
  evidence: string;
  idempotencyKey: string | null;
};

export type CashCompensationFormState<T> = {
  intent: CashCompensationIntent<T> | null;
  loading: boolean;
};

export type CashCompensationFormAction<T> =
  | { type: 'open'; target: T }
  | { type: 'cancel' }
  | { type: 'set_reason'; reason: string }
  | { type: 'set_evidence'; evidence: string }
  | { type: 'begin_submit'; idempotencyKey: string }
  | { type: 'uncertain_failure' }
  | { type: 'complete' };

export function initialCashCompensationFormState<T>(): CashCompensationFormState<T> {
  return { intent: null, loading: false };
}

export function reduceCashCompensationFormState<T>(
  state: CashCompensationFormState<T>,
  action: CashCompensationFormAction<T>,
): CashCompensationFormState<T> {
  if (action.type === 'open') {
    return state.loading ? state : {
      intent: { target: action.target, reason: '', evidence: '', idempotencyKey: null },
      loading: false,
    };
  }
  if (action.type === 'cancel' || action.type === 'complete') {
    return state.loading && action.type === 'cancel'
      ? state
      : initialCashCompensationFormState<T>();
  }
  if (!state.intent) return state;
  if (action.type === 'set_reason') {
    return state.loading ? state : {
      ...state,
      intent: { ...state.intent, reason: action.reason },
    };
  }
  if (action.type === 'set_evidence') {
    return state.loading ? state : {
      ...state,
      intent: { ...state.intent, evidence: action.evidence },
    };
  }
  if (action.type === 'begin_submit') {
    return state.loading ? state : {
      intent: { ...state.intent, idempotencyKey: action.idempotencyKey },
      loading: true,
    };
  }
  if (action.type === 'uncertain_failure') {
    return { ...state, loading: false };
  }
  return state;
}

export function cashMovementCapabilities(input: {
  canRead: boolean;
  canWithdraw: boolean;
  canDeposit: boolean;
  canCompensate?: boolean;
}) {
  const canWrite = input.canWithdraw || input.canDeposit;
  return {
    ...input,
    canCompensate: input.canCompensate === true,
    canWrite,
    canUse: input.canRead || canWrite,
    initialType: input.canWithdraw ? 'withdrawal' as const : 'deposit' as const,
  };
}
