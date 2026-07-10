import React, { useEffect, useState } from 'react';
import { Card, Badge, Button } from '@restaurantos/ui';
import { Clock, RefreshCcw, Search, Calendar, ChevronRight } from 'lucide-react';

interface Order {
  id: string;
  folio: string;
  status: string;
  total_cents: number;
  owner_name?: string;
  order_type?: string;
  created_at: string;
}

const History = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const branchId = localStorage.getItem('pos_branch_id');
      const url = branchId ? `/api/v1/orders?branch_id=${encodeURIComponent(branchId)}` : '/api/v1/orders';
      const response = await fetch(url);
      const data = await response.json();
      setOrders(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Error fetching orders:", e);
      setOrders([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, []);

  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(cents / 100 || 0);
  };

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'COMPLETED':
      case 'CLOSED':
      case 'CERRADO':
        return { label: 'Completado', bg: '#ecfdf5', color: '#059669', border: '#a7f3d0' };
      case 'ACCEPTED':
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
    if (type === 'dine-in') return 'Comedor';
    if (type === 'takeout') return 'Para Llevar';
    if (type === 'delivery') return 'Domicilio';
    return type || 'General';
  };

  const filteredOrders = orders.filter(order => 
    order.folio?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    order.owner_name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: '2.25rem', fontWeight: 800, marginBottom: 8, color: '#0f172a', letterSpacing: '-0.5px' }}>Historial de Transacciones</h1>
          <p style={{ color: '#64748b', fontSize: '1.05rem' }}>Consulta y gestiona los pedidos de esta sucursal.</p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ position: 'relative' }}>
            <Search size={18} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            <input 
              type="text" 
              placeholder="Buscar folio o cliente..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                padding: '10px 16px 10px 38px',
                borderRadius: '12px',
                border: '1px solid #e2e8f0',
                outline: 'none',
                width: '260px',
                fontSize: '0.95rem',
                color: '#334155',
                transition: 'all 0.2s',
                boxShadow: '0 2px 4px rgba(0,0,0,0.02)'
              }}
            />
          </div>
          <Button variant="secondary" onClick={fetchOrders} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '10px 16px', borderRadius: '12px', background: 'white', border: '1px solid #e2e8f0', color: '#475569', fontWeight: 600, cursor: 'pointer', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
            <RefreshCcw size={18} />
            Actualizar
          </Button>
        </div>
      </div>

      <Card style={{ padding: 0, borderRadius: '16px', border: '1px solid #e2e8f0', boxShadow: '0 10px 30px rgba(0,0,0,0.03)', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '60px 20px', textAlign: 'center', color: '#94a3b8', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <RefreshCcw size={32} className="animate-spin" />
            <span style={{ fontSize: '1.1rem', fontWeight: 500 }}>Cargando órdenes...</span>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                <th style={{ padding: '16px 24px', color: '#64748b', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Folio</th>
                <th style={{ padding: '16px 24px', color: '#64748b', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Cliente</th>
                <th style={{ padding: '16px 24px', color: '#64748b', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Tipo</th>
                <th style={{ padding: '16px 24px', color: '#64748b', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Fecha y Hora</th>
                <th style={{ padding: '16px 24px', color: '#64748b', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Estado</th>
                <th style={{ padding: '16px 24px', color: '#64748b', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', textAlign: 'right' }}>Total</th>
                <th style={{ padding: '16px 24px' }}></th>
              </tr>
            </thead>
            <tbody>
              {filteredOrders.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '60px 0', color: '#94a3b8' }}>
                    <Calendar size={48} style={{ margin: '0 auto', marginBottom: 16, opacity: 0.5 }} />
                    <span style={{ fontSize: '1.1rem', fontWeight: 500 }}>No se encontraron órdenes.</span>
                  </td>
                </tr>
              ) : (
                filteredOrders.map((order) => {
                  const statusConf = getStatusConfig(order.status);
                  return (
                    <tr key={order.id} style={{ borderBottom: '1px solid #f1f5f9', transition: 'background-color 0.2s', cursor: 'pointer' }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f8fafc'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
                      <td style={{ padding: '20px 24px' }}>
                        <span style={{ fontWeight: 700, color: '#334155' }}>{order.folio}</span>
                      </td>
                      <td style={{ padding: '20px 24px', color: '#475569', fontWeight: 500 }}>
                        {order.owner_name || 'General'}
                      </td>
                      <td style={{ padding: '20px 24px', color: '#64748b' }}>
                        {getTypeLabel(order.order_type)}
                      </td>
                      <td style={{ padding: '20px 24px', color: '#64748b' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <Clock size={16} />
                          {new Date(order.created_at).toLocaleString('es-MX', { 
                            day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' 
                          })}
                        </div>
                      </td>
                      <td style={{ padding: '20px 24px' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          padding: '6px 12px',
                          borderRadius: '9999px',
                          fontSize: '0.8rem',
                          fontWeight: 700,
                          backgroundColor: statusConf.bg,
                          color: statusConf.color,
                          border: `1px solid ${statusConf.border}`,
                          textTransform: 'uppercase',
                          letterSpacing: '0.5px'
                        }}>
                          {statusConf.label}
                        </span>
                      </td>
                      <td style={{ padding: '20px 24px', fontWeight: 800, color: '#0f172a', textAlign: 'right', fontSize: '1.05rem' }}>
                        {formatCurrency(order.total_cents)}
                      </td>
                      <td style={{ padding: '20px 24px', color: '#cbd5e1', textAlign: 'right' }}>
                        <ChevronRight size={20} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
};

export default History;
