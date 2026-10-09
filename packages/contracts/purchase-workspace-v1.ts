/** Online v1 capture. Exact decimals travel as strings; Python validates and calculates. */
export type PurchaseDocumentType = 'invoice' | 'receipt' | 'ticket' | 'note';
export type PurchasePaymentMethod = 'cash' | 'transfer' | 'card' | 'other';
export interface PurchaseCashContextV1 {
  branch_id: string;
  open_registers: { register_id: string; cash_shift_id: string; opened_at: string }[];
}
export type PurchaseConfirmInputV1 = { branch_id: string; register_id?: never; expected_cash_shift_id?: never }
  | { branch_id: string; register_id: string; expected_cash_shift_id: string };
export interface PurchaseLineInputV1 {
  presentation_id: string; quantity: string; unit_price: string; discount: string; tax: string;
}
export interface PurchaseCreateInputV1 {
  branch_id: string; supplier_id: string; document_type: PurchaseDocumentType;
  folio: string; document_date: string; payment_method: PurchasePaymentMethod; paid_from_cash: boolean;
  supplier_catalog_exception: boolean; supplier_catalog_exception_reason: string;
  notes: string; evidence_url: string; lines: PurchaseLineInputV1[];
}
