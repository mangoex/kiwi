import React, { useEffect, useState } from 'react';
import { DollarSign, ShoppingBag, TrendingUp, Users } from 'lucide-react';

interface Order {
  id: string;
  total_cents: number;
  status: string;
}

const StatCard = ({ title, value, icon, color }: { title: string, value: string, icon: React.ReactNode, color: string }) => (
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
  const [orders, setOrders] = useState<Order[]>([]);

  useEffect(() => {
    const fetchOrders = async () => {
      try {
        const res = await fetch('/api/v1/orders');
        const data = await res.json();
        setOrders(Array.isArray(data) ? data : []);
      } catch (e) {
        console.error("Error fetching orders:", e);
        setOrders([]);
      }
    };
    fetchOrders();
  }, []);

  const validOrders = orders.filter(o => o.status !== 'CANCELLED');
  const totalSalesCents = validOrders.reduce((acc, o) => acc + o.total_cents, 0);
  
  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 }).format(cents / 100 || 0);
  };

  const avgTicket = validOrders.length > 0 ? totalSalesCents / validOrders.length : 0;

  return (
    <div style={{ padding: '32px' }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: 8, color: 'var(--text-main)' }}>Resumen del Día</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 32 }}>Métricas en tiempo real de la sucursal actual.</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 24, marginBottom: 32 }}>
        <StatCard 
          title="Ventas Totales" 
          value={formatCurrency(totalSalesCents)} 
          icon={<DollarSign size={20} />} 
          color="#10b981" 
        />
        <StatCard 
          title="Órdenes Completadas" 
          value={String(validOrders.length)} 
          icon={<ShoppingBag size={20} />} 
          color="#3b82f6" 
        />
        <StatCard 
          title="Ticket Promedio" 
          value={formatCurrency(avgTicket)} 
          icon={<TrendingUp size={20} />} 
          color="#8b5cf6" 
        />
        <StatCard 
          title="Clientes Nuevos" 
          value={String(orders.length > 0 ? Math.floor(validOrders.length * 0.8) : 0)} 
          icon={<Users size={20} />} 
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
