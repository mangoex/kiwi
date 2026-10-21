import { useEffect, useState } from 'react';
import { fetchApi, type DeliveryCharge, type DeliveryOptions, type DeliverySelection } from '@restaurantos/api-client';
import { Button } from '@restaurantos/ui';
import { Bike, ChevronDown } from 'lucide-react';
import { formatMxnCents } from './cartMoney';

export function DeliveryFeeControl({ branchId, selection, charge, onChange }: {
  branchId: string; selection: DeliverySelection; charge: DeliveryCharge | null;
  onChange: (selection: DeliverySelection) => void;
}) {
  const [options, setOptions] = useState<DeliveryOptions | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setOptions(null); setError('');
    fetchApi<DeliveryOptions>(`/delivery-options?branch_id=${encodeURIComponent(branchId)}`,
      { signal: controller.signal }).then((data) => {
        if (!controller.signal.aborted) setOptions(data);
      }).catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'No se pudieron cargar las tarifas.');
      });
    return () => controller.abort();
  }, [branchId]);
  if (!charge && !options?.policy?.enabled) return error ? <p role="status">{error}</p> : null;
  const tariffs = [...(options?.tariffs || [])];
  if (charge && !tariffs.some((tariff) => tariff.id === charge.tariff.id)) tariffs.unshift(charge.tariff);
  const removed = selection.mode === 'REMOVED';
  const waived = charge?.state === 'WAIVED_THRESHOLD';
  return <fieldset className="delivery-fee-control">
    <legend className="pos-sr-only">Servicio de domicilio</legend>
    <details>
      <summary aria-label="Opciones de envío">
        <Bike size={19} aria-hidden="true" />
        <span className="delivery-fee-caption"><strong>Envío</strong><small>{charge?.state === 'REMOVED'
          ? 'Retirado manualmente' : waived ? 'Por monto mínimo' : charge?.tariff.name || 'Calculando…'}</small></span>
        <strong>{charge?.state === 'REMOVED' ? 'Sin cargo' : waived ? 'Gratis' : charge ? formatMxnCents(charge.charged_cents) : '—'}</strong>
        <ChevronDown size={16} className="delivery-fee-chevron" aria-hidden="true" />
      </summary>
      <div className="delivery-fee-options">
        <strong>Opciones de envío</strong>
        <label htmlFor="delivery-tariff">Tarifa de envío</label>
        <select id="delivery-tariff" disabled={removed || !options}
          value={selection.mode === 'SELECTED' ? selection.tariff_id : 'AUTO'}
          onChange={(event) => onChange(event.target.value === 'AUTO' ? { mode: 'AUTO' }
            : { mode: 'SELECTED', tariff_id: event.target.value })}>
          <option value="AUTO">Predeterminada{charge ? ` · ${charge.tariff.name}` : ''}</option>
          {tariffs.map((tariff) => <option key={tariff.id} value={tariff.id}>
            {tariff.name}{!waived && ` · ${formatMxnCents(tariff.amount_cents)}`}
          </option>)}
        </select>
        <p role="status">{charge?.state === 'REMOVED' ? 'Envío retirado manualmente'
          : waived ? 'Envío gratis por monto mínimo'
          : charge ? `${formatMxnCents(charge.charged_cents)} · IVA 16% incluido` : 'Calculando envío…'}</p>
        {charge && !waived && <p>Base del envío: {formatMxnCents(charge.net_cents)} · IVA: {formatMxnCents(charge.tax_cents)}</p>}
        <Button variant="secondary" onClick={() => onChange({ mode: removed ? 'AUTO' : 'REMOVED' })}>
          {removed ? 'Restaurar envío' : 'Quitar envío'}
        </Button>
      </div>
    </details>
    {error && <p role="alert">{error}</p>}
  </fieldset>;
}
