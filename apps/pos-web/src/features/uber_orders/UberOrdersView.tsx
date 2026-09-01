import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Badge, Button } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import {
  Bike,
  Clock,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  ShoppingBag,
  User,
  Phone,
  FileText,
  ChefHat,
  PackageCheck,
  Ban,
  Share2,
} from 'lucide-react';
import { usePosSession } from '../../session';

export type MarketplaceProvider = 'UBER_EATS' | 'DIDI_FOOD' | 'RAPPI';

interface ChannelOrderLine {
  id: string;
  product_name: string;
  quantity: number;
  unit_price_cents: number;
  line_total_cents: number;
  line_notes?: string;
  selected_modifiers?: any[];
}

interface ChannelOrder {
  id: string;
  folio: string;
  channel: string;
  status: string;
  total_cents: number;
  currency: string;
  created_at: string;
  accepted_at?: string;
  customer_snapshot?: { name: string; phone: string };
  delivery_address_snapshot?: { notes: string; channel: string };
  external_order_id: string;
  display_code: string;
  customer_name?: string;
  driver_name?: string;
  driver_phone?: string;
  external_status: string;
  lines: ChannelOrderLine[];
}

interface ChannelOrdersViewProps {
  provider?: MarketplaceProvider;
}

const PROVIDER_CONFIG: Record<
  MarketplaceProvider,
  {
    name: string;
    shortName: string;
    defaultCustomer: string;
    apiPath: string;
    brandColor: string;
    accentColor: string;
    lightBg: string;
    borderActive: string;
    emptyText: string;
    totalLabel: string;
    iconBg: string;
    icon: React.ReactNode;
  }
> = {
  UBER_EATS: {
    name: 'Uber Eats',
    shortName: 'Uber',
    defaultCustomer: 'Cliente Uber',
    apiPath: 'uber-eats',
    brandColor: '#064e3b',
    accentColor: '#10b981',
    lightBg: '#ecfdf5',
    borderActive: '#10b981',
    emptyText: 'No hay pedidos de Uber Eats en este estado',
    totalLabel: 'Total Pagado en Uber Eats:',
    iconBg: '#064e3b',
    icon: <Share2 size={24} style={{ color: '#10b981' }} />,
  },
  DIDI_FOOD: {
    name: 'DiDi Food',
    shortName: 'DiDi',
    defaultCustomer: 'Cliente DiDi',
    apiPath: 'didi-food',
    brandColor: '#7c2d12',
    accentColor: '#f97316',
    lightBg: '#fff7ed',
    borderActive: '#f97316',
    emptyText: 'No hay pedidos de DiDi Food en este estado',
    totalLabel: 'Total Pagado en DiDi Food:',
    iconBg: '#7c2d12',
    icon: <Bike size={24} style={{ color: '#f97316' }} />,
  },
  RAPPI: {
    name: 'Rappi',
    shortName: 'Rappi',
    defaultCustomer: 'Cliente Rappi',
    apiPath: 'rappi',
    brandColor: '#831843',
    accentColor: '#ec4899',
    lightBg: '#fdf2f8',
    borderActive: '#ec4899',
    emptyText: 'No hay pedidos de Rappi en este estado',
    totalLabel: 'Total Pagado en Rappi:',
    iconBg: '#831843',
    icon: <ShoppingBag size={24} style={{ color: '#ec4899' }} />,
  },
};

