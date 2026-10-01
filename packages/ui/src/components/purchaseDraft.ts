import type { PurchaseCreateInputV1, PurchaseDocumentType } from '../../../contracts/purchase-workspace-v1';

export interface PurchaseDraftLine {
  id: string;
  presentation_id: string;
  quantity: string;
  unit_price: string;
  discount: string;
  tax: string;
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
  notes: string;
  evidence_url: string;
  lines: PurchaseDraftLine[];
  creationKey: string;
  phase: 'editing' | 'submitting' | 'uncertain';
  message: string;
  dirty: boolean;
  reviewFingerprint?: string;
}
export type PurchaseDraftAction =
  | { type: 'header'; key: 'supplier_id' | 'folio' | 'document_type' | 'document_date' | 'notes' | 'evidence_url' | 'payment_method'; value: string }
  | { type: 'cash'; value: boolean }
  | { type: 'line'; id: string; key: Exclude<keyof PurchaseDraftLine, 'id'>; value: string }
  | { type: 'add'; id: string }
  | { type: 'remove'; id: string }
  | { type: 'submit'; fingerprint?: string }
  | { type: 'uncertain' | 'resolved'; message: string };
const emptyLine = (id: string): PurchaseDraftLine => ({ id, presentation_id: '', quantity: '1', unit_price: '', discount: '0', tax: '0' });
export function initialPurchaseDraft(scope: string, branchId: string, date: string, key: string, lineId: string): PurchaseDraft {
  return { scope, branch_id: branchId, supplier_id: '', folio: '', document_type: 'invoice', document_date: date, payment_method: 'other', paid_from_cash: false, notes: '', evidence_url: '', lines: [emptyLine(lineId)], creationKey: key, phase: 'editing', message: '', dirty: false };
}
export function restorePurchaseDraft(draft: PurchaseDraft): PurchaseDraft {
  return draft.phase === 'submitting'
    ? { ...draft, phase: 'uncertain', message: 'La sesión se interrumpió. Recupera la misma nota antes de continuar.' }
    : draft;
}
export function purchaseDraftReducer(state: PurchaseDraft, action: PurchaseDraftAction): PurchaseDraft {
  if (action.type === 'submit') return { ...state, phase: 'submitting', message: '', reviewFingerprint: action.fingerprint ?? state.reviewFingerprint };
  if (action.type === 'uncertain' || action.type === 'resolved') return { ...state, phase: action.type === 'uncertain' ? 'uncertain' : 'editing', message: action.message };
  if (state.phase !== 'editing') return state;
  state = { ...state, dirty: true };
  if (action.type === 'header') return { ...state, [action.key]: action.value, message: '' };
  if (action.type === 'cash') return { ...state, paid_from_cash: action.value, payment_method: action.value ? 'cash' : 'other' };
  if (action.type === 'line') return { ...state, lines: state.lines.map(line => line.id === action.id ? { ...line, [action.key]: action.value } : line) };
  if (action.type === 'add' && state.lines.length < 200) return { ...state, lines: [...state.lines, emptyLine(action.id)] };
  if (action.type === 'remove' && state.lines.length > 1) return { ...state, lines: state.lines.filter(line => line.id !== action.id) };
  return state;
}
export function purchasePayload(draft: PurchaseDraft): PurchaseCreateInputV1 {
  return {
    branch_id: draft.branch_id, supplier_id: draft.supplier_id, folio: draft.folio,
    document_type: draft.document_type as PurchaseDocumentType, document_date: draft.document_date,
    payment_method: draft.payment_method, paid_from_cash: draft.paid_from_cash,
    notes: draft.notes, evidence_url: draft.evidence_url,
    lines: draft.lines.map(({ id: _id, ...line }) => line),
  };
}
