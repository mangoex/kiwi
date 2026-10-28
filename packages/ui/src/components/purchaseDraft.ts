import type { PurchaseCreateInputV1, PurchaseDocumentType, PurchasePaymentMethod } from '../../../contracts/purchase-workspace-v1';

export type PurchaseDecimalKey = 'quantity' | 'unit_price' | 'discount' | 'tax';
// Presentation only. Never use this rounded string in a preview or command.
export function formatPurchaseDecimal(value: string | number | null | undefined): string {
  const match = String(value ?? '').trim().replace(',', '.').match(/^(-?)(\d+)(?:\.(\d+))?$/);
  if (!match) return '—';
  const [, sign, whole, fraction = ''] = match;
  let cents = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0').slice(0, 2));
  if (fraction.length > 2 && fraction[2] >= '5') cents += 1n;
  return `${sign && cents !== 0n ? '-' : ''}${cents / 100n}.${String(cents % 100n).padStart(2, '0')}`;
}
export function purchaseCaptureError(input: string | undefined): string {
  if (input === undefined) return '';
  return /^\d+(?:[.,]\d{1,2})?$/.test(input.trim()) ? '' : 'Usa máximo 2 decimales, sin signos ni exponentes.';
}

export interface PurchaseDraftLine {
  id: string;
  presentation_id: string;
  quantity: string;
  unit_price: string;
  discount: string;
  tax: string;
  manualInputs?: Partial<Record<PurchaseDecimalKey, string>>;
  ai_description?: string;
  ai_match_status?: 'matched' | 'cross_supplier' | 'unmatched';
}
export interface PurchaseAiExtractionInput {
  supplier_id?: string;
  folio?: string;
  document_date?: string;
  delivered_by_name?: string;
  payment_method?: string;
  notes?: string;
  lines: PurchaseDraftLine[];
}
export interface PurchaseDraft {
  scope: string;
  branch_id: string;
  supplier_id: string;
  folio: string;
  document_type: string;
  document_date: string;
  payment_method: string;
  paid_from_cash: boolean;
  delivered_by_name: string;
  supplier_catalog_exception: boolean;
  supplier_catalog_exception_reason: string;
  notes: string;
  evidence_url: string;
  lines: PurchaseDraftLine[];
  creationKey: string;
  phase: 'editing' | 'submitting' | 'uncertain';
  message: string;
  dirty: boolean;
  reviewFingerprint?: string;
  purchaseId?: string;
  expectedVersion?: number;
}
export interface PersistedPurchaseDraft {
  id: string; branch_id: string; supplier_id: string; folio: string; document_type: string;
  document_date: string; payment_method: string; paid_from_cash: boolean; version: number;
  delivered_by_name?: string | null; notes?: string | null; evidence_url?: string | null;
  lines: { id: string; presentation_id: string; presentation_quantity: string | number; unit_price: string | number; discount: string | number; tax: string | number; presentation_snapshot?: { supplier_catalog_exception?: boolean; supplier_catalog_exception_reason?: string | null } }[];
}
export type PurchaseDraftAction =
  | { type: 'header'; key: 'supplier_id' | 'folio' | 'document_type' | 'document_date' | 'delivered_by_name' | 'notes' | 'evidence_url' | 'payment_method' | 'supplier_catalog_exception_reason'; value: string }
  | { type: 'defaultDate'; value: string }
  | { type: 'cash'; value: boolean }
  | { type: 'supplierException'; value: boolean }
  | { type: 'line'; id: string; key: 'presentation_id' | 'quantity' | 'unit_price' | 'discount' | 'tax'; value: string }
  | { type: 'capture'; id: string; key: PurchaseDecimalKey; value: string }
  | { type: 'applyExtraction'; extraction: PurchaseAiExtractionInput }
  | { type: 'add'; id: string; afterId?: string }
  | { type: 'remove'; id: string }
  | { type: 'submit'; fingerprint?: string }
  | { type: 'uncertain' | 'resolved'; message: string };
