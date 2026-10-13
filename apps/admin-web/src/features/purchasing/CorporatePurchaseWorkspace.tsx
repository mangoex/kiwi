import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Building2, CheckCircle2, PackageCheck, Plus, Trash2, XCircle } from 'lucide-react';
import { Button, Badge } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import './CorporatePurchaseWorkspace.css';

interface Supplier { id: string; commercial_name: string; }
interface Presentation { id: string; supplier_id: string; name: string; item_name: string; item_sku: string; last_net_price: number; }
interface Destination { branch_id: string; branch_name: string; legal_entity_id: string; warehouse_id: string; warehouse_name: string; }
interface LegalEntity { id: string; name: string; }
interface Allocation { id: string; branch_id: string; warehouse_id: string; quantity: string; received_quantity: string; pending_quantity: string; }
interface CorporateLine { id: string; presentation_id: string; quantity: string; allocations: Allocation[]; }
interface CorporateOrder { id: string; legal_entity_id: string; supplier_id: string; folio: string; order_date: string; currency: string; total: string; status: string; version: number; lines: CorporateLine[]; }
type CorporateOrderSummary = Omit<CorporateOrder, 'lines'>;
interface Options { legal_entities: LegalEntity[]; destinations: Destination[]; suppliers: Supplier[]; presentations: Presentation[]; }
interface DraftAllocation { id: string; destination: string; quantity: string; }
interface DraftLine { id: string; presentation_id: string; quantity: string; unit_price: string; discount: string; tax: string; allocations: DraftAllocation[]; }

const uid = () => crypto.randomUUID();
const PAGE_SIZE = 50;
const emptyAllocation = (): DraftAllocation => ({ id: uid(), destination: '', quantity: '' });
const emptyLine = (): DraftLine => ({ id: uid(), presentation_id: '', quantity: '', unit_price: '', discount: '0', tax: '0', allocations: [emptyAllocation()] });
const statusLabel: Record<string, string> = { DRAFT: 'Borrador', APPROVED: 'Aprobada', PARTIALLY_RECEIVED: 'Recepción parcial', RECEIVED: 'Recibida', CANCELLED: 'Cancelada' };

