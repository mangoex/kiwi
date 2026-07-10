import React, { useEffect, useState } from 'react';
import { ArrowUpRight, ArrowDownRight, MoreVertical, Plus, Download } from 'lucide-react';

const formatCurrency = (cents: number) => {
  return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(cents / 100);
};

const Overview = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  const [branches, setBranches] = useState<any[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  
  // Current month simple mock logic
  const now = new Date();
  const currentMonthValue = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const [selectedMonth, setSelectedMonth] = useState<string>(currentMonthValue);

  useEffect(() => {
    const fetchBranches = async () => {
      const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
      try {
        const res = await fetch('/api/v1/branches', { headers: { 'Authorization': `Bearer ${token}` } });
        if (res.ok) {
          const json = await res.json();
          setBranches(json);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchBranches();
  }, []);

  useEffect(() => {
    const fetchDashboard = async () => {
      setLoading(true);
      try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        let url = '/api/v1/dashboard/overview?';
        if (selectedBranch) url += `branch_id=${selectedBranch}&`;
        if (selectedMonth) url += `month=${selectedMonth}`;
        
        const res = await fetch(url, {
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
  }, [selectedBranch, selectedMonth]);

  const handleAddCategory = () => {
    const name = prompt("Nombre de la nueva categoría popular:");
    if (name) {
       alert(`Categoría ${name} agregada (Simulación). El backend de agregar categoría puede ir aquí.`);
    }
  };

  if (loading && !data) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--admin-text-muted)' }}>Cargando datos...</div>;
  }

  const overviewData = data || {
    total_revenue_cents: 0,
    total_orders: 0,
    total_products: 0,
    recent_transactions: [],
    activity_chart: [],
    recent_notifications: [],
    popular_categories: []
  };

  const monthOptions = [
    { value: '2026-06', label: 'Junio 2026' },
    { value: '2026-07', label: 'Julio 2026' },
    { value: '2026-08', label: 'Agosto 2026' }
  ];

  return (
    <>
      <div className="admin-title-row">
        <h1 className="admin-title">Panel Principal</h1>
        <div style={{ display: 'flex', gap: 12 }}>
          <select 
            value={selectedBranch} 
            onChange={e => setSelectedBranch(e.target.value)}
            style={{ padding: '8px 16px', borderRadius: '8px', border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontWeight: 500 }}
          >
            <option value="">Todas las Sucursales</option>
            {branches.map(b => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Top Row: Balance and Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2.5fr', gap: 24, marginBottom: 24 }}>
        
        {/* Total Balance */}
        <div className="admin-metric-card dark">
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div className="admin-metric-title">Balance Total</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--admin-sidebar-text)' }}>Última Actualización hoy</div>
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
            <select 
              value={selectedMonth} 
              onChange={e => setSelectedMonth(e.target.value)}
              style={{ fontSize: '0.875rem', color: 'var(--admin-text-muted)', border: '1px solid #e2e8f0', padding: '4px 12px', borderRadius: '20px', background: '#fff' }}
            >
              {monthOptions.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
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
                {item.day.split(' ')[0]}
              </div>
            ))}
          </div>
        </div>

        {/* Popular Tags */}
        <div className="admin-chart-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Categorías Populares</h3>
            <MoreVertical size={16} color="var(--admin-text-muted)" style={{ cursor: 'pointer' }} onClick={handleAddCategory} />
          </div>
          <div className="admin-tags-grid">
            {overviewData.popular_categories?.map((cat: any) => (
              <span key={cat.id} className="admin-tag">#{cat.name.toLowerCase()}</span>
            ))}
            {(!overviewData.popular_categories || overviewData.popular_categories.length === 0) && (
              <span style={{ fontSize: '0.875rem', color: 'var(--admin-text-muted)' }}>Sin categorías</span>
            )}
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
            {overviewData.recent_notifications?.map((msg: any, i: number) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 40, height: 40, borderRadius: '50%', background: msg.action === 'cash_shift.opened' ? '#dcfce7' : '#fee2e2', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem' }}>
                  {msg.action === 'cash_shift.opened' ? '🔓' : '🔒'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                    {msg.register_code || msg.payload?.register_code || 'Caja'}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--admin-text-muted)' }}>
                    {msg.action === 'cash_shift.opened' ? 'Abrió la caja' : 'Cerró la caja'}
                    {msg.actor_name && msg.actor_name !== 'Sistema' ? ` · ${msg.actor_name}` : ''}
                  </div>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--admin-text-muted)', whiteSpace: 'nowrap' }}>
                  {new Date(msg.created_at).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            ))}
            {(!overviewData.recent_notifications || overviewData.recent_notifications.length === 0) && (
              <div style={{ fontSize: '0.875rem', color: 'var(--admin-text-muted)', textAlign: 'center' }}>No hay turnos recientes</div>
            )}
          </div>
        </div>

        {/* Latest Transactions */}
        <div className="admin-chart-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Últimas Transacciones</h3>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <Download size={16} color="var(--admin-text-muted)" style={{ cursor: 'pointer' }} />
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
              {overviewData.recent_transactions?.map((t: any) => (
                <tr key={t.id}>
                  <td>{t.folio}</td>
                  <td style={{ color: 'var(--admin-text-muted)' }}>{new Date(t.created_at).toLocaleDateString()}</td>
                  <td style={{ padding: '12px 16px', fontSize: '0.875rem' }}>
                  <span className={`admin-badge ${['completed', 'CONFIRMED', 'CLOSED'].includes(t.status) ? 'success' : 'pending'}`}>
                    {['completed', 'CONFIRMED', 'CLOSED'].includes(t.status) ? 'Completado' : (t.status === 'pending' ? 'Pendiente' : t.status)}
                  </span>
                </td>
                  <td style={{ fontWeight: 700 }}>{formatCurrency(t.amount_cents)}</td>
                  <td><MoreVertical size={16} color="var(--admin-text-muted)" style={{ cursor: 'pointer' }} /></td>
                </tr>
              ))}
              {(!overviewData.recent_transactions || overviewData.recent_transactions.length === 0) && (
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