const emptyLine = (id: string): PurchaseDraftLine => ({ id, presentation_id: '', quantity: '1', unit_price: '', discount: '0', tax: '0' });
export function branchLocalDate(timeZone: string, now = new Date()): string {
  try {
    const values = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
      timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(now).map(part => [part.type, part.value]));
    return values.year && values.month && values.day
      ? `${values.year}-${values.month}-${values.day}`
      : '';
  } catch {
    return '';
  }
}
export function initialPurchaseDraft(scope: string, branchId: string, date: string, key: string, lineId: string): PurchaseDraft {
  return { scope, branch_id: branchId, supplier_id: '', folio: '', document_type: 'invoice', document_date: date, payment_method: 'cash', paid_from_cash: true, delivered_by_name: '', supplier_catalog_exception: false, supplier_catalog_exception_reason: '', notes: '', evidence_url: '', lines: [emptyLine(lineId)], creationKey: key, phase: 'editing', message: '', dirty: false };
}
export function purchaseDraftFromDocument(scope: string, purchase: PersistedPurchaseDraft, key: string): PurchaseDraft {
  const exceptionLine = purchase.lines.find(line => line.presentation_snapshot?.supplier_catalog_exception === true);
  return {
    scope,
    branch_id: purchase.branch_id,
    supplier_id: purchase.supplier_id,
    folio: purchase.folio,
    document_type: purchase.document_type,
    document_date: purchase.document_date.slice(0, 10),
    payment_method: purchase.payment_method,
    paid_from_cash: purchase.paid_from_cash,
    delivered_by_name: purchase.delivered_by_name || '',
    supplier_catalog_exception: Boolean(exceptionLine),
    supplier_catalog_exception_reason: exceptionLine?.presentation_snapshot?.supplier_catalog_exception_reason || '',
    notes: purchase.notes || '',
    evidence_url: purchase.evidence_url || '',
    lines: purchase.lines.map(line => ({
      id: line.id,
      presentation_id: line.presentation_id,
      quantity: String(line.presentation_quantity),
      unit_price: String(line.unit_price),
      discount: String(line.discount),
      tax: String(line.tax),
    })),
    creationKey: key,
    phase: 'editing',
    message: '',
    dirty: false,
    purchaseId: purchase.id,
    expectedVersion: purchase.version,
  };
}
export function restorePurchaseDraft(draft: PurchaseDraft): PurchaseDraft {
  const compatibleDraft = {
    ...draft,
    delivered_by_name: draft.delivered_by_name || '',
    supplier_catalog_exception: Boolean(draft.supplier_catalog_exception),
    supplier_catalog_exception_reason: draft.supplier_catalog_exception_reason || '',
  };
  return compatibleDraft.phase === 'submitting'
    ? { ...compatibleDraft, phase: 'uncertain', message: 'La sesión se interrumpió. Recupera la misma nota antes de continuar.' }
    : compatibleDraft;
}
export function purchaseDraftReducer(state: PurchaseDraft, action: PurchaseDraftAction): PurchaseDraft {
  if (action.type === 'submit') return { ...state, phase: 'submitting', message: '', reviewFingerprint: action.fingerprint ?? state.reviewFingerprint };
  if (action.type === 'uncertain' || action.type === 'resolved') return { ...state, phase: action.type === 'uncertain' ? 'uncertain' : 'editing', message: action.message };
  if (state.phase !== 'editing') return state;
  if (action.type === 'defaultDate') return !state.dirty && !state.document_date
    ? { ...state, document_date: action.value }
    : state;
  state = { ...state, dirty: true };
  if (action.type === 'header') return { ...state, [action.key]: action.value, ...(action.key === 'payment_method' ? { paid_from_cash: action.value === 'cash' } : {}), message: '' };
  if (action.type === 'cash') return { ...state, paid_from_cash: action.value, payment_method: action.value ? 'cash' : 'other' };
  if (action.type === 'supplierException') return {
    ...state,
    supplier_catalog_exception: action.value,
    supplier_catalog_exception_reason: action.value ? state.supplier_catalog_exception_reason : '',
    message: '',
  };
  if (action.type === 'applyExtraction') {
    const ext = action.extraction;
    const method = ext.payment_method || state.payment_method || 'cash';
    return {
      ...state,
      supplier_id: ext.supplier_id || state.supplier_id,
      folio: ext.folio || state.folio,
      document_date: ext.document_date || state.document_date,
      delivered_by_name: ext.delivered_by_name || state.delivered_by_name,
      payment_method: method,
      paid_from_cash: method === 'cash',
      notes: ext.notes || state.notes,
      lines: ext.lines.length > 0 ? ext.lines.slice(0, 200) : state.lines,
      message: '',
    };
  }
  if (action.type === 'capture') return { ...state, lines: state.lines.map(line => line.id === action.id ? {
    ...line, [action.key]: action.value.trim().replace(',', '.'), manualInputs: { ...line.manualInputs, [action.key]: action.value },
  } : line) };
  if (action.type === 'line') return { ...state, lines: state.lines.map(line => line.id === action.id ? { ...line, [action.key]: action.value, manualInputs: { ...line.manualInputs, [action.key]: undefined }, ...(action.key === 'presentation_id' && action.value ? { ai_match_status: 'matched' as const } : {}) } : line) };
  if (action.type === 'add' && state.lines.length < 200) {
    const index = action.afterId ? state.lines.findIndex(line => line.id === action.afterId) : -1;
    const lines = [...state.lines];
    lines.splice(index >= 0 ? index + 1 : lines.length, 0, emptyLine(action.id));
    return { ...state, lines };
  }
  if (action.type === 'remove' && state.lines.length > 1) return { ...state, lines: state.lines.filter(line => line.id !== action.id) };
  return state;
}
export function purchasePayload(draft: PurchaseDraft): PurchaseCreateInputV1 {
  return {
    branch_id: draft.branch_id, supplier_id: draft.supplier_id, folio: draft.folio,
    document_type: draft.document_type as PurchaseDocumentType, document_date: draft.document_date,
    payment_method: draft.payment_method as PurchasePaymentMethod, paid_from_cash: draft.paid_from_cash,
    delivered_by_name: draft.delivered_by_name,
    supplier_catalog_exception: Boolean(draft.supplier_catalog_exception),
    supplier_catalog_exception_reason: draft.supplier_catalog_exception_reason || '',
    notes: draft.notes, evidence_url: draft.evidence_url,
    lines: draft.lines.map(line => ({
      presentation_id: line.presentation_id,
      quantity: line.quantity,
      unit_price: line.unit_price,
      discount: line.discount,
      tax: line.tax,
    })),
  };
}

export function purchasePreviewReady(draft: PurchaseDraft): boolean {
  const requiredDocumentFields = [
    draft.branch_id,
    draft.supplier_id,
    draft.document_type,
    draft.folio,
    draft.document_date,
    draft.payment_method,
  ];
  if (
    draft.phase !== 'editing'
    || requiredDocumentFields.some(value => !value.trim())
    || draft.lines.length < 1
    || draft.lines.length > 200
    || (draft.supplier_catalog_exception && !draft.supplier_catalog_exception_reason.trim())
  ) return false;
  return draft.lines.every(line => Object.values(line.manualInputs || {}).every(input => !purchaseCaptureError(input)) && [
    line.presentation_id,
    line.quantity,
    line.unit_price,
    line.discount,
    line.tax,
  ].every(value => value.trim()));
}
