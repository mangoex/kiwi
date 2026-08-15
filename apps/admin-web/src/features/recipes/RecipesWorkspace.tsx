import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';
import { RecipeManager, RecipeWorkspaceItem } from '../catalog/RecipeManager';
import { resolveBranchId } from '../../lib/branchContext';

type Branch = { id: string; name: string; code: string };
type Product = { id: string; name: string; sku: string };
type Workspace = { selected_branch_id: string | null; corporate_allowed: boolean; scopes: { branches: Branch[] }; products: Product[]; items: RecipeWorkspaceItem[] };

export default function RecipesWorkspace() {
  // null is an explicit corporate scope, including a first owner visit without a saved branch.
  const [scope, setScope] = useState<string | null>(() => resolveBranchId() || null);
  const [selected, setSelected] = useState<Product | null>(null);
  const query = useQuery<Workspace>({ queryKey: ['recipes-workspace', scope], queryFn: () => fetchApi<Workspace>(`/recipes/workspace${scope === null ? '' : `?branch_id=${encodeURIComponent(scope)}`}`) });
  const workspace = query.data;
  const branches = workspace?.scopes.branches || [];
  const selectedScope = useMemo(() => scope, [scope]);
  if (query.isLoading) return <div style={{ padding: 24 }}>Cargando espacio de recetas…</div>;
  if (query.isError || !workspace) return <div role="alert" style={{ padding: 24 }}>No fue posible cargar las recetas autorizadas.</div>;
  return <section style={{ padding: 24, color: '#111827' }}>
    <h2 style={{ color: '#111827' }}>Recetas</h2><p style={{ color: '#374151' }}>Productos e insumos de solo lectura; el backend decide alcance, versión y costo.</p>
    <label style={{ color: '#111827', fontWeight: 600 }}>Alcance <select aria-label="Alcance de receta" value={selectedScope ?? ''} onChange={(event) => setScope(event.target.value === '' ? null : event.target.value)}>
      {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
      {workspace.corporate_allowed && <option value="">Corporativa</option>}
    </select></label>
    <div style={{ marginTop: 20, overflowX: 'auto', border: '1px solid #d1d5db', borderRadius: 8, background: '#fff' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', color: '#111827' }}><thead style={{ background: '#f3f4f6' }}><tr><th style={{ padding: 12, textAlign: 'left', color: '#111827' }}>Producto</th><th style={{ padding: 12, textAlign: 'left', color: '#111827' }}>SKU</th><th style={{ padding: 12, textAlign: 'right' }} /></tr></thead><tbody>{workspace.products.map((product) => <tr key={product.id} style={{ borderTop: '1px solid #e5e7eb' }}><td style={{ padding: 12, color: '#111827' }}>{product.name}</td><td style={{ padding: 12, color: '#374151' }}>{product.sku}</td><td style={{ padding: 12, textAlign: 'right' }}><button style={{ color: '#fff', background: '#2563eb', border: 0, borderRadius: 6, padding: '8px 12px', cursor: 'pointer' }} onClick={() => setSelected(product)}>Editar receta</button></td></tr>)}</tbody></table>
    </div>
    {selected && <RecipeManager isOpen productId={selected.id} productName={selected.name} branchId={selectedScope || null} items={workspace.items} onClose={() => setSelected(null)} />}
  </section>;
}
