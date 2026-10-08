export type ExpenseMethod = 'cash' | 'transfer' | 'card' | 'other';
export interface ExpenseConcept {
    id: string;
    code: string;
    name: string;
    description: string;
    status: 'active' | 'archived';
    version: number;
}
export interface ExpenseInput {
    branch_id: string;
    concept_id: string;
    document_date: string;
    total_cents: number;
    tax_cents: number | null;
    payment_method: ExpenseMethod;
    reference: string;
    notes: string;
    evidence_refs: string[];
}
export interface ExpenseDocument extends ExpenseInput {
    id: string;
    folio: string;
    concept_snapshot: {
        code: string;
        name: string;
    };
    status: 'draft' | 'confirmed' | 'cancelled';
    version: number;
    confirmed_at: string | null;
    cash_movement_id: string | null;
    compensation_movement_id: string | null;
    cancellation_reason: string | null;
}
export interface ExpenseCashContext {
    branch_id: string;
    open_registers: {
        register_id: string;
        cash_shift_id: string;
        opened_at: string;
    }[];
}
export interface ExpenseSummary {
    confirmed_cents: number;
    reversed_cents: number;
    net_cents: number;
    cash_cents: number;
    other_cents: number;
    groups: {
        branch_id: string;
        concept_id: string;
        concept_name: string;
        payment_method: ExpenseMethod;
        net_cents: number;
    }[];
}
