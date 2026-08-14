import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card } from '@restaurantos/ui';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Calendar, ChevronRight, Clock, CreditCard, Pencil, ReceiptText, RefreshCcw, Search, X } from 'lucide-react';
import { usePosSession } from '../../session';
import { localDayUtcBounds } from '../reports/salesMonitorState';

type PaymentMethod = 'cash' | 'debit_card' | 'credit_card' | 'transfer';
type RequestStatus = 'REQUESTED' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'APPLIED';

interface OrderAccount {
  id: string;
  folio: string;
  status: string;
  payment_status?: 'PENDING' | 'CONFIRMED';
  total_cents: number;
  created_at: string;
  customer_label: string | null;
  service_type: string | null;
  register_code: string | null;
  cash_shift_id: string | null;
  reopen_eligible: boolean;
  active_reopen_request_status: RequestStatus | null;
}

interface OrderDetail extends OrderAccount {
  version: number;
  editable: boolean;
  edit_block_reason?: string | null;
  payment_method_intent?: PaymentMethod | null;
  lines: Array<{ id: string; product_name: string; quantity: number; line_total_cents: number }>;
  payments: Array<{ id: string; method: string; status: string; amount_cents: number }>;
  sales_operation_snapshots?: Array<{ id: string; quality_status?: string; captured_at?: string }>;
}

interface OrderAccountsResponse { items: OrderAccount[]; next_cursor: string | null }
interface ReopenRequest {
  id: string;
  branch_id: string;
  order_id: string;
  status: RequestStatus;
  reason: string;
  evidence_refs: string[];
  decision_reason: string | null;
  requested_at: string;
}
interface ReopenRequestsResponse { items: ReopenRequest[]; next_cursor: string | null }

const PAYMENT_METHODS: Array<{ value: PaymentMethod; label: string; hint: string }> = [
  { value: 'cash', label: 'Efectivo', hint: 'Pago en caja' },
  { value: 'debit_card', label: 'Débito', hint: 'Tarjeta de débito' },
  { value: 'credit_card', label: 'Crédito', hint: 'Tarjeta de crédito' },
  { value: 'transfer', label: 'Transferencia', hint: 'Transferencia bancaria' },
];

const newIdempotencyKey = () => globalThis.crypto?.randomUUID?.() ?? `pco005-${Date.now()}-${Math.random().toString(36).slice(2)}`;
const requestSignature = (orderId: string, reason: string, evidence: string[]) => JSON.stringify({ orderId, reason: reason.trim(), evidence });
const decisionSignature = (requestId: string, decision: string, decisionReason: string) => JSON.stringify({ requestId, decision, decisionReason: decisionReason.trim() });

const getStatusConfig = (status: string) => {
  switch (status) {
    case 'PENDING_PAYMENT': return { label: 'Pendiente de pago', bg: '#fff7ed', color: '#c2410c', border: '#fed7aa' };
    case 'COMPLETED': case 'CLOSED': case 'CERRADO': return { label: 'Completado', bg: '#ecfdf5', color: '#059669', border: '#a7f3d0' };
    case 'ACCEPTED': case 'PREPARING': return { label: 'Preparando', bg: '#eff6ff', color: '#2563eb', border: '#bfdbfe' };
    case 'READY': return { label: 'Listo', bg: '#fef3c7', color: '#d97706', border: '#fde68a' };
    case 'CANCELLED': return { label: 'Cancelado', bg: '#fef2f2', color: '#dc2626', border: '#fecaca' };
    default: return { label: status, bg: '#f1f5f9', color: '#475569', border: '#e2e8f0' };
  }
};
const getTypeLabel = (type?: string | null) => ({ 'dine-in': 'En sucursal', takeout: 'Para llevar', delivery: 'A domicilio' }[type || ''] || type || 'General');

