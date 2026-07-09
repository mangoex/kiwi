import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Button, Badge } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Package, Edit, Trash2 } from 'lucide-react';

interface Product {
  id: string;
  name: string;
  sku: string;
  category_name: string;
  price_cents: number;
  station: string;
}

const ProductsList = () => {
  const { data: products, isLoading, error } = useQuery<Product[]>({
    queryKey: ['products'],
    queryFn: () => fetchApi('/catalog/products'),
  });

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="admin-title" style={{ marginBottom: 4 }}>Products & Catalog</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>Manage your inventory, pricing, and stations.</p>
        </div>
        <Button variant="primary" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Plus size={18} />
          Add Product
        </Button>
      </div>

      <Card style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>
            Cargando catálogo...
          </div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>
            Error al cargar los productos. Revisa tu conexión.
          </div>
        ) : !products || products.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center' }}>
            <Package size={48} style={{ color: 'var(--color-border)', margin: '0 auto 16px' }} />
            <h3 style={{ marginBottom: 8 }}>No hay productos</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Comienza agregando tu primer producto al menú.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)' }}>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Product</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>SKU</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Category</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Station</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>Price</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '16px 24px', fontWeight: 500 }}>{product.name}</td>
                  <td style={{ padding: '16px 24px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>{product.sku}</td>
                  <td style={{ padding: '16px 24px' }}>
                    <Badge variant="info">{product.category_name}</Badge>
                  </td>
                  <td style={{ padding: '16px 24px', fontSize: '0.875rem' }}>{product.station}</td>
                  <td style={{ padding: '16px 24px', textAlign: 'right', fontWeight: 600 }}>
                    ${(product.price_cents / 100).toFixed(2)}
                  </td>
                  <td style={{ padding: '16px 24px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                      <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-blue)' }}><Edit size={18} /></button>
                      <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-red)' }}><Trash2 size={18} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
};

export default ProductsList;