export function CorporatePurchaseWorkspace({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<CorporateOrder | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [legalEntityId, setLegalEntityId] = useState('');
  const [supplierId, setSupplierId] = useState('');
  const [folio, setFolio] = useState('');
  const [orderDate, setOrderDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()]);
  const [receiptQuantities, setReceiptQuantities] = useState<Record<string, string>>({});
  const [page, setPage] = useState(0);
  const orders = useQuery<CorporateOrderSummary[]>({ queryKey: ['corporate-purchases', page], queryFn: () => fetchApi(`/corporate-purchases?limit=${PAGE_SIZE + 1}&offset=${page * PAGE_SIZE}`) });
  const options = useQuery<Options>({ queryKey: ['corporate-purchase-options'], queryFn: () => fetchApi('/corporate-purchases/options') });
  const destinations = useMemo(() => (options.data?.destinations || []).filter(item => item.legal_entity_id === legalEntityId), [options.data, legalEntityId]);
  const visibleOrders = orders.data?.slice(0, PAGE_SIZE) || [];
  const hasNextPage = (orders.data?.length || 0) > PAGE_SIZE;

  const refresh = async (orderId?: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['corporate-purchases'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory-costs'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'stock'] }),
    ]);
    if (orderId) {
      const latest = await fetchApi<CorporateOrder>(`/corporate-purchases/${orderId}`);
      setSelected(latest);
    }
  };
  const updateLine = (lineId: string, patch: Partial<DraftLine>) => setLines(current => current.map(line => line.id === lineId ? { ...line, ...patch } : line));
  const updateAllocation = (lineId: string, allocationId: string, patch: Partial<DraftAllocation>) => setLines(current => current.map(line => line.id !== lineId ? line : ({ ...line, allocations: line.allocations.map(item => item.id === allocationId ? { ...item, ...patch } : item) })));
  const selectOrder = async (orderId: string) => {
    setError('');
    try { setSelected(await fetchApi<CorporateOrder>(`/corporate-purchases/${orderId}`)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'No fue posible consultar la orden.'); }
  };
  const reset = () => { setLegalEntityId(''); setSupplierId(''); setFolio(''); setNotes(''); setLines([emptyLine()]); setCreating(false); };
  const createOrder = async () => {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const payload = {
        legal_entity_id: legalEntityId, supplier_id: supplierId, folio, order_date: orderDate,
        currency: 'MXN', notes: notes || null,
        lines: lines.map(line => ({
          presentation_id: line.presentation_id, quantity: line.quantity, unit_price: line.unit_price,
          discount: line.discount, tax: line.tax,
          allocations: line.allocations.map(item => {
            const destination = destinations.find(row => `${row.branch_id}|${row.warehouse_id}` === item.destination);
            return { branch_id: destination?.branch_id || '', warehouse_id: destination?.warehouse_id || '', quantity: item.quantity };
          }),
        })),
      };
      const created = await fetchApi<CorporateOrder>('/corporate-purchases', { method: 'POST', headers: { 'Idempotency-Key': `corporate-create:${uid()}` }, body: JSON.stringify(payload) });
      reset(); setSelected(created); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No fue posible crear la orden.'); }
    finally { setBusy(false); }
  };
  const approve = async (order: CorporateOrder) => {
    setBusy(true); setError('');
    try {
      const result = await fetchApi<CorporateOrder>(`/corporate-purchases/${order.id}/approve`, { method: 'POST', headers: { 'Idempotency-Key': `corporate-approve:${uid()}` }, body: JSON.stringify({ expected_version: order.version }) });
      setSelected(result); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No fue posible aprobar.'); }
    finally { setBusy(false); }
  };
  const cancel = async (order: CorporateOrder) => {
    const reason = window.prompt('Motivo obligatorio de cancelación');
    if (!reason) return;
    setBusy(true); setError('');
    try {
      const result = await fetchApi<CorporateOrder>(`/corporate-purchases/${order.id}/cancel`, { method: 'POST', headers: { 'Idempotency-Key': `corporate-cancel:${uid()}` }, body: JSON.stringify({ expected_version: order.version, reason }) });
      setSelected(result); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No fue posible cancelar.'); }
    finally { setBusy(false); }
  };
  const receive = async (order: CorporateOrder, allocation: Allocation) => {
    const quantity = receiptQuantities[allocation.id] || allocation.pending_quantity;
    setBusy(true); setError('');
    try {
      const response = await fetchApi<{order: CorporateOrder}>(`/corporate-purchases/${order.id}/receipts`, { method: 'POST', headers: { 'Idempotency-Key': `corporate-receive:${uid()}` }, body: JSON.stringify({ expected_version: order.version, branch_id: allocation.branch_id, warehouse_id: allocation.warehouse_id, received_at: new Date().toISOString().slice(0, 10), lines: [{ allocation_id: allocation.id, quantity }] }) });
      setReceiptQuantities(current => ({ ...current, [allocation.id]: '' })); setSelected(response.order); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No fue posible recibir.'); }
    finally { setBusy(false); }
  };

  return <section aria-label="Compras corporativas">
    <div className="corporate-purchase-header">
      <div><h1 className="premium-header-title">Compra corporativa</h1><p className="premium-header-subtitle">Ordena una vez y distribuye la recepción a los almacenes de cada sucursal.</p></div>
      {canManage && <button className="premium-add-btn" onClick={() => setCreating(value => !value)}><Plus size={18} /> Nueva orden corporativa</button>}
    </div>
    {error && <p role="alert" style={{ color: '#b91c1c', display: 'flex', gap: 8 }}><AlertCircle size={18} />{error}</p>}
    {creating && <div className="premium-card" style={{ padding: 24, marginBottom: 24, display: 'grid', gap: 18 }}>
      <h2 style={{ margin: 0 }}>Nueva orden</h2>
      <div className="corporate-purchase-meta-grid">
        <label className="corporate-purchase-field">Razón social<select className="premium-select" value={legalEntityId} onChange={event => { setLegalEntityId(event.target.value); setLines([emptyLine()]); }}><option value="">Selecciona</option>{options.data?.legal_entities.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="corporate-purchase-field">Proveedor<select className="premium-select" value={supplierId} onChange={event => setSupplierId(event.target.value)}><option value="">Selecciona</option>{(options.data?.suppliers || []).map(item => <option key={item.id} value={item.id}>{item.commercial_name}</option>)}</select></label>
        <label className="corporate-purchase-field">Folio<input className="premium-input" value={folio} onChange={event => setFolio(event.target.value)} /></label>
        <label className="corporate-purchase-field">Fecha<input className="premium-input" type="date" value={orderDate} onChange={event => setOrderDate(event.target.value)} /></label>
      </div>
      {lines.map((line, index) => <div key={line.id} style={{ border: '1px solid #e2e8f0', borderRadius: 12, padding: 16, display: 'grid', gap: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}><strong>Partida {index + 1}</strong>{lines.length > 1 && <button type="button" aria-label="Quitar partida" onClick={() => setLines(current => current.filter(item => item.id !== line.id))}><Trash2 size={16} /></button>}</div>
        <div className="corporate-purchase-line-grid">
          <label className="corporate-purchase-field corporate-purchase-presentation">Presentación<select className="premium-select" value={line.presentation_id} onChange={event => { const presentation = options.data?.presentations?.find(item => item.id === event.target.value); updateLine(line.id, { presentation_id: event.target.value, unit_price: String(presentation?.last_net_price ?? '') }); }}><option value="">Selecciona</option>{(options.data?.presentations || []).filter(item => item.supplier_id === supplierId).map(item => <option key={item.id} value={item.id}>{item.item_name} · {item.item_sku} · {item.name}</option>)}</select></label>
          <label className="corporate-purchase-field">Cantidad<input className="premium-input" inputMode="decimal" value={line.quantity} onChange={event => updateLine(line.id, { quantity: event.target.value })} /></label>
          <label className="corporate-purchase-field">Precio unitario<input className="premium-input" inputMode="decimal" value={line.unit_price} onChange={event => updateLine(line.id, { unit_price: event.target.value })} /></label>
          <label className="corporate-purchase-field">Descuento<input className="premium-input" inputMode="decimal" value={line.discount} onChange={event => updateLine(line.id, { discount: event.target.value })} /></label>
          <label className="corporate-purchase-field">Impuesto<input className="premium-input" inputMode="decimal" value={line.tax} onChange={event => updateLine(line.id, { tax: event.target.value })} /></label>
        </div>
        <strong>Distribución por sucursal</strong>
        {line.allocations.map(allocation => <div key={allocation.id} className="corporate-purchase-allocation-row">
          <select className="premium-select" aria-label="Sucursal y almacén" value={allocation.destination} onChange={event => updateAllocation(line.id, allocation.id, { destination: event.target.value })}><option value="">Selecciona destino</option>{destinations.map(item => <option key={item.warehouse_id} value={`${item.branch_id}|${item.warehouse_id}`}>{item.branch_name} · {item.warehouse_name}</option>)}</select>
          <input className="premium-input" inputMode="decimal" aria-label="Cantidad asignada" value={allocation.quantity} onChange={event => updateAllocation(line.id, allocation.id, { quantity: event.target.value })} />
          {line.allocations.length > 1 && <button type="button" aria-label="Quitar destino" onClick={() => updateLine(line.id, { allocations: line.allocations.filter(item => item.id !== allocation.id) })}><Trash2 size={16} /></button>}
        </div>)}
        <Button variant="secondary" onClick={() => updateLine(line.id, { allocations: [...line.allocations, emptyAllocation()] })}><Plus size={15} /> Agregar destino</Button>
      </div>)}
      <div style={{ display: 'flex', gap: 10 }}><Button variant="secondary" onClick={() => setLines(current => [...current, emptyLine()])}><Plus size={15} /> Agregar partida</Button><Button variant="primary" disabled={busy} onClick={() => void createOrder()}>Guardar borrador</Button><Button variant="secondary" onClick={reset}>Cancelar</Button></div>
      <label className="corporate-purchase-field">Notas<input className="premium-input" value={notes} onChange={event => setNotes(event.target.value)} /></label>
      <small>Guardar o aprobar no mueve inventario ni caja. Los efectos nacen al recibir en cada almacén.</small>
    </div>}
    <div className="corporate-purchase-master-detail">
      <div className="premium-card"><table className="premium-table"><thead><tr><th>Folio</th><th>Total</th><th>Estado</th></tr></thead><tbody>{visibleOrders.map(order => <tr key={order.id} onClick={() => void selectOrder(order.id)} style={{ cursor: 'pointer' }}><td><strong>{order.folio}</strong></td><td>${order.total}</td><td><Badge variant={order.status === 'RECEIVED' ? 'success' : 'info'}>{statusLabel[order.status] || order.status}</Badge></td></tr>)}</tbody></table>{visibleOrders.length === 0 && <p style={{ padding: 20 }}>No hay órdenes corporativas.</p>}<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 12 }}><Button variant="secondary" disabled={page === 0 || orders.isFetching} onClick={() => setPage(current => Math.max(0, current - 1))}>Anterior</Button><small>Página {page + 1}</small><Button variant="secondary" disabled={!hasNextPage || orders.isFetching} onClick={() => setPage(current => current + 1)}>Siguiente</Button></div></div>
      <div className="premium-card" style={{ padding: 22 }}>
        {!selected ? <div className="premium-empty-state"><Building2 size={48} /><h3>Selecciona una orden</h3></div> : <div style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}><div><h2 style={{ margin: 0 }}>{selected.folio}</h2><small>{statusLabel[selected.status]}</small></div><div style={{ display: 'flex', gap: 8 }}>{canManage && selected.status === 'DRAFT' && <><Button variant="primary" disabled={busy} onClick={() => void approve(selected)}><CheckCircle2 size={16} /> Aprobar</Button><Button variant="secondary" disabled={busy} onClick={() => void cancel(selected)}><XCircle size={16} /> Cancelar</Button></>}</div></div>
          {selected.lines.flatMap(line => line.allocations.map(allocation => {
            const destination = options.data?.destinations.find(item => item.branch_id === allocation.branch_id && item.warehouse_id === allocation.warehouse_id);
            const pending = Number(allocation.pending_quantity);
            return <div key={allocation.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 14 }}><strong>{destination?.branch_name || allocation.branch_id} · {destination?.warehouse_name || allocation.warehouse_id}</strong><p>Cantidad pendiente: {allocation.pending_quantity}</p>{canManage && pending > 0 && ['APPROVED', 'PARTIALLY_RECEIVED'].includes(selected.status) && <div className="corporate-purchase-receipt-row"><input className="premium-input" inputMode="decimal" aria-label="Cantidad a recibir" value={receiptQuantities[allocation.id] ?? allocation.pending_quantity} onChange={event => setReceiptQuantities(current => ({ ...current, [allocation.id]: event.target.value }))} /><Button variant="primary" disabled={busy} onClick={() => void receive(selected, allocation)}><PackageCheck size={16} /> Recibir</Button></div>}</div>;
          }))}
          {['APPROVED', 'PARTIALLY_RECEIVED', 'RECEIVED'].includes(selected.status) && <small>Las recepciones confirmadas son inmutables; una corrección requiere compensación autorizada.</small>}
        </div>}
      </div>
    </div>
  </section>;
}
