import React, { useEffect, useState } from 'react';
import { DollarSign, ShoppingBag, TrendingUp, Package } from 'lucide-react';
import { fetchApi } from '@restaurantos/api-client';

interface DashboardData {
  total_revenue_cents: number;
  total_orders: number;
  average_ticket_cents: number;
  total_products: number;
  period_from_utc: string;
  period_to_utc: string;
}

const StatCard = ({ title, value, icon, color }: { title: string; value: string; icon: React.ReactNode; color: string }) => (
  <div style={{ background: 'white', padding: '24px', borderRadius: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.03)', display: 'flex', flexDirection: 'column', gap: 12 }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span style={{ color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.9rem' }}>{title}</span>
      <div style={{ width: 40, height: 40, borderRadius: '12px', background: `${color}15`, color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {icon}
      </div>
    </div>
    <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.5px' }}>
      {value}
    </div>
  </div>
);

const DashboardOverview = () => {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const branchId = localStorage.getItem('pos_branch_id');
        const endpoint = branchId ? `/dashboard/overview?branch_id=${encodeURIComponent(branchId)}` : '/dashboard/overview';
        const result = await fetchApi<DashboardData>(endpoint);
        setData(result || null);
      } catch (e) {
        console.error("Error fetching dashboard overview:", e);
        setData(null);
      }
    };
    fetchDashboard();
  }, []);

  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 }).format(cents / 100 || 0);
  };

  const totalRevenue = data?.total_revenue_cents ?? 0;
  const totalOrders = data?.total_orders ?? 0;
  const totalProducts = data?.total_products ?? 0;
  const averageTicketCents = data?.average_ticket_cents ?? 0;

  return (
    <div style={{ padding: '32px' }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: 8, color: 'var(--text-main)' }}>Resumen operativo</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 32 }}>Métricas consolidadas de la sucursal actual con pagos confirmados.</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 24, marginBottom: 32 }}>
        <StatCard
          title="Ventas Totales"
          value={formatCurrency(totalRevenue)}
          icon={<DollarSign size={20} />}
          color="#10b981"
        />
        <StatCard
          title="Órdenes Cobradas"
          value={String(totalOrders)}
          icon={<ShoppingBag size={20} />}
          color="#3b82f6"
        />
        <StatCard
          title="Ticket Promedio"
          value={formatCurrency(averageTicketCents)}
          icon={<TrendingUp size={20} />}
          color="#8b5cf6"
        />
        <StatCard
          title="Productos Activos"
          value={String(totalProducts)}
          icon={<Package size={20} />}
          color="#f59e0b"
        />
      </div>

      <div style={{ background: 'white', padding: '32px', borderRadius: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.03)', height: 300, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
        <TrendingUp size={48} opacity={0.2} style={{ marginBottom: 16 }} />
        <p>Espacio para gráficas de ventas (Próximamente)</p>
      </div>
    </div>
  );
};

export default DashboardOverview;
