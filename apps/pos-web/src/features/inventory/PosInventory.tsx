import React, { useEffect, useState } from 'react';
import { Card, Badge } from '@restaurantos/ui';
import { Package, Search } from 'lucide-react';

interface InventoryItem {
  id: string;
  sku: string;
  name: string;
  item_type: string;
  status: string;
  quantity: number;
}

const PosInventory = () => {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    const fetchInventory = async () => {
      try {
        const response = await fetch('/api/v1/catalog/items');
        const data = await response.json();
        
        if (Array.isArray(data)) {
          // Mocking stock quantity for now as POS doesn't compute ledger on client side
          const itemsWithMockStock = data.map((d: any) => ({
            ...d,
            quantity: Math.floor(Math.random() * 100) + 10
          }));
          setItems(itemsWithMockStock);
        } else {
          setItems([]);
        }
      } catch (e) {
        console.error("Error fetching inventory:", e);
        setItems([]);
      } finally {
        setLoading(false);
      }
    };
    fetchInventory();
  }, []);

  const filtered = items.filter(item => item.name.toLowerCase().includes(searchTerm.toLowerCase()) || item.sku.toLowerCase().includes(searchTerm.toLowerCase()));

  return (
    <div style={{ padding: '32px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: 8, color: 'var(--text-main)' }}>Inventario de Sucursal</h1>
          <p style={{ color: 'var(--text-muted)' }}>Consulta el stock actual de insumos y productos para venta.</p>
        </div>
        <div style={{ background: 'white', padding: '10px 16px', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: 12, border: '1px solid var(--glass-border)', width: 300 }}>
          <Search size={18} color="var(--text-muted)" />
          <input 
            type="text" 
            placeholder="Buscar por nombre o SKU..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ background: 'transparent', border: 'none', outline: 'none', width: '100%' }} 
          />
        </div>
      </div>

      <Card>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Cargando inventario...</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--glass-border)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '12px' }}>SKU</th>
                <th style={{ padding: '12px' }}>Insumo / Producto</th>
                <th style={{ padding: '12px' }}>Tipo</th>
                <th style={{ padding: '12px' }}>Stock Disponible</th>
                <th style={{ padding: '12px' }}>Estado</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                    No se encontraron insumos.
                  </td>
                </tr>
              ) : (
                filtered.map((item) => (
                  <tr key={item.id}>
                    <td style={{ color: 'var(--text-muted)', fontFamily: 'monospace' }}>{item.sku}</td>
                    <td style={{ fontWeight: 600 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Package size={16} color="var(--primary)" />
                        {item.name}
                      </div>
                    </td>
                    <td style={{ textTransform: 'capitalize' }}>{item.item_type}</td>
                    <td style={{ fontWeight: 800, color: item.quantity < 20 ? 'var(--destructive)' : 'var(--text-main)' }}>
                      {item.quantity}
                    </td>
                    <td>
                      {item.status === 'active' ? (
                        <Badge variant="success">Activo</Badge>
                      ) : (
                        <Badge variant="default">{item.status}</Badge>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
};

export default PosInventory;
