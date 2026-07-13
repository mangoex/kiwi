import React, { useEffect, useMemo, useState } from 'react';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { Search, Package, AlertCircle } from 'lucide-react';
import { usePosSession } from '../../session';
import { BranchAdminPage } from './BranchAdminPage';

interface BranchProduct {
  id: string;
  name: string;
  sku: string;
  status: string;
  station: string;
  category: string;
  price_cents: number | null;
  sellable: boolean;
  effective_availability: boolean;
  has_local_override: boolean;
}

function formatPrice(cents: number | null): string {
  if (cents === null) return '—';
  return `$${(cents / 100).toFixed(2)}`;
}

const BranchAdminProducts: React.FC = () => {
  const { hasPermission } = usePosSession();
  const [products, setProducts] = useState<BranchProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [actingId, setActingId] = useState<string | null>(null);

  const canManage = hasPermission('catalog.branch.manage');

  const loadProducts = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchApi<BranchProduct[]>('/branch-administration/catalog/products');
      setProducts(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('No se pudo cargar el catálogo.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadProducts();
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return products;
    return products.filter(
      (p) => p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q),
    );
  }, [products, search]);

  const setAvailability = async (productId: string, action: 'available' | 'unavailable' | 'inherit') => {
    setActingId(productId);
    try {
      await fetchApi(
        `/branch-administration/catalog/products/${encodeURIComponent(productId)}/availability`,
        { method: 'PUT', body: JSON.stringify({ action }) },
      );
      await loadProducts();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('No se pudo actualizar la disponibilidad.');
      }
    } finally {
      setActingId(null);
    }
  };

  return (
    <BranchAdminPage
      title="Productos y recetas"
      description="La disponibilidad se gestiona aquí; las recetas permanecen en el catálogo central."
      icon={Package}
    >
      <div style={{ position: 'relative', marginBottom: '1rem', maxWidth: '24rem' }}>
        <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
        <input
          type="text"
          placeholder="Buscar por nombre o SKU…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: '100%', padding: '0.5rem 0.75rem 0.5rem 2.25rem', border: '1px solid #d1d5db', borderRadius: '0.5rem' }}
        />
      </div>

      {error && (
        <div style={{ color: '#dc2626', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {loading ? (
        <p>Cargando productos…</p>
      ) : filtered.length === 0 ? (
        <p style={{ color: '#6b7280' }}>No hay productos que coincidan.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '0.75rem', overflow: 'hidden' }}>
            <thead>
              <tr style={{ background: '#f9fafb', textAlign: 'left' }}>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Producto</th>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Categoría</th>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Estado central</th>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Precio</th>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Vendible</th>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Disponibilidad</th>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Fuente</th>
                {canManage && <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Acciones</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr key={p.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '0.6rem 1rem' }}>
                    {p.name}
                    <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>{p.sku}</div>
                  </td>
                  <td style={{ padding: '0.6rem 1rem' }}>{p.category}</td>
                  <td style={{ padding: '0.6rem 1rem' }}>{p.status}</td>
                  <td style={{ padding: '0.6rem 1rem' }}>{formatPrice(p.price_cents)}</td>
                  <td style={{ padding: '0.6rem 1rem' }}>
                    {p.sellable ? (
                      <span style={{ color: '#16a34a' }}>Sí</span>
                    ) : (
                      <span style={{ color: '#dc2626' }}>No</span>
                    )}
                  </td>
                  <td style={{ padding: '0.6rem 1rem' }}>
                    {p.effective_availability ? (
                      <span style={{ color: '#16a34a' }}>Disponible</span>
                    ) : (
                      <span style={{ color: '#dc2626' }}>No disponible</span>
                    )}
                  </td>
                  <td style={{ padding: '0.6rem 1rem', fontSize: '0.75rem', color: '#6b7280' }}>
                    {p.has_local_override ? 'Excepción local' : 'Catálogo central'}
                  </td>
                  {canManage && (
                    <td style={{ padding: '0.6rem 1rem' }}>
                      <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
                        <button
                          onClick={() => void setAvailability(p.id, 'available')}
                          disabled={actingId === p.id}
                          style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.25rem', background: p.effective_availability && p.has_local_override ? '#f0fdf4' : '#fff' }}
                        >
                          Disponible
                        </button>
                        <button
                          onClick={() => void setAvailability(p.id, 'unavailable')}
                          disabled={actingId === p.id}
                          style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.25rem', background: !p.effective_availability && p.has_local_override ? '#fef2f2' : '#fff' }}
                        >
                          No disponible
                        </button>
                        <button
                          onClick={() => void setAvailability(p.id, 'inherit')}
                          disabled={actingId === p.id}
                          style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.25rem', background: '#fff' }}
                        >
                          Heredar
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </BranchAdminPage>
  );
};

export default BranchAdminProducts;
