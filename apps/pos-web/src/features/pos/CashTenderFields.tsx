import React from 'react';
import { formatMxnCents } from './cartMoney';
import type { CashTender } from './useCashTenderPreview';

export function CashTenderFields({ received, onChange, tender, error, disabled = false }: {
  received: string; onChange: (value: string) => void; tender?: CashTender;
  error?: string; disabled?: boolean;
}) {
  return <section className="pos-cash-tender" aria-label="Efectivo recibido y cambio">
    <label>Importe recibido
      <input autoFocus inputMode="decimal" value={received} maxLength={18} disabled={disabled}
        placeholder="Ej. 200.00" onChange={(event) => onChange(event.target.value)} />
    </label>
    {error ? <p role="alert">{error}</p> : received && !tender ? <p role="status">Calculando cambio…</p> : null}
    {tender ? <div aria-live="polite"><span>{tender.can_confirm ? 'Cambio' : 'Falta recibir'}</span>
      <strong>{formatMxnCents(tender.can_confirm ? tender.change_cents : tender.shortfall_cents)}</strong>
    </div> : null}
  </section>;
}