const History = () => {
  const navigate = useNavigate();
  const { hasPermission, session } = usePosSession();
  const canRequestReopen = hasPermission('orders.reopen.request');
  const canAuthorizeReopen = hasPermission('orders.reopen.authorize');
  const branchId = session?.active_branch?.id || '';
  const branchTimezone = session?.active_branch?.timezone || 'UTC';
  const configuredRegisterId = (localStorage.getItem('pos_register_id') || '').trim();
  const [orders, setOrders] = useState<OrderAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [day, setDay] = useState('');
  const [cashShiftId, setCashShiftId] = useState('');
  const [registerCode, setRegisterCode] = useState('');
  const [serviceType, setServiceType] = useState('');
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [selected, setSelected] = useState<OrderDetail | null>(null);
  const [activeOrderId, setActiveOrderId] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash');
  const [paymentPending, setPaymentPending] = useState(false);
  const [listError, setListError] = useState('');
  const [detailError, setDetailError] = useState('');
  const [reopenReason, setReopenReason] = useState('');
  const [evidenceText, setEvidenceText] = useState('');
  const [reopenPending, setReopenPending] = useState(false);
  const [reopenError, setReopenError] = useState('');
  const requestKeyRef = useRef<{ signature: string; key: string } | null>(null);
  const decisionKeysRef = useRef(new Map<string, { signature: string; key: string }>());
  const [requests, setRequests] = useState<ReopenRequest[]>([]);
  const [requestsCursor, setRequestsCursor] = useState<string | null>(null);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [requestsError, setRequestsError] = useState('');
  const [decisionReasonById, setDecisionReasonById] = useState<Record<string, string>>({});
  const [decisionPendingId, setDecisionPendingId] = useState<string | null>(null);
  const accountRequestSequence = useRef(0);

  const loadAccounts = useCallback(async (cursor: string | null = null, append = false) => {
    const sequence = ++accountRequestSequence.current;
    setLoading(true); setListError('');
    const params = new URLSearchParams({ limit: '25' });
    if (branchId) params.set('branch_id', branchId);
    if (day) {
      const bounds = localDayUtcBounds(day, branchTimezone);
      params.set('from_utc', bounds.fromUtc); params.set('to_utc', bounds.toUtc);
    }
    if (cashShiftId) params.set('cash_shift_id', cashShiftId);
    if (registerCode) params.set('register_code', registerCode);
    if (serviceType) params.set('service_type', serviceType);
    const search = searchQuery.trim();
    if (search.length >= 2) params.set('q', search);
    if (cursor) params.set('cursor', cursor);
    try {
      const data = await fetchApi<OrderAccountsResponse>(`/orders/accounts?${params.toString()}`, { headers: { 'Cache-Control': 'no-cache' } });
      if (sequence !== accountRequestSequence.current) return;
      setOrders((previous) => append ? [...previous, ...data.items] : data.items);
      setNextCursor(data.next_cursor);
    } catch (reason) {
      if (sequence !== accountRequestSequence.current) return;
      setListError(reason instanceof ApiError ? reason.message : 'No fue posible cargar las cuentas.');
      if (!append) setOrders([]);
    } finally {
      if (sequence === accountRequestSequence.current) setLoading(false);
    }
  }, [branchId, branchTimezone, cashShiftId, day, registerCode, searchQuery, serviceType]);

  const loadRequests = useCallback(async (cursor: string | null = null, append = false) => {
    if (!canAuthorizeReopen) return;
    setRequestsLoading(true); setRequestsError('');
    const params = new URLSearchParams({ limit: '20' });
    if (branchId) params.set('branch_id', branchId);
    if (cursor) params.set('cursor', cursor);
    try {
      const data = await fetchApi<ReopenRequestsResponse>(`/orders/reopen-requests?${params.toString()}`);
      setRequests((previous) => append ? [...previous, ...data.items] : data.items);
      setRequestsCursor(data.next_cursor);
    } catch (reason) {
      setRequestsError(reason instanceof ApiError ? reason.message : 'No fue posible cargar solicitudes.');
      if (!append) setRequests([]);
    } finally { setRequestsLoading(false); }
  }, [branchId, canAuthorizeReopen]);

  useEffect(() => {
    const timeout = window.setTimeout(() => { void loadAccounts(); }, 250);
    return () => window.clearTimeout(timeout);
  }, [loadAccounts]);
  useEffect(() => { void loadRequests(); }, [loadRequests]);

  const openOrder = async (orderId: string) => {
    setActiveOrderId(orderId); setSelected(null); setDetailLoading(true); setDetailError('');
    try { const detail = await fetchApi<OrderDetail>(`/orders/${orderId}`); setSelected(detail); setPaymentMethod(detail.payment_method_intent || 'cash'); }
    catch (reason) { setDetailError(reason instanceof ApiError ? reason.message : 'No fue posible abrir el pedido.'); }
    finally { setDetailLoading(false); }
  };
  const closeDetail = () => { setSelected(null); setActiveOrderId(null); setDetailError(''); setReopenError(''); };
  const refreshSelected = async () => { if (selected) await openOrder(selected.id); };
  const confirmPayment = async () => {
    if (!selected) return;
    if (!configuredRegisterId) { setDetailError('Configura la caja en Configuración > Turno y Caja antes de confirmar el pago.'); return; }
    setPaymentPending(true); setDetailError('');
    try { await fetchApi(`/orders/${selected.id}/payments`, { method: 'POST', body: JSON.stringify({ amount_cents: selected.total_cents, method: paymentMethod, register_id: configuredRegisterId }) }); await loadAccounts(); await refreshSelected(); }
    catch (reason) { setDetailError(reason instanceof ApiError ? reason.message : 'No fue posible confirmar el pago.'); }
    finally { setPaymentPending(false); }
  };
  const submitReopenRequest = async () => {
    if (!selected || !canRequestReopen || !selected.reopen_eligible || selected.active_reopen_request_status) return;
    const evidenceRefs = evidenceText.split('\n').map((value) => value.trim()).filter(Boolean);
    const signature = requestSignature(selected.id, reopenReason, evidenceRefs);
    if (reopenReason.trim().length < 10 || reopenReason.trim().length > 500 || evidenceRefs.length < 1 || evidenceRefs.length > 10 || evidenceRefs.some((value) => value.length > 500)) { setReopenError('El motivo requiere 10 a 500 caracteres y la evidencia 1 a 10 referencias no vacías de hasta 500 caracteres.'); return; }
    if (!requestKeyRef.current || requestKeyRef.current.signature !== signature) requestKeyRef.current = { signature, key: newIdempotencyKey() };
    setReopenPending(true); setReopenError('');
    try {
      await fetchApi(`/orders/${selected.id}/reopen-requests`, { method: 'POST', headers: { 'Idempotency-Key': requestKeyRef.current.key }, body: JSON.stringify({ reason: reopenReason.trim(), evidence_refs: evidenceRefs }) });
      requestKeyRef.current = null; setReopenReason(''); setEvidenceText(''); await Promise.all([loadAccounts(), refreshSelected(), loadRequests()]);
    } catch (reason) { setReopenError(reason instanceof ApiError ? reason.message : 'No fue posible enviar la solicitud. Conserva la misma clave para reintentar de forma segura.'); }
    finally { setReopenPending(false); }
  };
  const decideRequest = async (request: ReopenRequest, decision: 'approve' | 'reject') => {
    if (!canAuthorizeReopen) return;
    const decisionReason = decisionReasonById[request.id] || '';
    if (decisionReason.trim().length < 10 || decisionReason.trim().length > 500) { setRequestsError('El motivo de la decisión requiere 10 a 500 caracteres.'); return; }
    const mapKey = `${request.id}:${decision}`;
    const signature = decisionSignature(request.id, decision, decisionReason);
    const current = decisionKeysRef.current.get(mapKey);
    if (!current || current.signature !== signature) decisionKeysRef.current.set(mapKey, { signature, key: newIdempotencyKey() });
    setDecisionPendingId(request.id); setRequestsError('');
    try {
      await fetchApi(`/orders/reopen-requests/${request.id}/${decision}`, { method: 'POST', headers: { 'Idempotency-Key': decisionKeysRef.current.get(mapKey)?.key || '' }, body: JSON.stringify({ decision_reason: decisionReason.trim() }) });
      decisionKeysRef.current.delete(mapKey); await Promise.all([loadRequests(), loadAccounts(), refreshSelected()]);
    } catch (reason) { setRequestsError(reason instanceof ApiError ? reason.message : 'No fue posible registrar la decisión.'); }
    finally { setDecisionPendingId(null); }
  };

  const formatCurrency = (cents: number) => new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(cents / 100 || 0);
  const selectedStatus = selected ? getStatusConfig(selected.status) : null;
  const selectedSnapshotQuality = selected?.sales_operation_snapshots?.map((snapshot) => snapshot.quality_status || 'sin dato').join(', ') || 'Sin snapshot operativo';
  const today = useMemo(() => new Date().toLocaleDateString('en-CA', { timeZone: branchTimezone }), [branchTimezone]);

  return <div className="orders-history-page">
    <header className="orders-history-header"><div><h1>Pedidos</h1><p>Consulta, edita y confirma el pago de los pedidos de esta sucursal.</p></div>
      <div className="orders-history-toolbar"><label className="orders-history-search"><Search size={18} aria-hidden="true" /><input type="search" aria-label="Buscar pedido" placeholder="Buscar folio o cliente…" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} /></label><Button className="orders-history-refresh" variant="secondary" onClick={() => void loadAccounts()}><RefreshCcw size={18} /> Actualizar</Button></div>
    </header>
    <section className="orders-history-filters" aria-label="Filtros de cuentas">
      <label>Día<input type="date" value={day} max={today} onChange={(event) => setDay(event.target.value)} /></label>
      <label>Turno<input value={cashShiftId} onChange={(event) => setCashShiftId(event.target.value)} placeholder="ID de turno" /></label>
      <label>Caja<input value={registerCode} onChange={(event) => setRegisterCode(event.target.value)} placeholder="Código de caja" /></label>
      <label>Servicio<select value={serviceType} onChange={(event) => setServiceType(event.target.value)}><option value="">Todos</option><option value="dine-in">En sucursal</option><option value="takeout">Para llevar</option><option value="delivery">A domicilio</option></select></label>
      <Button variant="secondary" onClick={() => { setDay(''); setCashShiftId(''); setRegisterCode(''); setServiceType(''); setSearchQuery(''); }}>Limpiar filtros</Button>
    </section>
    {listError ? <p role="alert" className="orders-history-error">{listError}</p> : null}
    <div className="orders-history-layout"><Card className="orders-history-list">{loading ? <div className="orders-history-list-state"><RefreshCcw size={32} className="orders-history-spin" /><span>Cargando cuentas…</span></div> : <><div className="orders-history-table-scroll"><table><thead><tr><th>Folio</th><th>Cliente</th><th className="orders-history-type-cell">Tipo</th><th className="orders-history-date-cell">Fecha y hora</th><th>Estado</th><th>Total</th><th aria-label="Acciones" /></tr></thead><tbody>{orders.length === 0 ? <tr><td colSpan={7}><div className="orders-history-list-state"><Calendar size={42} /><span>No se encontraron cuentas.</span></div></td></tr> : orders.map((order) => { const status = getStatusConfig(order.status); const isSelected = selected?.id === order.id || activeOrderId === order.id; return <tr key={order.id} role="button" tabIndex={0} aria-selected={isSelected} className={isSelected ? 'is-selected' : ''} onClick={() => void openOrder(order.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void openOrder(order.id); } }}><td className="orders-history-folio">{order.folio}</td><td><span>{order.customer_label || 'Cliente General'}</span><small className="orders-history-compact-meta">{getTypeLabel(order.service_type)} · {new Date(order.created_at).toLocaleString('es-MX')}</small></td><td className="orders-history-type-cell">{getTypeLabel(order.service_type)}</td><td className="orders-history-date-cell"><Clock size={15} aria-hidden="true" />{new Date(order.created_at).toLocaleString('es-MX')}</td><td><span className="orders-history-status" style={{ background: status.bg, color: status.color, borderColor: status.border }}>{status.label}</span></td><td className="orders-history-total">{formatCurrency(order.total_cents)}</td><td><ChevronRight size={20} aria-hidden="true" /></td></tr>; })}</tbody></table></div>{nextCursor ? <div className="orders-history-pagination"><Button variant="secondary" onClick={() => void loadAccounts(nextCursor, true)}>Cargar más cuentas</Button></div> : null}</>}</Card>
      <aside className="orders-history-detail" aria-label="Detalle del pedido">{detailLoading ? <div className="orders-history-detail-state" role="status"><RefreshCcw size={30} className="orders-history-spin" /><strong>Abriendo pedido…</strong><span>Estamos preparando el detalle.</span></div> : !selected ? <div className="orders-history-detail-state"><span className="orders-history-empty-icon"><ReceiptText size={30} /></span><strong>Selecciona un pedido para revisar su detalle</strong><span>Podrás consultar productos, editarlo o confirmar el pago cuando corresponda.</span>{detailError ? <p role="alert" className="orders-history-inline-error">{detailError}</p> : null}</div> : <><div className="orders-history-detail-header"><div><span>Cuenta actual</span><h2>Detalle del pedido</h2></div><button type="button" onClick={closeDetail} aria-label="Cerrar detalle del pedido"><X size={20} /></button></div><div className="orders-history-detail-scroll"><section className="orders-history-order-meta"><div><span>Pedido</span><strong>{selected.folio}</strong></div><span className="orders-history-status" style={{ background: selectedStatus?.bg, color: selectedStatus?.color, borderColor: selectedStatus?.border }}>{selectedStatus?.label}</span></section><section className="orders-history-customer"><strong>{selected.customer_label || 'Cliente General'}</strong><span>{getTypeLabel(selected.service_type)}</span><small>{new Date(selected.created_at).toLocaleString('es-MX')}</small></section><section className="orders-history-snapshot"><strong>Calidad del snapshot operativo</strong><span>{selectedSnapshotQuality}</span></section><section className="orders-history-lines"><div className="orders-history-section-title"><span>Productos</span><small>{selected.lines.length} línea(s)</small></div>{selected.lines.map((line) => <div key={line.id} className="orders-history-line"><span className="orders-history-line-quantity">{line.quantity}</span><div><strong>{line.product_name}</strong><small>{line.quantity} × {formatCurrency(line.line_total_cents / line.quantity)}</small></div><strong>{formatCurrency(line.line_total_cents)}</strong></div>)}</section><section className="orders-history-summary"><div><span>Subtotal</span><span>{formatCurrency(selected.total_cents)}</span></div><div className="orders-history-summary-total"><strong>Total</strong><strong>{formatCurrency(selected.total_cents)}</strong></div>{selected.payment_status === 'CONFIRMED' ? <div className="orders-history-paid-method"><CreditCard size={17} />Pago confirmado</div> : null}</section>{selected.payment_status === 'PENDING' ? <section className="orders-history-payment"><div className="orders-history-section-title"><span>Confirmar pago recibido</span><small>{formatCurrency(selected.total_cents)}</small></div><div className="orders-history-payment-grid">{PAYMENT_METHODS.map((method) => <button key={method.value} type="button" aria-pressed={paymentMethod === method.value} className={paymentMethod === method.value ? 'is-selected' : ''} onClick={() => setPaymentMethod(method.value)}><CreditCard size={17} /><span><strong>{method.label}</strong><small>{method.hint}</small></span></button>)}</div></section> : null}{canRequestReopen && selected.reopen_eligible && !selected.active_reopen_request_status ? <section className="orders-history-reopen"><div className="orders-history-section-title"><span>Solicitar reapertura</span><small>Requiere autorización de Dueño</small></div><label>Motivo<textarea value={reopenReason} minLength={10} maxLength={500} onChange={(event) => setReopenReason(event.target.value)} /></label><label>Evidencia (una referencia por línea)<textarea value={evidenceText} maxLength={5000} onChange={(event) => setEvidenceText(event.target.value)} /></label><Button disabled={reopenPending} onClick={() => void submitReopenRequest()}>{reopenPending ? 'Enviando…' : 'Solicitar reapertura'}</Button>{reopenError ? <p role="alert" className="orders-history-inline-error">{reopenError}</p> : null}</section> : null}{selected.active_reopen_request_status ? <p className="orders-history-block-reason">Solicitud activa: {selected.active_reopen_request_status}.</p> : null}{detailError ? <p role="alert" className="orders-history-inline-error">{detailError}</p> : null}{!selected.editable && selected.edit_block_reason ? <p className="orders-history-block-reason">{selected.edit_block_reason}</p> : null}</div><div className="orders-history-detail-actions">{selected.editable ? <Button className="orders-history-edit-action" variant="secondary" onClick={() => navigate(`/pos/orders/${encodeURIComponent(selected.id)}/edit`)}><Pencil size={17} /> Editar pedido</Button> : null}{selected.payment_status === 'PENDING' ? (!configuredRegisterId ? <p role="alert" className="orders-history-inline-error">Configura la caja en Configuración &gt; Turno y Caja para habilitar el cobro.</p> : <Button className="orders-history-confirm-action" disabled={paymentPending || !configuredRegisterId} onClick={() => void confirmPayment()}><CreditCard size={17} />{paymentPending ? 'Confirmando…' : 'Confirmar pagado'}</Button>) : null}</div></>}</aside></div>
    {canAuthorizeReopen ? <Card className="orders-history-reopen-queue"><h2>Solicitudes de reapertura</h2><p>Solo Dueño puede decidir. La reapertura no se aplica desde esta pantalla.</p>{requestsError ? <p role="alert" className="orders-history-inline-error">{requestsError}</p> : null}{requestsLoading ? <p role="status">Cargando solicitudes…</p> : requests.length === 0 ? <p>No hay solicitudes pendientes o históricas en este alcance.</p> : requests.map((request) => <article key={request.id} className="orders-history-reopen-request"><strong>Pedido {request.order_id}</strong><span>{request.status}</span><p><b>Motivo:</b> {request.reason}</p><p><b>Evidencia:</b> {request.evidence_refs.join(', ')}</p>{request.decision_reason ? <p><b>Decisión:</b> {request.decision_reason}</p> : null}{request.status === 'REQUESTED' ? <><label>Motivo de decisión<textarea value={decisionReasonById[request.id] || ''} minLength={10} maxLength={500} onChange={(event) => setDecisionReasonById((current) => ({ ...current, [request.id]: event.target.value }))} /></label><div><Button disabled={decisionPendingId === request.id} onClick={() => void decideRequest(request, 'approve')}>Aprobar</Button><Button variant="secondary" disabled={decisionPendingId === request.id} onClick={() => void decideRequest(request, 'reject')}>Rechazar</Button></div></> : null}</article>)}{requestsCursor ? <Button variant="secondary" onClick={() => void loadRequests(requestsCursor, true)}>Cargar más solicitudes</Button> : null}</Card> : null}
  </div>;
};

export default History;
