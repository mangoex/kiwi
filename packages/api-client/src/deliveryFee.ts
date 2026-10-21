export type DeliverySelection = { mode: 'AUTO' } | { mode: 'REMOVED' }
  | { mode: 'SELECTED'; tariff_id: string };

export interface DeliveryTariff {
  id: string; code: string; name: string; version: number; amount_cents: number; active: boolean;
  fiscal_mapping: { product_key?: string; unit_key?: string; emitter_id?: string };
}
export interface DeliveryPolicy {
  id: string; version: number; scope_key: string; enabled: boolean; eligible_tariff_ids: string[];
  default_tariff_id: string | null; free_threshold_cents: number | null;
}
export interface DeliveryCharge {
  state: 'CHARGED' | 'WAIVED_THRESHOLD' | 'REMOVED'; selection: DeliverySelection;
  tariff: DeliveryTariff; policy: DeliveryPolicy; charged_cents: number; list_cents: number;
  net_amount: string; tax_amount: string; net_cents: number; tax_cents: number; eligible_subtotal_cents: number;
}
export interface DeliveryOptions { policy: DeliveryPolicy | null; tariffs: DeliveryTariff[] }

/** Capture cents without rounding, binary fractional arithmetic or exponent notation. */
export function parseDeliveryAmount(value: string): number {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) throw new Error('Usa un importe con máximo dos decimales.');
  const [whole, fractional = ''] = value.split('.');
  const cents = Number(whole) * 100 + Number(fractional.padEnd(2, '0'));
  if (!Number.isSafeInteger(cents) || cents > 2_000_000_000) throw new Error('El importe excede el límite.');
  return cents;
}

export function deliverySelectionFromDraft(value: unknown): DeliverySelection {
  if (value === undefined || value === null) return { mode: 'AUTO' };
  if (typeof value !== 'object' || Array.isArray(value)) throw new Error('Selección de envío inválida.');
  const candidate = value as Record<string, unknown>;
  if (candidate.mode === 'AUTO' || candidate.mode === 'REMOVED') return { mode: candidate.mode };
  if (candidate.mode === 'SELECTED' && typeof candidate.tariff_id === 'string' && candidate.tariff_id) {
    return { mode: 'SELECTED', tariff_id: candidate.tariff_id };
  }
  throw new Error('Selección de envío inválida.');
}
