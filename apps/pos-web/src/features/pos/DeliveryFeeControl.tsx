import { useEffect, useState } from 'react';
import { fetchApi, type DeliveryCharge, type DeliveryOptions, type DeliverySelection } from '@restaurantos/api-client';
import { Button } from '@restaurantos/ui';
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
  return <fieldset className="delivery-fee-control" style={{ margin: '12px 0', padding: 12, border: '1px solid #d1d5db', borderRadius: 8 }}>
    <legend>Servicio de domicilio</legend>
    {error && <p role="alert">{error}</p>}
    <label htmlFor="delivery-tariff">Tarifa de envío</label>
    <select id="delivery-tariff" disabled={removed || !options} style={{ width: '100%', padding: 8 }}
      value={selection.mode === 'SELECTED' ? selection.tariff_id : 'AUTO'}
      onChange={(event) => onChange(event.target.value === 'AUTO' ? { mode: 'AUTO' }
        : { mode: 'SELECTED', tariff_id: event.target.value })}>
      <option value="AUTO">Predeterminada{charge ? ` · ${charge.tariff.name}` : ''}</option>
      {tariffs.map((tariff) => <option key={tariff.id} value={tariff.id}>{tariff.name} · {formatMxnCents(tariff.amount_cents)}</option>)}
    </select>
    <p role="status">{charge?.state === 'REMOVED' ? 'Envío retirado manualmente'
      : charge?.state === 'WAIVED_THRESHOLD' ? 'Envío gratis por monto mínimo'
      : charge ? `${formatMxnCents(charge.charged_cents)} · IVA 16% incluido` : 'Calculando envío…'}</p>
    {charge && charge.state !== 'WAIVED_THRESHOLD' && <p>Base del envío: {formatMxnCents(charge.net_cents)} · IVA: {formatMxnCents(charge.tax_cents)}</p>}
    <Button variant="secondary" onClick={() => onChange({ mode: removed ? 'AUTO' : 'REMOVED' })}>
      {removed ? 'Restaurar envío' : 'Quitar envío'}
    </Button>
  </fieldset>;
}
