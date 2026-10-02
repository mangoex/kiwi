/** Pending command receipt, not a draft sale. Freeze the body before any network write. */
export const CASHIER_PAYMENT_STORAGE_KEY = 'pos_cashier_payment_v1';
export interface PaymentAttempt {
  schema: 1;
  authority: string;
  orderId: string;
  key: string;
  body: { amount_cents: number; method: string; register_id: string; received_cash?: string };
}
type StorageAccess = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function readPaymentAttempt(storage: StorageAccess): PaymentAttempt | null {
  const raw = storage.getItem(CASHIER_PAYMENT_STORAGE_KEY);
  if (raw === null) return null;
  if (raw.length > 5000) throw new Error('El intento de cobro guardado es inválido.');
  const value = JSON.parse(raw) as PaymentAttempt;
  if (!value || value.schema !== 1 || typeof value.authority !== 'string' || !value.authority
    || !uuid.test(value.orderId) || !uuid.test(value.key) || !value.body
    || !Number.isSafeInteger(value.body.amount_cents) || value.body.amount_cents <= 0
    || !['cash', 'debit_card', 'credit_card', 'transfer'].includes(value.body.method)
    || typeof value.body.register_id !== 'string' || !value.body.register_id.trim()
    || (value.body.received_cash !== undefined && typeof value.body.received_cash !== 'string')) {
    throw new Error('El intento de cobro guardado es inválido.');
  }
  return value;
}

export function storePaymentAttempt(storage: StorageAccess, attempt: PaymentAttempt): void {
  if (readPaymentAttempt(storage)) throw new Error('Resuelve el cobro pendiente antes de iniciar otro.');
  storage.setItem(CASHIER_PAYMENT_STORAGE_KEY, JSON.stringify(attempt));
}

export function clearPaymentAttempt(storage: StorageAccess, expectedKey?: string): void {
  if (expectedKey && readPaymentAttempt(storage)?.key !== expectedKey) return;
  storage.removeItem(CASHIER_PAYMENT_STORAGE_KEY);
}

/** Only definite domain rejections allow a corrected intention. Conflicts stay recoverable. */
export function paymentWasDefinitelyRejected(error: unknown): boolean {
  if (!error || typeof error !== 'object' || !('code' in error)) return false;
  return ['cash_received_invalid', 'cash_received_insufficient', 'payment_total_mismatch',
    'invalid_payment_method', 'invalid_payment_amount', 'register_id_required',
    'cash_shift_not_open', 'order_already_closed', 'order_cancelled',
  ].includes(String(error.code));
}

export interface CashierPaymentResult {
  order_status: string;
  cash_tender?: { received_cents: number; change_cents: number; shortfall_cents: number; can_confirm: boolean };
  already_confirmed?: true;
}

/** A competing confirmation requires authoritative reconciliation before releasing the receipt. */
export async function submitCashierPayment(
  request: <T>(endpoint: string, options?: RequestInit) => Promise<T>,
  orderId: string, options: RequestInit,
): Promise<CashierPaymentResult> {
  try {
    return await request<CashierPaymentResult>(`/orders/${orderId}/payments`, options);
  } catch (error) {
    if (!error || typeof error !== 'object' || !('code' in error)
      || error.code !== 'payment_already_confirmed') throw error;
    const detail = await request<{ id: string; payment_status: string; status: string }>(`/orders/${orderId}`);
    if (detail.id !== orderId || detail.payment_status !== 'CONFIRMED') throw error;
    return { order_status: detail.status, already_confirmed: true };
  }
}
