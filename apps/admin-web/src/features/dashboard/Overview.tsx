import React, { useEffect, useState } from 'react';
import { ArrowUpRight, ArrowDownRight, MoreVertical, Filter, Plus, Download } from 'lucide-react';

const formatCurrency = (cents: number) => {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100);
};

const Overview = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const res = await fetch('/api/v1/dashboard/overview', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const json = await res.json();
          setData(json);
        }
      } catch (err) {
        console.error("Error fetching dashboard data", err);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, []);

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--admin-text-muted)' }}>Loading dashboard...</div>;
  }

  const overviewData = data || {
    total_revenue_cents: 0,
    total_orders: 0,
    total_products: 0,
    recent_transactions: [],
    activity_chart: []
  };

  return (
    <>
      <div className="admin-title-row">
        <h1 className="admin-title">Panel Principal</h1>
        <div style={{ display: 'flex', gap: 12 }}>
          <button style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: '8px', border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontWeight: 500 }}>
            <Filter size={16} /> Filtrar
          </button>
          <button className="admin-btn" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Plus size={16} /> Añadir Producto
          </button>
        </div>
      </div>

      {/* Top Row: Balance and Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2.5fr', gap: 24, marginBottom: 24 }}>
        
        {/* Total Balance */}
        <div className="admin-metric-card dark">
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div className="admin-metric-title">Balance Total</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--admin-sidebar-text)' }}>Última Actualización 12:15 pm</div>
          </div>
          <div className="admin-metric-value">{formatCurrency(overviewData.total_revenue_cents)}</div>
          <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', marginTop: 16 }}>
            {/* Mock SVG Wave */}
            <svg width="100%" height="60" viewBox="0 0 200 60" preserveAspectRatio="none">
              <path d="M0,40 Q20,20 40,40 T80,40 T120,40 T160,20 T200,50" fill="none" stroke="var(--admin-accent)" strokeWidth="3" />
            </svg>
          </div>
        </div>

        {/* Statistics Block */}
        <div className="admin-chart-card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Estadísticas</h3>
            <div style={{ fontSize: '0.875rem', color: 'var(--admin-text-muted)', border: '1px solid #e2e8f0', padding: '4px 12px', borderRadius: '20px' }}>Este Mes ⌄</div>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', flex: 1 }}>
            <div>
              <div className="admin-metric-title">Ganancias Totales</div>
              <div className="admin-metric-value">{formatCurrency(overviewData.total_revenue_cents)}</div>
              <div className="admin-metric-trend up"><ArrowUpRight size={14} /> +20.46%</div>
            </div>
            <div style={{ width: '1px', background: '#e2e8f0', margin: '0 24px' }}></div>
            <div>
              <div className="admin-metric-title">Número de Ventas</div>
              <div className="admin-metric-value">{overviewData.total_orders}</div>
              <div className="admin-metric-trend down"><ArrowDownRight size={14} /> -3.46%</div>
            </div>
            <div style={{ width: '1px', background: '#e2e8f0', margin: '0 24px' }}></div>
            <div>
              <div className="admin-metric-title">Vistas a Productos</div>
              <div className="admin-metric-value">{overviewData.total_products * 23}</div>
              <div className="admin-metric-trend up"><ArrowUpRight size={14} /> +8.30%</div>
            </div>
          </div>
        </div>

      </div>

      {/* Middle Row: Charts and Tags */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24, marginBottom: 24 }}>
        
        {/* Purchase Activity Chart */}
        <div className="admin-chart-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Actividad de Compras</h3>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', fontWeight: 600, color: 'var(--admin-text-muted)' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#0ea5e9' }}></span> Completado
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', fontWeight: 600, color: 'var(--admin-text-muted)' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--admin-accent)' }}></span> Pendiente
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--admin-text-muted)', border: '1px solid #e2e8f0', padding: '4px 12px', borderRadius: '20px' }}>2026 ⌄</div>
            </div>
          </div>
          
          <div style={{ height: '220px', display: 'flex', alignItems: 'flex-end', gap: '8px', padding: '20px 0 0 40px', position: 'relative', borderLeft: '1px solid #e2e8f0', borderBottom: '1px solid #e2e8f0' }}>
            {/* Y Axis Labels */}
            <div style={{ position: 'absolute', left: '-30px', top: 0, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--admin-text-muted)' }}>
              <span>100</span><span>80</span><span>60</span><span>40</span><span>20</span><span>0</span>
            </div>
            
            {/* Bars */}
            {overviewData.activity_chart.map((item: any, idx: number) => {
              const max = 15; // mock max for chart scaling
              const compH = `${(item.completed / max) * 100}%`;
              const pendH = `${(item.pending / max) * 100}%`;
              return (
                <div key={idx} style={{ flex: 1, display: 'flex', gap: '4px', alignItems: 'flex-end', height: '100%' }}>
                  <div style={{ width: '40%', height: compH, background: 'linear-gradient(to top, #38bdf8, #0ea5e9)', borderRadius: '4px 4px 0 0' }}></div>
                  <div style={{ width: '40%', height: pendH, background: 'linear-gradient(to top, #fb923c, #f97316)', borderRadius: '4px 4px 0 0' }}></div>
                </div>
              );
            })}
          </div>
          {/* X Axis */}
          <div style={{ display: 'flex', paddingLeft: '40px', marginTop: '8px' }}>
            {overviewData.activity_chart.map((item: any, idx: number) => (
              <div key={idx} style={{ flex: 1, textAlign: 'center', fontSize: '0.75rem', color: 'var(--admin-text-muted)' }}>
                {item.day.split(' ')[0]} {/* Show just the month for brevity if it's long */}
              </div>
            ))}
          </div>
        </div>

        {/* Popular Tags */}
        <div className="admin-chart-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Categorías Populares</h3>
            <MoreVertical size={16} color="var(--admin-text-muted)" />
          </div>
          <div className="admin-tags-grid">
            {['#hamburguesas', '#bebidas', '#postres', '#tacos', '#pizza', '#combos', '#papas', '#ensaladas', '#cafe', '#vegano'].map(tag => (
              <span key={tag} className="admin-tag">{tag}</span>
            ))}
          </div>
        </div>

      </div>

      {/* Bottom Row: Messages and Transactions */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 24 }}>
        
        {/* Recent Messages */}
        <div className="admin-chart-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Notificaciones Recientes</h3>
            <span style={{ fontSize: '0.875rem', color: 'var(--admin-text-muted)', cursor: 'pointer' }}>Ver Todas</span>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {[
              { name: 'Sistema', msg: 'Nuevo turno de caja abierto en Norte', time: '12:50 PM', img: 'https://i.pravatar.cc/150?u=a' },
              { name: 'Admin', msg: 'Inventario bajo en Tomates', time: '11:30 AM', img: 'https://i.pravatar.cc/150?u=b' },
              { name: 'Gerente', msg: 'Reporte de sucursal enviado ayer', time: '09:15 AM', img: 'https://i.pravatar.cc/150?u=c' },
            ].map((msg, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <img src={msg.img} alt="" style={{ width: 40, height: 40, borderRadius: '50%' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{msg.name}</div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--admin-text-muted)' }}>{msg.msg}</div>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--admin-text-muted)' }}>{msg.time}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Latest Transactions */}
        <div className="admin-chart-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Últimas Transacciones</h3>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <Download size={16} color="var(--admin-text-muted)" style={{ cursor: 'pointer' }} />
              <div style={{ fontSize: '0.875rem', color: 'var(--admin-text-muted)', border: '1px solid #e2e8f0', padding: '4px 12px', borderRadius: '20px' }}>Este Mes ⌄</div>
            </div>
          </div>
          
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID Transacción</th>
                <th>Fecha</th>
                <th>Estado</th>
                <th>Monto</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {overviewData.recent_transactions.map((t: any) => (
                <tr key={t.id}>
                  <td>{t.folio}</td>
                  <td style={{ color: 'var(--admin-text-muted)' }}>{new Date(t.created_at).toLocaleDateString()}</td>
                  <td>
                    <span className={`admin-badge ${t.status === 'completed' ? 'success' : 'pending'}`}>
                      {t.status === 'completed' ? 'Completado' : (t.status === 'pending' ? 'Pendiente' : t.status)}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700 }}>{formatCurrency(t.amount_cents)}</td>
                  <td><MoreVertical size={16} color="var(--admin-text-muted)" style={{ cursor: 'pointer' }} /></td>
                </tr>
              ))}
              {overviewData.recent_transactions.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--admin-text-muted)', padding: '24px' }}>No hay transacciones recientes</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

      </div>
    </>
  );
};

export default Overview;
