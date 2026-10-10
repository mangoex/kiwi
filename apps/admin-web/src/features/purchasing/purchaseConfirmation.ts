import type { PurchaseCashContextV1, PurchaseConfirmInputV1 } from '../../../../../packages/contracts/purchase-workspace-v1';

export interface PurchaseScope { organization_id: string; actor_id: string; branch_id: string; }
export interface ConfirmablePurchase { id: string; organization_id: string; branch_id: string; paid_from_cash: boolean; payment_method: string; }
export interface PurchaseAttempt { scope: PurchaseScope; purchase_id: string; key: string; body: PurchaseConfirmInputV1; }
export const purchaseMethodLabels: Record<string, string> = { cash: 'Efectivo', transfer: 'Transferencia', card: 'Tarjeta', other: 'Otro' };
export const purchaseScopeKey = (scope: PurchaseScope): string => `${scope.organization_id}:${scope.actor_id}:${scope.branch_id}`;
export const purchaseAttemptKey = (scope: PurchaseScope, id: string): string => `purchase-attempt:${purchaseScopeKey(scope)}:${id}`;

export function isDefinitivePurchaseRejection(status: number, code: string, recovering: boolean): boolean {
  if (status < 400 || status >= 500 || status === 401 || status === 403 || code === 'idempotency_key_conflict') return false;
  if (!recovering) return true;
  // Same-key replays of an applied confirmation return its persisted result before these guards.
  return status === 409 && ['purchase_cash_context_changed', 'cash_shift_not_open', 'purchase_not_confirmable', 'purchase_already_confirmed'].includes(code);
}

export function selectedPurchaseRegister(context: PurchaseCashContextV1 | undefined, branch: string, hint: string | null): string {
  if (context?.branch_id !== branch) return '';
  const boxes = context.open_registers;
  return boxes.find(box => box.register_id === hint)?.register_id || (boxes.length === 1 ? boxes[0].register_id : '');
}

export function createPurchaseAttempt(scope: PurchaseScope, purchase: ConfirmablePurchase, cash: PurchaseCashContextV1 | undefined, register: string, key: string): PurchaseAttempt {
  if (!scope.organization_id || !scope.actor_id || !scope.branch_id || purchase.organization_id !== scope.organization_id || purchase.branch_id !== scope.branch_id) throw new Error('Vuelve a la cuenta y sucursal de esta compra antes de confirmar.');
  if (!purchaseMethodLabels[purchase.payment_method] || (purchase.payment_method === 'cash') !== purchase.paid_from_cash) throw new Error('El método de esta nota es incoherente. Cancélala y vuelve a capturarla.');
  let body: PurchaseConfirmInputV1 = { branch_id: scope.branch_id };
  if (purchase.paid_from_cash) {
    const box = cash?.branch_id === scope.branch_id ? cash.open_registers.find(row => row.register_id === register) : undefined;
    if (!box) throw new Error('Selecciona una caja con turno abierto en esta sucursal.');
    body = { ...body, register_id: box.register_id, expected_cash_shift_id: box.cash_shift_id };
  }
  return { scope: { ...scope }, purchase_id: purchase.id, key, body };
}

export function readPurchaseAttempt(storage: Pick<Storage, 'getItem'>, scope: PurchaseScope, id: string): PurchaseAttempt | null {
  const raw = storage.getItem(purchaseAttemptKey(scope, id));
  if (!raw) return null;
  try {
    const parsed: PurchaseAttempt = JSON.parse(raw);
    const scopeFields = ['organization_id', 'actor_id', 'branch_id'];
    if (Object.keys(parsed).sort().join() !== ['body', 'key', 'purchase_id', 'scope'].join()
      || Object.keys(parsed.scope).sort().join() !== [...scopeFields].sort().join()
      || scopeFields.some(field => parsed.scope[field as keyof PurchaseScope] !== scope[field as keyof PurchaseScope]) || parsed.purchase_id !== id
      || typeof parsed.key !== 'string' || !parsed.key || parsed.key.length > 180
      || parsed.body.branch_id !== scope.branch_id
      || Object.keys(parsed.body).some(field => !['branch_id', 'register_id', 'expected_cash_shift_id'].includes(field))
      || Object.values(parsed.body).some(value => typeof value !== 'string' || !value)
      || ('register_id' in parsed.body) !== ('expected_cash_shift_id' in parsed.body)) throw new Error();
    return parsed;
  } catch { throw new Error('No se pudo validar el intento pendiente. Revisa su resultado antes de confirmar otra vez.'); }
}