export default function ChannelOrdersView({ provider = 'UBER_EATS' }: ChannelOrdersViewProps) {
  const config = PROVIDER_CONFIG[provider];
  const queryClient = useQueryClient();
  const { session } = usePosSession();
  const branchId = session?.active_branch?.id || localStorage.getItem('canonical_branch_id') || '';
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  // Fetch orders for this branch
  const { data: orders = [], isLoading, refetch } = useQuery<ChannelOrder[]>({
    queryKey: ['pos', config.apiPath, 'orders', branchId],
    queryFn: () => fetchApi(`/pos/${config.apiPath}/orders?branch_id=` + branchId),
    refetchInterval: 5000,
  });

  // Update order status mutation
  const updateStatusMutation = useMutation({
    mutationFn: ({ orderId, status }: { orderId: string; status: string }) =>
      fetchApi(`/pos/${config.apiPath}/orders/${orderId}/status`, {
        method: 'POST',
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pos', config.apiPath, 'orders', branchId] });
    },
  });

  const selectedOrder = orders.find((o) => o.id === selectedOrderId) || orders[0];

  const filteredOrders = orders.filter((o) => {
    if (filterStatus === 'ALL') return true;
    if (filterStatus === 'ACTIVE') return ['PENDING', 'ACCEPTED', 'PREPARING', 'READY'].includes(o.status);
    if (filterStatus === 'ACCEPTED') return ['ACCEPTED', 'PREPARING'].includes(o.status);
    return o.status === filterStatus;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'PENDING':
        return <Badge variant="warning">Por Aceptar</Badge>;
      case 'ACCEPTED':
        return <Badge variant="info">En Cocina</Badge>;
      case 'PREPARING':
        return <Badge variant="info">Preparando</Badge>;
      case 'READY':
        return <Badge variant="success">Listo para Repartidor</Badge>;
      case 'COMPLETED':
        return <Badge variant="default">Entregado</Badge>;
      case 'CANCELLED':
        return <Badge variant="danger">Cancelado</Badge>;
      default:
        return <Badge variant="default">{status}</Badge>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#f8fafc', padding: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: config.iconBg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {config.icon}
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 8 }}>
              Pedidos de {config.name}
              <span
                style={{
                  fontSize: '0.75rem',
                  padding: '2px 8px',
                  background: config.accentColor,
                  color: '#fff',
                  borderRadius: 12,
                  fontWeight: 700,
                }}
              >
                LIVE
              </span>
            </h1>
            <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
              Monitor en tiempo real sincronizado con cocina y repartidores de {config.shortName}.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="secondary" onClick={() => refetch()}>
            <RefreshCw size={16} />
            Actualizar
          </Button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {[
          { key: 'ALL', label: 'Todos (' + orders.length + ')' },
          { key: 'PENDING', label: 'Por Aceptar (' + orders.filter((o) => o.status === 'PENDING').length + ')' },
          { key: 'ACCEPTED', label: 'En Cocina (' + orders.filter((o) => ['ACCEPTED', 'PREPARING'].includes(o.status)).length + ')' },
          { key: 'READY', label: 'Listos para Retiro (' + orders.filter((o) => o.status === 'READY').length + ')' },
          { key: 'COMPLETED', label: 'Entregados (' + orders.filter((o) => o.status === 'COMPLETED').length + ')' },
        ].map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilterStatus(f.key)}
            style={{
              padding: '8px 16px',
              borderRadius: 20,
              border: filterStatus === f.key ? `2px solid ${config.borderActive}` : '1px solid #cbd5e1',
              background: filterStatus === f.key ? config.lightBg : '#fff',
              color: filterStatus === f.key ? config.brandColor : '#64748b',
              fontWeight: 600,
              fontSize: '0.875rem',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Main Split Layout: Orders List & Detail */}
      <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: 20, flex: 1, minHeight: 0 }}>
        {/* Left Column: Orders Cards List */}
        <div
          style={{
            background: '#fff',
            borderRadius: 14,
            border: '1px solid #e2e8f0',
            overflowY: 'auto',
            padding: 12,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          {filteredOrders.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: '#94a3b8' }}>
              <ShoppingBag size={48} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
              <p style={{ margin: 0, fontWeight: 600, fontSize: '0.95rem' }}>{config.emptyText}</p>
            </div>
          ) : (
            filteredOrders.map((order) => {
              const isSelected = selectedOrder?.id === order.id;
              return (
                <div
                  key={order.id}
                  onClick={() => setSelectedOrderId(order.id)}
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    border: isSelected ? `2px solid ${config.borderActive}` : '1px solid #e2e8f0',
                    background: isSelected ? config.lightBg : '#fff',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span
                        style={{
                          background: config.brandColor,
                          color: '#fff',
                          fontWeight: 800,
                          fontSize: '0.95rem',
                          padding: '4px 8px',
                          borderRadius: 6,
                          fontFamily: 'monospace',
                        }}
                      >
                        {order.display_code}
                      </span>
                      <strong style={{ fontSize: '0.95rem', color: '#0f172a' }}>
                        {order.customer_name || order.customer_snapshot?.name || config.defaultCustomer}
                      </strong>
                    </div>
                    {getStatusBadge(order.status)}
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8125rem', color: '#64748b' }}>
                    <span>{order.lines.length} {order.lines.length === 1 ? 'producto' : 'productos'}</span>
                    <strong style={{ color: '#0f172a', fontSize: '0.95rem' }}>
                      ${(order.total_cents / 100).toFixed(2)} {order.currency}
                    </strong>
                  </div>

                  <div style={{ marginTop: 8, fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Clock size={12} />
                    {new Date(order.created_at).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Column: Selected Order Detail */}
        {selectedOrder ? (
          <div
            style={{
              background: '#fff',
              borderRadius: 14,
              border: '1px solid #e2e8f0',
              padding: 24,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              overflowY: 'auto',
            }}
          >
            <div>
              {/* Order Header Detail */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: 16, marginBottom: 20 }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
                    <span
                      style={{
                        background: config.brandColor,
                        color: '#fff',
                        fontWeight: 900,
                        fontSize: '1.4rem',
                        padding: '6px 14px',
                        borderRadius: 8,
                        fontFamily: 'monospace',
                      }}
                    >
                      {selectedOrder.display_code}
                    </span>
                    <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800 }}>
                      {selectedOrder.customer_name || selectedOrder.customer_snapshot?.name || 'Cliente'}
                    </h2>
                  </div>
                  <p style={{ margin: 0, fontSize: '0.8125rem', color: '#64748b' }}>
                    Folio Sistema: <code>{selectedOrder.folio}</code> · ID {config.shortName}: <code>{selectedOrder.external_order_id}</code>
                  </p>
                </div>
                <div>{getStatusBadge(selectedOrder.status)}</div>
              </div>

              {/* Delivery / Eater Info */}
              <div style={{ background: '#f8fafc', borderRadius: 10, padding: 14, marginBottom: 20, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                <div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: 2 }}>
                    Cliente
                  </div>
                  <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#0f172a' }}>
                    {selectedOrder.customer_name || selectedOrder.customer_snapshot?.name}
                  </div>
                </div>
                {selectedOrder.delivery_address_snapshot?.notes && (
                  <div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: 2 }}>
                      Notas de Entrega
                    </div>
                    <div style={{ fontSize: '0.875rem', color: '#b45309', fontWeight: 600 }}>
                      {selectedOrder.delivery_address_snapshot.notes}
                    </div>
                  </div>
                )}
              </div>

              {/* Order Items */}
              <div style={{ marginBottom: 24 }}>
                <h3 style={{ margin: '0 0 12px', fontSize: '1rem', fontWeight: 700 }}>
                  Contenido de la Comanda
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {selectedOrder.lines.map((line, idx) => (
                    <div
                      key={line.id || idx}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        padding: '12px 14px',
                        background: '#f8fafc',
                        borderRadius: 8,
                        border: '1px solid #f1f5f9',
                      }}
                    >
                      <div style={{ display: 'flex', gap: 12 }}>
                        <span
                          style={{
                            background: '#e2e8f0',
                            fontWeight: 800,
                            padding: '2px 8px',
                            borderRadius: 6,
                            fontSize: '0.9rem',
                            height: 'fit-content',
                          }}
                        >
                          {line.quantity}x
                        </span>
                        <div>
                          <strong style={{ fontSize: '0.95rem', color: '#0f172a' }}>
                            {line.product_name}
                          </strong>
                          {line.line_notes && (
                            <p style={{ margin: '4px 0 0', fontSize: '0.8125rem', color: '#dc2626', fontWeight: 600 }}>
                              • {line.line_notes}
                            </p>
                          )}
                        </div>
                      </div>
                      <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                        ${(line.line_total_cents / 100).toFixed(2)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Total Row */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 0', borderTop: '2px dashed #e2e8f0' }}>
                <strong style={{ fontSize: '1.1rem' }}>{config.totalLabel}</strong>
                <strong style={{ fontSize: '1.3rem', color: config.brandColor }}>
                  ${(selectedOrder.total_cents / 100).toFixed(2)} {selectedOrder.currency}
                </strong>
              </div>
            </div>

            {/* Action Buttons Toolbar */}
            <div style={{ display: 'flex', gap: 12, paddingTop: 16, borderTop: '1px solid #e2e8f0', justifyContent: 'flex-end' }}>
              {selectedOrder.status === 'PENDING' && (
                <Button
                  variant="primary"
                  onClick={() => updateStatusMutation.mutate({ orderId: selectedOrder.id, status: 'ACCEPTED' })}
                  disabled={updateStatusMutation.isPending}
                >
                  <ChefHat size={16} />
                  Aceptar y Mandar a Cocina
                </Button>
              )}

              {['ACCEPTED', 'PREPARING'].includes(selectedOrder.status) && (
                <Button
                  variant="primary"
                  onClick={() => updateStatusMutation.mutate({ orderId: selectedOrder.id, status: 'READY' })}
                  disabled={updateStatusMutation.isPending}
                >
                  <PackageCheck size={16} />
                  Marcar Listo para Repartidor
                </Button>
              )}

              {selectedOrder.status === 'READY' && (
                <Button
                  variant="primary"
                  onClick={() => updateStatusMutation.mutate({ orderId: selectedOrder.id, status: 'COMPLETED' })}
                  disabled={updateStatusMutation.isPending}
                >
                  <CheckCircle size={16} />
                  Confirmar Entrega al Repartidor
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', color: '#94a3b8' }}>
            Selecciona un pedido de la lista para ver su detalle
          </div>
        )}
      </div>
    </div>
  );
}

export function UberOrdersView() {
  return <ChannelOrdersView provider="UBER_EATS" />;
}

export function DidiOrdersView() {
  return <ChannelOrdersView provider="DIDI_FOOD" />;
}

export function RappiOrdersView() {
  return <ChannelOrdersView provider="RAPPI" />;
}
