import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  BarChart3,
  TrendingUp,
  ShoppingBag,
  Receipt,
  Package,
  RefreshCw,
  Store,
  Calendar,
  ArrowRight,
  Clock,
  Layers,
  UtensilsCrossed,
} from 'lucide-react';
import { Button, Badge } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { useAdminSession } from '../../lib/adminSession';
import './AnalyticsDashboard.css';

interface Branch {
  id: string;
  name: string;
}

interface OverviewResponse {
  total_revenue_cents: number;
  total_orders: number;
  average_ticket_cents: number;
  total_products: number;
  order_types: {
    mostrador: number;
    para_llevar: number;
    domicilio: number;
  };
  period_from_utc: string;
  period_to_utc: string;
  recent_transactions: {
    id: string;
    amount_cents: number;
    status: string;
    created_at: string;
    folio: string;
  }[];
  activity_chart: {
    day: string;
    completed: number;
    pending: number;
  }[];
  popular_categories: {
    id: string;
    name: string;
    quantity: number;
    known_net_cents: number;
    share_bps: number;
  }[];
}

export default function AnalyticsDashboard() {
  const navigate = useNavigate();
  const { session } = useAdminSession();

  const today = new Date();
  const currentMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;

  const [selectedMonth, setSelectedMonth] = useState(currentMonth);
  const [selectedBranchId, setSelectedBranchId] = useState('');

  const { data: branches = [] } = useQuery<Branch[]>({
    queryKey: ['branches'],
    queryFn: () => fetchApi('/branches'),
  });

  const {
    data,
    isLoading,
    isRefetching,
    error,
    refetch,
  } = useQuery<OverviewResponse>({
    queryKey: ['dashboard-overview-analytics', session?.organization_id, selectedMonth, selectedBranchId],
    queryFn: async () => {
      const params = new URLSearchParams({ month: selectedMonth });
      if (selectedBranchId) {
        params.set('branch_id', selectedBranchId);
      }
      return fetchApi<OverviewResponse>(`/dashboard/overview?${params.toString()}`);
    },
  });

  const formatMoney = (cents: number) => {
    return (cents / 100).toLocaleString('es-MX', {
      style: 'currency',
      currency: 'MXN',
      minimumFractionDigits: 2,
    });
  };

  const totalChannels =
    (data?.order_types.mostrador || 0) +
    (data?.order_types.para_llevar || 0) +
    (data?.order_types.domicilio || 0) || 1;

  const maxActivity = Math.max(
    ...(data?.activity_chart.map((a) => a.completed) || [1]),
    1
  );

  return (
    <div className="analytics-dashboard">
      {/* Header and Controls */}
      <header className="analytics-header">
        <div>
          <h1>Métricas y Rendimiento de Ventas</h1>
          <p>Consolidado comercial en vivo, desglose por canal e indicadores de la cadena.</p>
        </div>

        <div className="analytics-controls">
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#475569' }}>
            <Calendar size={16} />
            Mes:
            <input
              type="month"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              aria-label="Seleccionar mes de consulta"
            />
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: '#475569' }}>
            <Store size={16} />
            <select
              value={selectedBranchId}
              onChange={(e) => setSelectedBranchId(e.target.value)}
              aria-label="Filtrar por sucursal"
            >
              <option value="">🏢 Todas las sucursales</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>

          <Button
            variant="ghost"
            onClick={() => void refetch()}
            disabled={isLoading || isRefetching}
            title="Refrescar métricas"
          >
            <RefreshCw size={16} className={isRefetching ? 'sales-monitor-spin' : ''} />
          </Button>

          <Button variant="secondary" onClick={() => navigate('/reports')}>
            Ver Cierres y Cortes <ArrowRight size={15} />
          </Button>
        </div>
      </header>

      {/* Loading state */}
      {isLoading && (
        <div style={{ textAlign: 'center', padding: '48px 0', color: '#64748b' }}>
          <RefreshCw size={32} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 12px' }} />
          <p>Cargando métricas de ventas y rendimiento…</p>
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: 18, borderRadius: 12, color: '#991b1b', marginBottom: 20 }}>
          <strong>No fue posible cargar las métricas:</strong>
          <p style={{ margin: '4px 0 10px', fontSize: '0.9rem' }}>{error instanceof Error ? error.message : 'Error al consultar el servidor'}</p>
          <Button variant="secondary" onClick={() => void refetch()}>Reintentar</Button>
        </div>
      )}

      {/* Content when loaded */}
      {data && !isLoading && (
        <>
          {/* Main KPI Cards */}
          <section className="analytics-kpis" aria-label="KPIs principales">
            <div className="analytics-kpi-card">
              <div className="analytics-kpi-card-header">
                <span>Venta Neta Total</span>
                <div className="analytics-kpi-icon" style={{ background: '#dcfce7', color: '#15803d' }}>
                  <TrendingUp size={20} />
                </div>
              </div>
              <div className="analytics-kpi-value">
                {formatMoney(data.total_revenue_cents)}
              </div>
              <div className="analytics-kpi-footer">
                <span>Ingresos netos confirmados en el periodo</span>
              </div>
            </div>

            <div className="analytics-kpi-card">
              <div className="analytics-kpi-card-header">
                <span>Total de Pedidos</span>
                <div className="analytics-kpi-icon" style={{ background: '#eff6ff', color: '#2563eb' }}>
                  <ShoppingBag size={20} />
                </div>
              </div>
              <div className="analytics-kpi-value">
                {data.total_orders.toLocaleString('es-MX')}
              </div>
              <div className="analytics-kpi-footer">
                <span>Órdenes liquidadas y entregadas</span>
              </div>
            </div>

            <div className="analytics-kpi-card">
              <div className="analytics-kpi-card-header">
                <span>Ticket Promedio</span>
                <div className="analytics-kpi-icon" style={{ background: '#fef3c7', color: '#b45309' }}>
                  <Receipt size={20} />
                </div>
              </div>
              <div className="analytics-kpi-value">
                {formatMoney(data.average_ticket_cents)}
              </div>
              <div className="analytics-kpi-footer">
                <span>Promedio de consumo por orden</span>
              </div>
            </div>

            <div className="analytics-kpi-card">
              <div className="analytics-kpi-card-header">
                <span>Productos Activos</span>
                <div className="analytics-kpi-icon" style={{ background: '#f3e8ff', color: '#7e22ce' }}>
                  <Package size={20} />
                </div>
              </div>
              <div className="analytics-kpi-value">
                {data.total_products}
              </div>
              <div className="analytics-kpi-footer">
                <span>Platillos activos en catálogo</span>
              </div>
            </div>
          </section>

          {/* Two Columns: Channels and Top Categories */}
          <div className="analytics-grid-two">
            {/* Sales by Channel / Service type */}
            <section className="analytics-panel">
              <h3>
                <Layers size={18} color="#2563eb" />
                Ventas por Canal de Servicio
              </h3>
              <div className="analytics-channel-list">
                <div className="analytics-channel-item">
                  <div className="analytics-channel-info">
                    <span style={{ color: '#0f172a' }}>Comedor / Mostrador</span>
                    <span style={{ color: '#047857' }}>
                      {data.order_types.mostrador} pedidos ({Math.round(((data.order_types.mostrador || 0) / totalChannels) * 100)}%)
                    </span>
                  </div>
                  <div className="analytics-channel-bar-bg">
                    <div
                      className="analytics-channel-bar-fill"
                      style={{
                        width: `${Math.round(((data.order_types.mostrador || 0) / totalChannels) * 100)}%`,
                        background: '#10b981',
                      }}
                    />
                  </div>
                </div>

                <div className="analytics-channel-item">
                  <div className="analytics-channel-info">
                    <span style={{ color: '#0f172a' }}>Para Llevar (Pick-up)</span>
                    <span style={{ color: '#0369a1' }}>
                      {data.order_types.para_llevar} pedidos ({Math.round(((data.order_types.para_llevar || 0) / totalChannels) * 100)}%)
                    </span>
                  </div>
                  <div className="analytics-channel-bar-bg">
                    <div
                      className="analytics-channel-bar-fill"
                      style={{
                        width: `${Math.round(((data.order_types.para_llevar || 0) / totalChannels) * 100)}%`,
                        background: '#0ea5e9',
                      }}
                    />
                  </div>
                </div>

                <div className="analytics-channel-item">
                  <div className="analytics-channel-info">
                    <span style={{ color: '#0f172a' }}>A Domicilio / Delivery</span>
                    <span style={{ color: '#7c3aed' }}>
                      {data.order_types.domicilio} pedidos ({Math.round(((data.order_types.domicilio || 0) / totalChannels) * 100)}%)
                    </span>
                  </div>
                  <div className="analytics-channel-bar-bg">
                    <div
                      className="analytics-channel-bar-fill"
                      style={{
                        width: `${Math.round(((data.order_types.domicilio || 0) / totalChannels) * 100)}%`,
                        background: '#8b5cf6',
                      }}
                    />
                  </div>
                </div>
              </div>
            </section>

            {/* Popular Categories */}
            <section className="analytics-panel">
              <h3>
                <UtensilsCrossed size={18} color="#16a34a" />
                Familias y Categorías Populares
              </h3>
              {data.popular_categories && data.popular_categories.length > 0 ? (
                <div className="analytics-categories-list">
                  {data.popular_categories.slice(0, 5).map((cat) => (
                    <div key={cat.id} className="analytics-category-item">
                      <span className="analytics-category-name">{cat.name || 'Sin Categoría'}</span>
                      <div className="analytics-category-metrics">
                        <strong>{cat.quantity} uds.</strong>
                        <span>{formatMoney(cat.known_net_cents)}</span>
                        <Badge variant="default">{(cat.share_bps / 100).toFixed(1)}%</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ color: '#64748b', fontSize: '0.9rem', margin: '20px 0' }}>
                  No se registraron ventas por categoría en el mes seleccionado.
                </p>
              )}
            </section>
          </div>

          {/* Activity Trend Chart */}
          {data.activity_chart && data.activity_chart.length > 0 && (
            <section className="analytics-panel" style={{ marginBottom: 24 }}>
              <h3>
                <BarChart3 size={18} color="#0d9488" />
                Tendencia de Actividad Comercial Diaria
              </h3>
              <div className="analytics-activity-chart">
                {data.activity_chart.map((dayItem, index) => {
                  const barHeight = Math.max(Math.round((dayItem.completed / maxActivity) * 90), 6);
                  return (
                    <div key={index} className="analytics-activity-bar-wrap">
                      <span className="analytics-activity-count">{dayItem.completed}</span>
                      <div
                        className="analytics-activity-bar"
                        style={{ height: `${barHeight}px` }}
                        title={`${dayItem.day}: ${dayItem.completed} pedidos`}
                      />
                      <span className="analytics-activity-label">{dayItem.day}</span>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Recent Orders / Transactions */}
          <section className="analytics-panel">
            <h3>
              <Clock size={18} color="#475569" />
              Últimas Transacciones Registradas
            </h3>
            {data.recent_transactions && data.recent_transactions.length > 0 ? (
              <div className="analytics-table-wrap">
                <table className="analytics-table">
                  <thead>
                    <tr>
                      <th>Folio</th>
                      <th>Fecha y Hora</th>
                      <th>Importe</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_transactions.map((tx) => (
                      <tr key={tx.id}>
                        <td>
                          <strong style={{ color: '#0f172a' }}>{tx.folio || tx.id.slice(0, 8)}</strong>
                        </td>
                        <td>
                          {new Date(tx.created_at).toLocaleString('es-MX', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </td>
                        <td>
                          <strong style={{ color: '#047857' }}>{formatMoney(tx.amount_cents)}</strong>
                        </td>
                        <td>
                          <Badge variant="success">CONFIRMADO</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p style={{ color: '#64748b', fontSize: '0.9rem', margin: '16px 0' }}>
                No hay transacciones registradas en el periodo.
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
