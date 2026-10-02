/** Unconfirmed capture only. Never an operational order, payment or offline outbox. */
export const CASHIER_DRAFT_PREFIX = 'pos_cashier_drafts_v1:';

export interface CashierDraftScope {
  userId: string;
  branchId: string;
  registerId: string;
  transport: 'online' | 'local';
  gatewayUrl?: string;
  deviceId?: string;
}

export interface DraftLine {
  id: string;
  lineId: string;
  name: string;
  quantity: number;
  notes: string;
  modifiers: Array<{ option_id: string; option_name: string; price_delta_cents: number; text?: string }>;
  commentPresets: Array<{ id: string; text: string }>;
  ingredientExtras: Array<{ extra_id: string; name: string; portions: number; portion_quantity: string; sale_price_cents: number; station: string }>;
}

export interface CashierDraft<T extends DraftLine = DraftLine> {
  id: string;
  paymentKey: string;
  createdAt: string;
  cart: T[];
  ownerName: string;
  orderType: 'dine-in' | 'takeout' | 'delivery';
  paymentMethod: 'cash' | 'debit_card' | 'credit_card' | 'transfer' | null;
  customerId: string;
  addressId: string;
  driverId: string;
  requiresAdjustmentReview?: boolean;
  customer?: {
    id: string; name: string;
    addresses: Array<{ id: string; alias: string; street: string; exterior_number: string;
      interior_number?: string | null; neighborhood: string; postal_code?: string;
      city?: string; municipality?: string; state?: string; is_default: boolean; status: string }>;
    phones?: Array<{ captured_number?: string; normalized_number?: string }>;
  } | null;
}

