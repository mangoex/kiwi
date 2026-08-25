import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';
import { RecipeManager, RecipeWorkspaceItem } from '../catalog/RecipeManager';
import { resolveBranchId } from '../../lib/branchContext';
import { ChefHat, Search, SlidersHorizontal, BookOpen } from 'lucide-react';
import '../../premium-catalogs.css';

type Branch = { id: string; name: string; code: string };
type Product = { id: string; name: string; sku: string };
type Workspace = {
  selected_branch_id: string | null;
  corporate_allowed: boolean;
  scopes: { branches: Branch[] };
  products: Product[];
  items: RecipeWorkspaceItem[];
};

export default function RecipesWorkspace() {
  const [scope, setScope] = useState<string | null>(() => resolveBranchId() || null);
  const [selected, setSelected] = useState<Product | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const query = useQuery<Workspace>({
    queryKey: ['recipes-workspace', scope],
    queryFn: () => fetchApi<Workspace>(`/recipes/workspace${scope === null ? '' : `?branch_id=${encodeURIComponent(scope)}`}`),
  });

  const workspace = query.data;
  const branches = workspace?.scopes.branches || [];
  const selectedScope = useMemo(() => scope, [scope]);

  const filteredProducts = useMemo(() => {
    if (!workspace?.products) return [];
    return workspace.products.filter((p) =>
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [workspace?.products, searchTerm]);

  if (query.isLoading) {
    return (
      <div className="premium-card" style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>
        Cargando catálogo de productos y recetas...
      </div>
    );
  }

  if (query.isError || !workspace) {
    return (
      <div role="alert" className="premium-card" style={{ padding: 32, color: 'var(--color-red)', textAlign: 'center' }}>
        No fue posible cargar las recetas autorizadas.
      </div>
    );
  }

  return (
    <section>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 className="premium-header-title">Escandallo y Recetas por Producto</h1>
          <p className="premium-header-subtitle">
            Selecciona un producto del menú para definir sus ingredientes, porciones y costo teórico de producción.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SlidersHorizontal size={18} style={{ color: 'var(--color-text-muted)' }} />
          <label style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text)' }}>
            Alcance:
          </label>
          <select
            aria-label="Alcance de receta"
            value={selectedScope ?? ''}
            onChange={(event) => setScope(event.target.value === '' ? null : event.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: 8,
              border: '1px solid var(--color-border)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              fontWeight: 500,
            }}
          >
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>{branch.name}</option>
            ))}
            {workspace.corporate_allowed && <option value="">Corporativa (Todas)</option>}
          </select>
        </div>
      </div>

      <div className="premium-card" style={{ marginBottom: 20, padding: 16 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Search size={18} style={{ color: 'var(--color-text-muted)' }} />
          <input
            type="text"
            placeholder="Buscar producto por nombre o SKU para configurar su receta..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: 8,
              border: '1px solid var(--color-border)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
            }}
          />
        </div>
      </div>

      <div className="premium-card">
        {filteredProducts.length === 0 ? (
          <div className="premium-empty-state">
            <BookOpen size={64} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No se encontraron productos</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Prueba con otro término de búsqueda.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th style={{ width: 120 }}>SKU</th>
                  <th>Producto del Menú</th>
                  <th style={{ textAlign: 'right' }}>Acción</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map((product) => (
                  <tr key={product.id}>
                    <td style={{ fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                      {product.sku}
                    </td>
                    <td style={{ fontWeight: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ padding: 8, background: 'rgba(34, 197, 94, 0.1)', color: '#16a34a', borderRadius: 8 }}>
                          <ChefHat size={18} />
                        </div>
                        <div>
                          <span style={{ fontSize: '0.9375rem', fontWeight: 600 }}>{product.name}</span>
                        </div>
                      </div>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="premium-add-btn"
                        style={{ padding: '6px 14px', fontSize: '0.875rem', display: 'inline-flex' }}
                        onClick={() => setSelected(product)}
                      >
                        <ChefHat size={16} />
                        Configurar Receta
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && (
        <RecipeManager
          isOpen
          productId={selected.id}
          productName={selected.name}
          branchId={selectedScope || null}
          items={workspace.items}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}