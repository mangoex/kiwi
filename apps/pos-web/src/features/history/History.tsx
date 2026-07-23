import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Modal } from '@restaurantos/ui';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { Clock, RefreshCcw, Search, Calendar, ChevronRight, CreditCard, Pencil } from 'lucide-react';

type PaymentMethod = 'cash' | 'debit_card' | 'credit_card' | 'transfer';

interface Order {
  id: string;
  folio: string;
  status: string;
  display_status?: string;
  payment_status?: 'PENDING' | 'CONFIRMED';
  payment_method_intent?: PaymentMethod | null;
  total_cents: number;
  owner_name?: string;
  order_type?: string;
  created_at: string;
}

interface OrderDetail extends Order {
  version: number;
  editable: boolean;
  edit_block_reason?: string | null;
  lines: Array<{
    id: string;
    product_name: string;
    quantity: number;
    line_total_cents: number;
    selected_modifiers: Array<Record<string, unknown>>;
  }>;
  payments: Array<{ id: string; method: string; status: string; amount_cents: number }>;
  events: Array<{ id: string; event_type: string; created_at: string }>;
}

const PAYMENT_METHODS: Array<{ value: PaymentMethod; label: string }> = [
  { value: 'cash', label: 'Efectivo' },
  { value: 'debit_card', label: 'Tarjeta de débito' },
  { value: 'credit_card', label: 'Tarjeta de crédito' },
  { value: 'transfer', label: 'Transferencia' },
];

