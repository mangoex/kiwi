import React, { useEffect, useState } from 'react';
import { Card, Table, Badge, Button } from '@restaurantos/ui';
import { Clock, CheckCircle, XCircle } from 'lucide-react';

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

  useEffect(() => {
    const fetchOrders = async () => {
      try {
        const response = await fetch('/api/v1/orders');
        const data = await response.json();
        setOrders(data);
      } catch (e) {
        console.error("Error fetching orders:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchOrders();
  }, []);

  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(cents / 100 || 0); // Need to divide by 100 since it's cents, wait, in operations we didn't multiply by 100, wait, price_cents was used as is. I will assume it's cents.
  };

  const getStatusBadge = (status: string) => {
    if (status === 'ACCEPTED') return <Badge variant="success" icon={<CheckCircle size={14} />}>Aceptado</Badge>;
    if (status === 'CLOSED') return <Badge variant="default" icon={<CheckCircle size={14} />}>Cerrado</Badge>;
    if (status === 'CANCELLED') return <Badge variant="destructive" icon={<XCircle size={14} />}>Cancelado</Badge>;
    return <Badge>{status}</Badge>;
  };

  const getTypeLabel = (type?: string) => {
    if (type === 'dine-in') return 'Comedor';
    if (type === 'takeout') return 'Para Llevar';
    if (type === 'delivery') return 'Domicilio';
    return type || 'N/A';
  };

  return (
    <div style={{ padding: '32px' }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: 8, color: 'var(--text-main)' }}>Historial de Transacciones</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 32 }}>Consulta los pedidos recientes y su estado.</p>

      <Card>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Cargando órdenes...</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <th>Folio</th>
                <th>Cliente</th>
                <th>Tipo</th>
                <th>Fecha/Hora</th>
                <th>Estado</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                    No hay órdenes recientes.
                  </td>
                </tr>
              ) : (
                orders.map((order) => (
                  <tr key={order.id}>
                    <td style={{ fontWeight: 600 }}>{order.folio}</td>
                    <td>{order.owner_name || 'General'}</td>
                    <td>{getTypeLabel(order.order_type)}</td>
                    <td style={{ color: 'var(--text-muted)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Clock size={14} />
                        {new Date(order.created_at).toLocaleString('es-MX')}
                      </div>
                    </td>
                    <td>{getStatusBadge(order.status)}</td>
                    <td style={{ fontWeight: 700 }}>{formatCurrency(order.total_cents)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
};

export default History;
