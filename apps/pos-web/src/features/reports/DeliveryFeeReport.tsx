import { useEffect, useState } from 'react';
import { fetchApi } from '@restaurantos/api-client';
import { formatMxnCents } from '../pos/cartMoney';

interface Report {
  summary: { gross_cents: number; net_cents: number; tax_cents: number; entry_count: number };
  legacy_not_captured: number;
  items: { id: string; folio: string; kind: string; state: string; gross_cents: number; net_cents: number; tax_cents: number }[];
  has_more: boolean; next_offset: number | null;
}

export function DeliveryFeeReport({ branchId, start, end }: { branchId: string; start: string; end: string }) {
  const [data, setData] = useState<Report | null>(null);
  const [error, setError] = useState('');
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setData(null);
    const params = new URLSearchParams({ branch_id: branchId, start, end, offset: String(offset), limit: '50' });
    fetchApi<Report>(`/reports/delivery-fees?${params}`, { signal: controller.signal }).then((value) => {
      if (!controller.signal.aborted) setData(value);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'No fue posible cargar los envíos.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [branchId, start, end, offset]);
  return <section className="sales-monitor-breakdown" aria-labelledby="delivery-report-title">
    <h2 id="delivery-report-title">Cargos de domicilio</h2>
    <p>Todos los cobros y ajustes de esta sucursal en el periodo seleccionado. Los filtros de familia, caja y turno del monitor no limitan este desglose.</p>
    {loading && <p role="status">Cargando envíos…</p>}
    {error && <p role="alert">{error}</p>}
    {data && <>
      <p>Cobrado: <strong>{formatMxnCents(data.summary.gross_cents)}</strong> · Base: {formatMxnCents(data.summary.net_cents)} · IVA 16% incluido: {formatMxnCents(data.summary.tax_cents)}</p>
      {data.legacy_not_captured > 0 && <p>{data.legacy_not_captured} pedidos históricos sin desglose de envío; su importe no se presume cero.</p>}
      <div className="sales-monitor-table-scroll"><table><thead><tr><th>Folio</th><th>Movimiento</th><th>Estado</th><th>Cargo</th><th>Base</th><th>IVA</th></tr></thead><tbody>
        {data.items.map((item) => <tr key={item.id}><td>{item.folio}</td><td>{item.kind === 'PAYMENT' ? 'Cobro' : 'Corrección'}</td><td>{{ CHARGED: 'Cobrado', REMOVED: 'Retirado', WAIVED_THRESHOLD: 'Gratis por monto' }[item.state] || item.state}</td><td>{formatMxnCents(item.gross_cents)}</td><td>{formatMxnCents(item.net_cents)}</td><td>{formatMxnCents(item.tax_cents)}</td></tr>)}
      </tbody></table></div>
      {offset > 0 && <button type="button" disabled={loading} onClick={() => setOffset(Math.max(0, offset - 50))}>Anteriores</button>}
      {data.has_more && <button type="button" disabled={loading} onClick={() => setOffset(data.next_offset || 0)}>Siguientes</button>}
    </>}
  </section>;
}