const History = () => {
  const navigate = useNavigate();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selected, setSelected] = useState<OrderDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash');
  const [paymentPending, setPaymentPending] = useState(false);
  const [error, setError] = useState('');

  const fetchOrders = async () => {
    setLoading(true);
    setError('');
    try {
      const branchId = localStorage.getItem('pos_branch_id');
      const url = branchId ? `/orders?branch_id=${encodeURIComponent(branchId)}` : '/orders';
      const data = await fetchApi<Order[]>(url, { headers: { 'Cache-Control': 'no-cache' } });
      setOrders(Array.isArray(data) ? data : []);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'No fue posible cargar los pedidos.');
      setOrders([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchOrders();
  }, []);

  const openOrder = async (orderId: string) => {
    setDetailLoading(true);
    setError('');
    try {
      const detail = await fetchApi<OrderDetail>(`/orders/${orderId}`);
      setSelected(detail);
      setPaymentMethod(detail.payment_method_intent || 'cash');
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'No fue posible abrir el pedido.');
    } finally {
      setDetailLoading(false);
    }
  };

  const confirmPayment = async () => {
    if (!selected) return;
    setPaymentPending(true);
    setError('');
    try {
      await fetchApi(`/orders/${selected.id}/payments`, {
        method: 'POST',
        body: JSON.stringify({ amount_cents: selected.total_cents, method: paymentMethod }),
      });
      await fetchOrders();
      const detail = await fetchApi<OrderDetail>(`/orders/${selected.id}`);
      setSelected(detail);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'No fue posible confirmar el pago.');
    } finally {
      setPaymentPending(false);
    }
  };

  const formatCurrency = (cents: number) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(cents / 100 || 0);

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'PENDING_PAYMENT':
        return { label: 'Pendiente de pago', bg: '#fff7ed', color: '#c2410c', border: '#fed7aa' };
      case 'COMPLETED':
      case 'CLOSED':
      case 'CERRADO':
        return { label: 'Completado', bg: '#ecfdf5', color: '#059669', border: '#a7f3d0' };
      case 'ACCEPTED':
      case 'PREPARING':
        return { label: 'Preparando', bg: '#eff6ff', color: '#2563eb', border: '#bfdbfe' };
      case 'READY':
        return { label: 'Listo', bg: '#fef3c7', color: '#d97706', border: '#fde68a' };
      case 'CANCELLED':
        return { label: 'Cancelado', bg: '#fef2f2', color: '#dc2626', border: '#fecaca' };
      default:
        return { label: status, bg: '#f1f5f9', color: '#475569', border: '#e2e8f0' };
    }
  };

  const getTypeLabel = (type?: string) => {
    if (type === 'dine-in') return 'En sucursal';
    if (type === 'takeout') return 'Para llevar';
    if (type === 'delivery') return 'A domicilio';
    return type || 'General';
  };

  const filteredOrders = useMemo(() => orders.filter((order) =>
    order.folio?.toLowerCase().includes(searchQuery.toLowerCase())
    || order.owner_name?.toLowerCase().includes(searchQuery.toLowerCase())), [orders, searchQuery]);

  return (
    <div style={{ padding: '32px 40px', maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: '2.25rem', fontWeight: 800, marginBottom: 8, color: '#0f172a' }}>Pedidos</h1>
          <p style={{ color: '#64748b', fontSize: '1.05rem' }}>Consulta, edita y confirma el pago de los pedidos de esta sucursal.</p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <label style={{ position: 'relative' }}>
            <Search size={18} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            <input type="search" aria-label="Buscar pedido" placeholder="Buscar folio o cliente…" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} style={{ padding: '10px 16px 10px 38px', borderRadius: 12, border: '1px solid #e2e8f0', width: 260 }} />
          </label>
          <Button variant="secondary" onClick={() => void fetchOrders()}><RefreshCcw size={18} /> Actualizar</Button>
        </div>
      </div>

      {error && <p role="alert" style={{ color: '#b91c1c' }}>{error}</p>}
      {detailLoading && <p role="status">Abriendo pedido…</p>}

      <Card style={{ padding: 0, borderRadius: 16, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#94a3b8' }}><RefreshCcw size={32} /> Cargando pedidos…</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead><tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              {['Folio', 'Cliente', 'Tipo', 'Fecha y hora', 'Estado', 'Total', ''].map((label) => <th key={label} style={{ padding: '16px 24px', color: '#64748b', fontSize: '.8rem', textTransform: 'uppercase' }}>{label}</th>)}
            </tr></thead>
            <tbody>
              {filteredOrders.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: 60, color: '#94a3b8' }}><Calendar size={42} /><div>No se encontraron pedidos.</div></td></tr>
              ) : filteredOrders.map((order) => {
                const status = getStatusConfig(order.display_status || order.status);
                return (
                  <tr key={order.id} role="button" tabIndex={0} onClick={() => void openOrder(order.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') void openOrder(order.id); }} style={{ borderBottom: '1px solid #f1f5f9', cursor: 'pointer' }}>
                    <td style={{ padding: '20px 24px', fontWeight: 700 }}>{order.folio}</td>
                    <td style={{ padding: '20px 24px' }}>{order.owner_name || 'General'}</td>
                    <td style={{ padding: '20px 24px' }}>{getTypeLabel(order.order_type)}</td>
                    <td style={{ padding: '20px 24px' }}><Clock size={15} /> {new Date(order.created_at).toLocaleString('es-MX')}</td>
                    <td style={{ padding: '20px 24px' }}><span style={{ padding: '6px 12px', borderRadius: 999, background: status.bg, color: status.color, border: `1px solid ${status.border}`, fontWeight: 700, fontSize: '.76rem' }}>{status.label}</span></td>
                    <td style={{ padding: '20px 24px', textAlign: 'right', fontWeight: 800 }}>{formatCurrency(order.total_cents)}</td>
                    <td style={{ padding: '20px 24px' }}><ChevronRight size={20} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      <Modal isOpen={Boolean(selected)} onClose={() => setSelected(null)} title={selected ? `Pedido ${selected.folio}` : 'Pedido'}>
        {selected && (
          <div style={{ display: 'grid', gap: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <div><strong>{selected.owner_name || 'Cliente general'}</strong><div style={{ color: '#64748b' }}>{getTypeLabel(selected.order_type)}</div></div>
              <strong>{formatCurrency(selected.total_cents)}</strong>
            </div>
            <section>
              <strong>Productos</strong>
              {selected.lines.map((line) => <div key={line.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}><span>{line.quantity} × {line.product_name}</span><span>{formatCurrency(line.line_total_cents)}</span></div>)}
            </section>
            {selected.payment_status === 'PENDING' && (
              <section style={{ padding: 14, borderRadius: 12, background: '#fff7ed', border: '1px solid #fed7aa' }}>
                <strong style={{ display: 'block', marginBottom: 8 }}>Confirmar pago recibido</strong>
                <select value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value as PaymentMethod)} style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #fdba74', marginBottom: 10 }}>
                  {PAYMENT_METHODS.map((method) => <option key={method.value} value={method.value}>{method.label}</option>)}
                </select>
                <Button disabled={paymentPending} onClick={() => void confirmPayment()}><CreditCard size={17} /> Confirmar pagado</Button>
              </section>
            )}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              {selected.editable ? (
                <Button variant="secondary" onClick={() => navigate(`/pos?edit_order_id=${encodeURIComponent(selected.id)}`)}><Pencil size={17} /> Editar pedido</Button>
              ) : selected.edit_block_reason ? (
                <span style={{ color: '#64748b', fontSize: 13 }}>{selected.edit_block_reason}</span>
              ) : null}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default History;
