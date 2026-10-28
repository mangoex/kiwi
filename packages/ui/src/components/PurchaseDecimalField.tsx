import { useId, useState } from 'react';
import { formatPurchaseDecimal, purchaseCaptureError } from './purchaseDraft';

export function PurchaseDecimalField({ label, value, input, onChange }: {
  label: string; value: string; input?: string; onChange: (value: string) => void;
}) {
  const [editingText, setEditingText] = useState<string | null>(null);
  const errorId = useId();
  const error = purchaseCaptureError(input);
  const shown = editingText ?? (error ? input : value ? formatPurchaseDecimal(value) : '');
  return <label>{label}<input inputMode="decimal" value={shown} aria-label={label} aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined}
    onFocus={event => setEditingText(event.currentTarget.value)} onBlur={() => setEditingText(null)}
    onChange={event => { setEditingText(event.target.value); onChange(event.target.value); }} />
    {error && <span id={errorId} className="purchase-field-error" role="alert">{error}</span>}
  </label>;
}