export interface DraftStorage {
  readonly length: number;
  key(index: number): string | null;
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

interface DraftBook<T extends DraftLine> {
  schema: 1;
  scope: CashierDraftScope;
  active: CashierDraft<T> | null;
  held: CashierDraft<T>[];
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const object = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const string = (value: unknown, limit = 500): value is string => typeof value === 'string' && value.length <= limit;
const positive = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
const cents = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;

function validLine(value: unknown): boolean {
  if (!object(value) || !string(value.id, 200) || !string(value.lineId, 200) || !string(value.name, 300)
    || !positive(value.quantity) || !string(value.notes) || !Array.isArray(value.modifiers)
    || !Array.isArray(value.commentPresets) || !Array.isArray(value.ingredientExtras)) return false;
  return value.modifiers.every((entry) => object(entry) && string(entry.option_id, 200)
    && string(entry.option_name, 300) && cents(entry.price_delta_cents)
    && (entry.text === undefined || string(entry.text)))
    && value.commentPresets.every((entry) => object(entry) && string(entry.id, 200) && string(entry.text))
    && value.ingredientExtras.every((entry) => object(entry) && string(entry.extra_id, 200)
      && string(entry.name, 300) && positive(entry.portions) && string(entry.portion_quantity, 100)
      && cents(entry.sale_price_cents) && ['kitchen', 'drinks', 'packing'].includes(String(entry.station)));
}

function validDraft(value: unknown): value is CashierDraft {
  return object(value) && typeof value.id === 'string' && uuid.test(value.id)
    && typeof value.paymentKey === 'string' && uuid.test(value.paymentKey)
    && typeof value.createdAt === 'string' && Number.isFinite(Date.parse(value.createdAt))
    && Array.isArray(value.cart) && value.cart.length <= 100
    && value.cart.every(validLine) && string(value.ownerName, 300)
    && ['dine-in', 'takeout', 'delivery'].includes(String(value.orderType))
    && (value.paymentMethod === null || ['cash', 'debit_card', 'credit_card', 'transfer'].includes(String(value.paymentMethod)))
    && string(value.customerId, 200) && string(value.addressId, 200) && string(value.driverId, 200)
    && (value.requiresAdjustmentReview === undefined || typeof value.requiresAdjustmentReview === 'boolean')
    && (value.customer === undefined || value.customer === null || validCustomer(value.customer, value.customerId));
}

function validCustomer(value: unknown, customerId: string): boolean {
  if (!object(value) || value.id !== customerId || !string(value.name, 300)
    || !Array.isArray(value.addresses) || value.addresses.length > 100) return false;
  return value.addresses.every((address) => object(address) && string(address.id, 200)
    && ['alias', 'street', 'exterior_number', 'neighborhood', 'status'].every((field) => string(address[field]))
    && ['interior_number', 'postal_code', 'city', 'municipality', 'state'].every((field) =>
      address[field] === undefined || address[field] === null || string(address[field]))
    && typeof address.is_default === 'boolean')
    && (value.phones === undefined || (Array.isArray(value.phones) && value.phones.length <= 20
      && value.phones.every((phone) => object(phone)
        && ['captured_number', 'normalized_number'].every((field) => phone[field] === undefined || string(phone[field], 100)))));
}

export function cashierDraftStorageKey(scope: CashierDraftScope): string {
  if (!scope.userId || !scope.branchId || !scope.registerId || !['online', 'local'].includes(scope.transport)
    || (scope.transport === 'local' && (!scope.gatewayUrl || !scope.deviceId))) {
    throw new Error('cashier_draft_scope_required');
  }
  return CASHIER_DRAFT_PREFIX + JSON.stringify([scope.userId, scope.branchId, scope.registerId,
    scope.transport, scope.gatewayUrl || '', scope.deviceId || '']);
}

const key = cashierDraftStorageKey;

export function readCashierDrafts<T extends DraftLine>(storage: DraftStorage, scope: CashierDraftScope): DraftBook<T> {
  const raw = storage.getItem(key(scope));
  if (raw === null) return { schema: 1, scope, active: null, held: [] };
  if (raw.length > 1_000_000) throw new Error('cashier_draft_invalid');
  const book: unknown = JSON.parse(raw);
  if (!object(book) || book.schema !== 1 || !object(book.scope)
    || key(book.scope as unknown as CashierDraftScope) !== key(scope)
    || (book.active !== null && !validDraft(book.active)) || !Array.isArray(book.held)
    || book.held.length > 20 || !book.held.every(validDraft)) throw new Error('cashier_draft_invalid');
  const ids = [...book.held.map((draft) => draft.id), ...(book.active ? [(book.active as CashierDraft).id] : [])];
  if (new Set(ids).size !== ids.length) throw new Error('cashier_draft_invalid');
  return book as unknown as DraftBook<T>;
}

function write<T extends DraftLine>(storage: DraftStorage, scope: CashierDraftScope, book: DraftBook<T>): void {
  if ((book.active && !validDraft(book.active)) || !book.held.every(validDraft) || book.held.length > 20) {
    throw new Error('cashier_draft_invalid');
  }
  const ids = [...book.held.map((draft) => draft.id), ...(book.active ? [book.active.id] : [])];
  if (new Set(ids).size !== ids.length) throw new Error('cashier_draft_invalid');
  const raw = JSON.stringify(book);
  if (raw.length > 1_000_000) throw new Error('cashier_draft_full');
  storage.setItem(key(scope), raw);
}

export function saveActiveCashierDraft<T extends DraftLine>(storage: DraftStorage, scope: CashierDraftScope, draft: CashierDraft<T> | null): void {
  const book = readCashierDrafts<T>(storage, scope);
  write(storage, scope, { ...book, active: draft });
}

export function holdCashierDraft<T extends DraftLine>(storage: DraftStorage, scope: CashierDraftScope): void {
  const book = readCashierDrafts<T>(storage, scope);
  if (!book.active?.cart.length) throw new Error('cashier_draft_empty');
  const held = book.held.filter((entry) => entry.id !== book.active?.id);
  if (held.length >= 20) throw new Error('cashier_draft_full');
  write(storage, scope, { ...book, active: null, held: [...held, book.active] });
}

export function restoreHeldCashierDraft<T extends DraftLine>(storage: DraftStorage, scope: CashierDraftScope, draftId: string): CashierDraft<T> {
  const book = readCashierDrafts<T>(storage, scope);
  const draft = book.held.find((entry) => entry.id === draftId);
  if (!draft) throw new Error('cashier_draft_not_found');
  const held = book.held.filter((entry) => entry.id !== draftId && entry.id !== book.active?.id);
  if (book.active?.cart.length) held.push(book.active);
  write(storage, scope, { ...book, active: draft, held });
  return draft;
}

export function clearCashierDraftStorage(storage: DraftStorage): void {
  const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index));
  for (const storedKey of keys) if (storedKey?.startsWith(CASHIER_DRAFT_PREFIX)) storage.removeItem(storedKey);
}

export function clearCashierLocalCapture(): void {
  for (const name of ['localStorage', 'sessionStorage'] as const) {
    try { clearCashierDraftStorage(globalThis[name]); } catch { /* Logout must still remove authentication. */ }
  }
}
