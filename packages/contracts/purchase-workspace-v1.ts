/** Online v1 capture. Exact decimals travel as strings; Python validates and calculates. */
export type PurchaseDocumentType = 'invoice' | 'receipt' | 'ticket' | 'note';
export interface PurchaseLineInputV1 {
  presentation_id: string; quantity: string; unit_price: string; discount: string; tax: string;
}
export interface PurchaseCreateInputV1 {
  branch_id: string; supplier_id: string; document_type: PurchaseDocumentType;
  folio: string; document_date: string; payment_method: string; paid_from_cash: boolean;
  notes: string; evidence_url: string; lines: PurchaseLineInputV1[];
}
