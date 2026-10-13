import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Building2, CheckCircle2, PackageCheck, Plus, Trash2, XCircle } from 'lucide-react';
import { Button, Badge } from '@restaurantos/ui';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { useAdminSession } from '../../lib/adminSession';
import { corporateIntentKey, createCorporateIntent, definitiveCorporateRejection, explicitReceiptQuantity, pendingBaseQuantity, readCorporateIntent, type CorporateIntent } from './corporateIntent';
import './CorporatePurchaseWorkspace.css';

interface Supplier { id: string; commercial_name: string; }
interface Presentation { id: string; supplier_id: string; name: string; item_name: string; item_sku: string; last_net_price: number; }
interface Destination { branch_id: string; branch_name: string; legal_entity_id: string; warehouse_id: string; warehouse_name: string; }
interface LegalEntity { id: string; name: string; }
interface Allocation { id: string; branch_id: string; warehouse_id: string; quantity: string; received_quantity: string; pending_quantity: string; base_quantity: string; received_base_quantity: string; }
interface CorporateLine { id: string; item_id: string; presentation_id: string; quantity: string; presentation_snapshot: { name: string; item_name?: string; item_sku?: string; base_unit_code?: string; commercial_unit_code?: string; base_unit_id: string; commercial_unit_id: string; }; allocations: Allocation[]; }
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
  const { session, assertCurrentAuthority } = useAdminSession();
  const authority = useMemo(() => ({ organization_id: session.organization_id || '', actor_id: session.user.id }), [session.organization_id, session.user.id]);
  const scope = corporateIntentKey(authority);
  const [pendingIntent, setPendingIntent] = useState<CorporateIntent | null>(null);
  const [journalReady, setJournalReady] = useState(false);
  const inFlight = useRef(false);
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
  const orders = useQuery<CorporateOrderSummary[]>({ queryKey: ['corporate-purchases', scope, page], queryFn: () => fetchApi(`/corporate-purchases?limit=${PAGE_SIZE + 1}&offset=${page * PAGE_SIZE}`) });
  const options = useQuery<Options>({ queryKey: ['corporate-purchase-options', scope], queryFn: () => fetchApi('/corporate-purchases/options') });
  const destinations = useMemo(() => (options.data?.destinations || []).filter(item => item.legal_entity_id === legalEntityId), [options.data, legalEntityId]);
  const visibleOrders = orders.data?.slice(0, PAGE_SIZE) || [];
  const hasNextPage = (orders.data?.length || 0) > PAGE_SIZE;
  const mutationDisabled = busy || !journalReady || Boolean(pendingIntent);
  useEffect(() => {
    const load = () => {
      try { setPendingIntent(readCorporateIntent(localStorage, authority)); setJournalReady(true); }
      catch (cause) { setJournalReady(false); setError(cause instanceof Error ? cause.message : 'No se pudo recuperar la operación.'); }
    };
    load();
    const changed = (event: StorageEvent) => { if (event.key === scope || event.key === null) load(); };
    window.addEventListener('storage', changed);
    return () => window.removeEventListener('storage', changed);
  }, [authority, scope]);

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
  const runMutation = async (endpoint?: string, body?: string, recovering = false) => {
    if (inFlight.current || !canManage || !journalReady) return;
    inFlight.current = true; setBusy(true); setError('');
    try {
      assertCurrentAuthority();
      if (!navigator.locks) throw new Error('No se pudo asegurar la operación. No se envió ningún comando.');
      const result = await navigator.locks.request(scope, async () => {
        const stored = readCorporateIntent(localStorage, authority);
        if (stored && !recovering) { setPendingIntent(stored); throw new Error('Recupera la operación pendiente antes de iniciar otra.'); }
        if (recovering && !stored) throw new Error('La operación pendiente ya fue resuelta. Actualiza la consulta.');
        assertCurrentAuthority();
        const intent = stored || createCorporateIntent(localStorage, authority, endpoint || '', body || '', `corporate:${uid()}`);
        setPendingIntent(intent);
        try {
          const response = await fetchApi<CorporateOrder | { order: CorporateOrder }>(intent.endpoint, { method: 'POST', headers: { 'Idempotency-Key': intent.key }, body: intent.body });
          const order = 'order' in response ? response.order : response;
          if (!order.id || !Number.isInteger(order.version)) throw new Error('La respuesta requiere recuperación antes de otra operación.');
          localStorage.removeItem(scope); setPendingIntent(null);
          return { order, created: intent.endpoint === '/corporate-purchases' };
        } catch (cause) {
          if (cause instanceof ApiError && definitiveCorporateRejection(cause.status, cause.code)) {
            localStorage.removeItem(scope); setPendingIntent(null);
          }
          throw cause;
        }
      });
      if (result.created) reset();
      setReceiptQuantities({}); setSelected(result.order);
      try { await refresh(result.order.id); }
      catch { setError('Operación confirmada. No se pudo actualizar la consulta; vuelve a consultarla.'); }
    } catch (cause) {
      setError(cause instanceof TypeError ? 'No se pudo comprobar el resultado. Recupera la operación pendiente.'
        : cause instanceof Error ? cause.message : 'La operación requiere recuperación.');
    }
    finally { inFlight.current = false; setBusy(false); }
  };
  const createOrder = async () => {
    if (mutationDisabled) return;
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
      await runMutation('/corporate-purchases', JSON.stringify(payload));
  };
  const approve = async (order: CorporateOrder) => {
    await runMutation(`/corporate-purchases/${order.id}/approve`, JSON.stringify({ expected_version: order.version }));
  };
  const cancel = async (order: CorporateOrder) => {
    const reason = window.prompt('Motivo obligatorio de cancelación');
    if (!reason) return;
    await runMutation(`/corporate-purchases/${order.id}/cancel`, JSON.stringify({ expected_version: order.version, reason }));
  };
  const receive = async (order: CorporateOrder, line: CorporateLine, allocation: Allocation) => {
    try {
      const quantity = explicitReceiptQuantity(receiptQuantities[allocation.id], allocation.pending_quantity);
      const destination = options.data?.destinations.find(item => item.branch_id === allocation.branch_id && item.warehouse_id === allocation.warehouse_id);
      if (!window.confirm(`Confirmar recepción: ${quantity} de ${line.presentation_snapshot.name} (${line.presentation_snapshot.item_name || line.item_id}) en ${destination?.branch_name || allocation.branch_id} · ${destination?.warehouse_name || allocation.warehouse_id}.`)) return;
      await runMutation(`/corporate-purchases/${order.id}/receipts`, JSON.stringify({ expected_version: order.version, branch_id: allocation.branch_id, warehouse_id: allocation.warehouse_id, received_at: new Date().toISOString().slice(0, 10), lines: [{ allocation_id: allocation.id, quantity }] }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No fue posible recibir.'); }
  };

  return <section aria-label="Compras corporativas">
    <div className="corporate-purchase-header">
      <div><h1 className="premium-header-title">Compra corporativa</h1><p className="premium-header-subtitle">Ordena una vez y distribuye la recepción a los almacenes de cada sucursal.</p></div>
      {canManage && <button className="premium-add-btn" disabled={mutationDisabled} onClick={() => setCreating(value => !value)}><Plus size={18} /> Nueva orden corporativa</button>}
    </div>
    {error && <p role="alert" style={{ color: '#b91c1c', display: 'flex', gap: 8 }}><AlertCircle size={18} />{error}</p>}
    {pendingIntent && <div role="status" className="premium-card" style={{ padding: 16, marginBottom: 16 }}><p>Hay una operación pendiente de comprobar. Recupera su resultado antes de iniciar otra.</p>{canManage && <Button variant="primary" disabled={busy || !journalReady} onClick={() => void runMutation(undefined, undefined, true)}>Recuperar operación pendiente</Button>}</div>}
    {creating && <fieldset disabled={mutationDisabled} className="premium-card" style={{ padding: 24, marginBottom: 24, display: 'grid', gap: 18, minWidth: 0, border: 0 }}>
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
    </fieldset>}
    <div className="corporate-purchase-master-detail">
      <div className="premium-card"><table className="premium-table"><thead><tr><th>Folio</th><th>Total</th><th>Estado</th></tr></thead><tbody>{visibleOrders.map(order => <tr key={order.id} onClick={() => void selectOrder(order.id)} style={{ cursor: 'pointer' }}><td><strong>{order.folio}</strong></td><td>${order.total}</td><td><Badge variant={order.status === 'RECEIVED' ? 'success' : 'info'}>{statusLabel[order.status] || order.status}</Badge></td></tr>)}</tbody></table>{visibleOrders.length === 0 && <p style={{ padding: 20 }}>No hay órdenes corporativas.</p>}<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 12 }}><Button variant="secondary" disabled={page === 0 || orders.isFetching} onClick={() => setPage(current => Math.max(0, current - 1))}>Anterior</Button><small>Página {page + 1}</small><Button variant="secondary" disabled={!hasNextPage || orders.isFetching} onClick={() => setPage(current => current + 1)}>Siguiente</Button></div></div>
      <div className="premium-card" style={{ padding: 22 }}>
        {!selected ? <div className="premium-empty-state"><Building2 size={48} /><h3>Selecciona una orden</h3></div> : <div style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}><div><h2 style={{ margin: 0 }}>{selected.folio}</h2><small>{statusLabel[selected.status]}</small></div><div style={{ display: 'flex', gap: 8 }}>{canManage && selected.status === 'DRAFT' && <><Button variant="primary" disabled={mutationDisabled} onClick={() => void approve(selected)}><CheckCircle2 size={16} /> Aprobar</Button><Button variant="secondary" disabled={mutationDisabled} onClick={() => void cancel(selected)}><XCircle size={16} /> Cancelar</Button></>}</div></div>
          {selected.lines.flatMap(line => line.allocations.map(allocation => {
            const destination = options.data?.destinations.find(item => item.branch_id === allocation.branch_id && item.warehouse_id === allocation.warehouse_id);
            let hasPending = false;
            let validQuantity = false;
            try { explicitReceiptQuantity(allocation.pending_quantity, allocation.pending_quantity); hasPending = true; } catch { /* No positive remainder. */ }
            try { explicitReceiptQuantity(receiptQuantities[allocation.id], allocation.pending_quantity); validQuantity = true; } catch { /* Capture remains incomplete. */ }
            const snapshot = line.presentation_snapshot;
            return <div key={allocation.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 14 }}>
              <strong>{snapshot.item_name || line.item_id} · {snapshot.item_sku ? `SKU: ${snapshot.item_sku}` : `SKU no conservado · ID del insumo: ${line.item_id}`}</strong>
              <p>{snapshot.name || line.presentation_id} · Unidad comercial: {snapshot.commercial_unit_code || snapshot.commercial_unit_id} · Unidad base: {snapshot.base_unit_code || snapshot.base_unit_id}</p>
              <strong>{destination?.branch_name || allocation.branch_id} · {destination?.warehouse_name || allocation.warehouse_id}</strong>
              <p>Comercial — Ordenado: {allocation.quantity} · Recibido: {allocation.received_quantity} · Cantidad pendiente: {allocation.pending_quantity}</p>
              <p>Base — Ordenado: {allocation.base_quantity} · Recibido: {allocation.received_base_quantity} · Pendiente: {pendingBaseQuantity(allocation.base_quantity, allocation.received_base_quantity)}</p>
              {canManage && hasPending && ['APPROVED', 'PARTIALLY_RECEIVED'].includes(selected.status) && <div className="corporate-purchase-receipt-row">
                <input className="premium-input" inputMode="decimal" aria-label="Cantidad a recibir" disabled={mutationDisabled} value={receiptQuantities[allocation.id] ?? ''} onChange={event => setReceiptQuantities(current => ({ ...current, [allocation.id]: event.target.value }))} />
                <Button variant="primary" disabled={mutationDisabled || !validQuantity} onClick={() => void receive(selected, line, allocation)}><PackageCheck size={16} /> Recibir</Button>
              </div>}
            </div>;
          }))}
          {['APPROVED', 'PARTIALLY_RECEIVED', 'RECEIVED'].includes(selected.status) && <small>Las recepciones confirmadas son inmutables; una corrección requiere compensación autorizada.</small>}
        </div>}
      </div>
    </div>
  </section>;
}
