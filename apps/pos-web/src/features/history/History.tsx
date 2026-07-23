import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card } from '@restaurantos/ui';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import {
  Calendar,
  ChevronRight,
  Clock,
  CreditCard,
  Pencil,
  ReceiptText,
  RefreshCcw,
  Search,
  X,
} from 'lucide-react';

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

const PAYMENT_METHODS: Array<{ value: PaymentMethod; label: string; hint: string }> = [
  { value: 'cash', label: 'Efectivo', hint: 'Pago en caja' },
  { value: 'debit_card', label: 'Débito', hint: 'Tarjeta de débito' },
  { value: 'credit_card', label: 'Crédito', hint: 'Tarjeta de crédito' },
  { value: 'transfer', label: 'Transferencia', hint: 'Transferencia bancaria' },
];

const History = () => {
  const navigate = useNavigate();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selected, setSelected] = useState<OrderDetail | null>(null);
  const [activeOrderId, setActiveOrderId] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash');
  const [paymentPending, setPaymentPending] = useState(false);
  const [listError, setListError] = useState('');
  const [detailError, setDetailError] = useState('');

  const fetchOrders = async () => {
    setLoading(true);
    setListError('');
    try {
      const branchId = localStorage.getItem('pos_branch_id');
      const url = branchId ? `/orders?branch_id=${encodeURIComponent(branchId)}` : '/orders';
      const data = await fetchApi<Order[]>(url, { headers: { 'Cache-Control': 'no-cache' } });
      setOrders(Array.isArray(data) ? data : []);
    } catch (reason) {
      setListError(reason instanceof ApiError ? reason.message : 'No fue posible cargar los pedidos.');
      setOrders([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchOrders();
  }, []);

  const openOrder = async (orderId: string) => {
    setActiveOrderId(orderId);
    setSelected(null);
    setDetailLoading(true);
    setDetailError('');
    try {
      const detail = await fetchApi<OrderDetail>(`/orders/${orderId}`);
      setSelected(detail);
      setPaymentMethod(detail.payment_method_intent || 'cash');
    } catch (reason) {
      setDetailError(reason instanceof ApiError ? reason.message : 'No fue posible abrir el pedido.');
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setSelected(null);
    setActiveOrderId(null);
    setDetailError('');
  };

  const confirmPayment = async () => {
    if (!selected) return;
    setPaymentPending(true);
    setDetailError('');
    try {
      await fetchApi(`/orders/${selected.id}/payments`, {
        method: 'POST',
        body: JSON.stringify({ amount_cents: selected.total_cents, method: paymentMethod }),
      });
      await fetchOrders();
      const detail = await fetchApi<OrderDetail>(`/orders/${selected.id}`);
      setSelected(detail);
    } catch (reason) {
      setDetailError(reason instanceof ApiError ? reason.message : 'No fue posible confirmar el pago.');
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

  const getPaymentLabel = (method?: string | null) =>
    PAYMENT_METHODS.find((item) => item.value === method)?.label || method || 'Sin registrar';

  const filteredOrders = useMemo(
    () =>
      orders.filter(
        (order) =>
          order.folio?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          order.owner_name?.toLowerCase().includes(searchQuery.toLowerCase()),
      ),
    [orders, searchQuery],
  );

  const selectedStatus = selected
    ? getStatusConfig(selected.display_status || selected.status)
    : null;

  return (
    <div className="orders-history-page">
      <header className="orders-history-header">
        <div>
          <h1>Pedidos</h1>
          <p>Consulta, edita y confirma el pago de los pedidos de esta sucursal.</p>
        </div>
        <div className="orders-history-toolbar">
          <label className="orders-history-search">
            <Search size={18} aria-hidden="true" />
            <input
              type="search"
              aria-label="Buscar pedido"
              placeholder="Buscar folio o cliente…"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </label>
          <Button className="orders-history-refresh" variant="secondary" onClick={() => void fetchOrders()}>
            <RefreshCcw size={18} /> Actualizar
          </Button>
        </div>
      </header>

      {listError && <p role="alert" className="orders-history-error">{listError}</p>}

      <div className="orders-history-layout">
        <Card className="orders-history-list">
          {loading ? (
            <div className="orders-history-list-state">
              <RefreshCcw size={32} className="orders-history-spin" />
              <span>Cargando pedidos…</span>
            </div>
          ) : (
            <div className="orders-history-table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Folio</th>
                    <th>Cliente</th>
                    <th className="orders-history-type-cell">Tipo</th>
                    <th className="orders-history-date-cell">Fecha y hora</th>
                    <th>Estado</th>
                    <th>Total</th>
                    <th aria-label="Acciones" />
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.length === 0 ? (
                    <tr>
                      <td colSpan={7}>
                        <div className="orders-history-list-state">
                          <Calendar size={42} />
                          <span>No se encontraron pedidos.</span>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredOrders.map((order) => {
                      const status = getStatusConfig(order.display_status || order.status);
                      const isSelected = selected?.id === order.id || activeOrderId === order.id;
                      return (
                        <tr
                          key={order.id}
                          role="button"
                          tabIndex={0}
                          aria-selected={isSelected}
                          className={isSelected ? 'is-selected' : ''}
                          onClick={() => void openOrder(order.id)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.preventDefault();
                              void openOrder(order.id);
                            }
                          }}
                        >
                          <td className="orders-history-folio">{order.folio}</td>
                          <td>
                            <span>{order.owner_name || 'Cliente General'}</span>
                            <small className="orders-history-compact-meta">
                              {getTypeLabel(order.order_type)} · {new Date(order.created_at).toLocaleString('es-MX')}
                            </small>
                          </td>
                          <td className="orders-history-type-cell">{getTypeLabel(order.order_type)}</td>
                          <td className="orders-history-date-cell">
                            <Clock size={15} aria-hidden="true" />
                            {new Date(order.created_at).toLocaleString('es-MX')}
                          </td>
                          <td>
                            <span
                              className="orders-history-status"
                              style={{
                                background: status.bg,
                                color: status.color,
                                borderColor: status.border,
                              }}
                            >
                              {status.label}
                            </span>
                          </td>
                          <td className="orders-history-total">{formatCurrency(order.total_cents)}</td>
                          <td><ChevronRight size={20} aria-hidden="true" /></td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <aside className="orders-history-detail" aria-label="Detalle del pedido">
          {detailLoading ? (
            <div className="orders-history-detail-state" role="status">
              <RefreshCcw size={30} className="orders-history-spin" />
              <strong>Abriendo pedido…</strong>
              <span>Estamos preparando el detalle.</span>
            </div>
          ) : !selected ? (
            <div className="orders-history-detail-state">
              <span className="orders-history-empty-icon"><ReceiptText size={30} /></span>
              <strong>Selecciona un pedido para revisar su detalle</strong>
              <span>Podrás consultar productos, editarlo o confirmar el pago cuando corresponda.</span>
              {detailError && <p role="alert" className="orders-history-inline-error">{detailError}</p>}
            </div>
          ) : (
            <>
              <div className="orders-history-detail-header">
                <div>
                  <span>Cuenta actual</span>
                  <h2>Detalle del pedido</h2>
                </div>
                <button type="button" onClick={closeDetail} aria-label="Cerrar detalle del pedido">
                  <X size={20} />
                </button>
              </div>

              <div className="orders-history-detail-scroll">
                <section className="orders-history-order-meta">
                  <div>
                    <span>Pedido</span>
                    <strong>{selected.folio}</strong>
                  </div>
                  <span
                    className="orders-history-status"
                    style={{
                      background: selectedStatus?.bg,
                      color: selectedStatus?.color,
                      borderColor: selectedStatus?.border,
                    }}
                  >
                    {selectedStatus?.label}
                  </span>
                </section>

                <section className="orders-history-customer">
                  <strong>{selected.owner_name || 'Cliente General'}</strong>
                  <span>{getTypeLabel(selected.order_type)}</span>
                  <small>{new Date(selected.created_at).toLocaleString('es-MX')}</small>
                </section>

                <section className="orders-history-lines">
                  <div className="orders-history-section-title">
                    <span>Productos</span>
                    <small>{selected.lines.length} línea(s)</small>
                  </div>
                  {selected.lines.map((line) => (
                    <div key={line.id} className="orders-history-line">
                      <span className="orders-history-line-quantity">{line.quantity}</span>
                      <div>
                        <strong>{line.product_name}</strong>
                        <small>{line.quantity} × {formatCurrency(line.line_total_cents / line.quantity)}</small>
                      </div>
                      <strong>{formatCurrency(line.line_total_cents)}</strong>
                    </div>
                  ))}
                </section>

                <section className="orders-history-summary">
                  <div><span>Subtotal</span><span>{formatCurrency(selected.total_cents)}</span></div>
                  <div><span>IVA incluido</span><span>$0.00</span></div>
                  <div className="orders-history-summary-total">
                    <strong>Total</strong>
                    <strong>{formatCurrency(selected.total_cents)}</strong>
                  </div>
                  {selected.payment_status === 'CONFIRMED' && (
                    <div className="orders-history-paid-method">
                      <CreditCard size={17} />
                      Pago confirmado · {getPaymentLabel(selected.payments.find((payment) => payment.status === 'CONFIRMED')?.method)}
                    </div>
                  )}
                </section>

                {selected.payment_status === 'PENDING' && (
                  <section className="orders-history-payment">
                    <div className="orders-history-section-title">
                      <span>Confirmar pago recibido</span>
                      <small>{formatCurrency(selected.total_cents)}</small>
                    </div>
                    <div className="orders-history-payment-grid">
                      {PAYMENT_METHODS.map((method) => (
                        <button
                          key={method.value}
                          type="button"
                          aria-pressed={paymentMethod === method.value}
                          className={paymentMethod === method.value ? 'is-selected' : ''}
                          onClick={() => setPaymentMethod(method.value)}
                        >
                          <CreditCard size={17} />
                          <span><strong>{method.label}</strong><small>{method.hint}</small></span>
                        </button>
                      ))}
                    </div>
                  </section>
                )}

                {detailError && <p role="alert" className="orders-history-inline-error">{detailError}</p>}
                {!selected.editable && selected.edit_block_reason && (
                  <p className="orders-history-block-reason">{selected.edit_block_reason}</p>
                )}
              </div>

              <div className="orders-history-detail-actions">
                {selected.editable && (
                  <Button
                    className="orders-history-edit-action"
                    variant="secondary"
                    onClick={() => navigate(`/pos?edit_order_id=${encodeURIComponent(selected.id)}`)}
                  >
                    <Pencil size={17} /> Editar pedido
                  </Button>
                )}
                {selected.payment_status === 'PENDING' && (
                  <Button
                    className="orders-history-confirm-action"
                    disabled={paymentPending}
                    onClick={() => void confirmPayment()}
                  >
                    <CreditCard size={17} />
                    {paymentPending ? 'Confirmando…' : 'Confirmar pagado'}
                  </Button>
                )}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
};

export default History;
