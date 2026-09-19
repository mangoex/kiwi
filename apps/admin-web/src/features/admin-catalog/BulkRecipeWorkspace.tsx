import React, { useMemo, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Plus, Trash2 } from 'lucide-react';
import { resolveBranchId } from '../../lib/branchContext';
import '../../premium-catalogs.css';

type WorkspaceItem = { id: string; name: string; sku: string; unit_id: string; unit_code?: string };
type Product = { id: string; name: string; sku: string };
type Workspace = { products: Product[]; items: WorkspaceItem[] };
type Branch = { id: string; name: string; status: string };
type Unit = { id: string; code: string; name: string };
type Component = { item_id: string; unit_id: string; net_quantity: string; waste_rate: string };
type Draft = { branch_id: string | null; destination_product_ids: string[]; yield_quantity: string; yield_unit_id: string; components: Component[] };
type Preview = {
  branch_id: string | null;
  fingerprint: string;
  normalized_payload: Omit<Draft, 'branch_id' | 'destination_product_ids'>;
  destinations: Array<{
    product_id: string; expected_active_recipe_id: string | null; expected_version: number; has_active_recipe: boolean;
    difference: {
      current_yield_quantity: string | null; current_yield_unit_id: string | null; current_components: Component[];
      next_yield_quantity: string; next_yield_unit_id: string; next_components: Component[]; changed: boolean;
    };
  }>;
};
type ApplyResult = { command_id: string; destinations: Array<{ product_id: string; recipe_id: string; recipe_version: number }> };

const emptyComponent = (): Component => ({ item_id: '', unit_id: '', net_quantity: '', waste_rate: '0' });
const failure = (reason: unknown, fallback: string) => reason instanceof ApiError ? reason.message : fallback;

export default function BulkRecipeWorkspace() {
  const [scope, setScope] = useState<string | null>(() => resolveBranchId() || null);
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [yieldQuantity, setYieldQuantity] = useState('1');
  const [yieldUnitId, setYieldUnitId] = useState('');
  const [components, setComponents] = useState<Component[]>([emptyComponent()]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [message, setMessage] = useState('');
  const idempotencyKey = useRef('');
  const workspace = useQuery<Workspace>({
    queryKey: ['recipes-workspace', 'bulk', scope],
    queryFn: () => fetchApi(`/recipes/workspace${scope === null ? '' : `?branch_id=${encodeURIComponent(scope)}`}`),
  });
  const branches = useQuery<Branch[]>({ queryKey: ['branches', 'bulk-recipes'], queryFn: () => fetchApi('/branches') });
  const units = useQuery<Unit[]>({ queryKey: ['inventory', 'units', 'bulk-recipes'], queryFn: () => fetchApi('/inventory/units') });
  const draft = useMemo<Draft>(() => ({
    branch_id: scope,
    destination_product_ids: selectedProductIds,
    yield_quantity: yieldQuantity,
    yield_unit_id: yieldUnitId,
    components,
  }), [components, scope, selectedProductIds, yieldQuantity, yieldUnitId]);
  const invalidatePreview = () => { setPreview(null); setMessage(''); idempotencyKey.current = ''; };
  const updateComponent = (index: number, patch: Partial<Component>) => {
    invalidatePreview();
    setComponents((previous) => previous.map((component, componentIndex) => componentIndex === index ? { ...component, ...patch } : component));
  };

  const requestPreview = useMutation({
    mutationFn: () => fetchApi<Preview>('/admin-catalog/recipes/bulk-preview', { method: 'POST', body: JSON.stringify(draft) }),
    onSuccess: (response) => { setPreview(response); idempotencyKey.current = crypto.randomUUID(); setMessage('Vista previa preparada. Revisa cada destino antes de aplicar.'); },
    onError: (reason) => setMessage(failure(reason, 'No fue posible preparar la vista previa.')),
  });
  const apply = useMutation({
    mutationFn: () => {
      if (!preview) throw new Error('No hay vista previa vigente.');
      const expected_active_recipe_ids = Object.fromEntries(preview.destinations.map((destination) => [destination.product_id, destination.expected_active_recipe_id]));
      const { yield_quantity, yield_unit_id, components: normalizedComponents } = preview.normalized_payload;
      return fetchApi<ApplyResult>('/admin-catalog/recipes/bulk-apply', {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey.current },
        body: JSON.stringify({
          yield_quantity,
          yield_unit_id,
          components: normalizedComponents.map((component) => ({
            item_id: component.item_id,
            unit_id: component.unit_id,
            net_quantity: component.net_quantity,
            waste_rate: component.waste_rate,
          })),
          branch_id: preview.branch_id,
          destination_product_ids: preview.destinations.map((destination) => destination.product_id),
          preview_fingerprint: preview.fingerprint,
          expected_active_recipe_ids,
        }),
      });
    },
    onSuccess: (response) => setMessage(`Lote aplicado: ${response.destinations.length} receta(s) versionada(s). Comando ${response.command_id}.`),
    onError: (reason) => setMessage(failure(reason, 'No fue posible aplicar el lote. No se guardó un resultado parcial.')),
  });
  const activeItems = workspace.data?.items || [];
  const products = workspace.data?.products || [];
  const unitLabel = (unitId: string) => (units.data || []).find((unit) => unit.id === unitId)?.code || unitId;
  const componentLabel = (component: Component) => {
    const item = activeItems.find((candidate) => candidate.id === component.item_id);
    return `${item?.name || component.item_id} — ${component.net_quantity} ${unitLabel(component.unit_id)}, merma ${component.waste_rate}`;
  };

  if (workspace.isLoading) return <p role="status">Cargando productos e insumos autorizados…</p>;
  if (workspace.isError || !workspace.data) return <p role="alert">No fue posible cargar el espacio de recetas.</p>;

  return (
    <main className="admin-catalog-tool">
      <header className="admin-catalog-tool__header">
        <div><h1 className="premium-header-title">Aplicar receta a varios productos</h1><p className="premium-header-subtitle">La vista previa no escribe datos. El servidor valida y versiona el lote completo al confirmar.</p></div>
      </header>
      {message && <p className="admin-catalog-message" role="status">{message}</p>}
      <section className="premium-card" style={{ padding: 20, marginBottom: 20 }}>
        <div className="premium-form-grid">
          <label className="premium-form-group">Alcance
            <select value={scope ?? ''} onChange={(event) => { invalidatePreview(); setScope(event.target.value || null); }}>
              <option value="">Corporativo</option>
              {(branches.data || []).filter((branch) => branch.status === 'active').map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
            </select>
          </label>
          <label className="premium-form-group">Rendimiento
            <input value={yieldQuantity} inputMode="decimal" onChange={(event) => { invalidatePreview(); setYieldQuantity(event.target.value); }} />
          </label>
          <label className="premium-form-group">Unidad de rendimiento
            <select value={yieldUnitId} onChange={(event) => { invalidatePreview(); setYieldUnitId(event.target.value); }}>
              <option value="">Selecciona una unidad</option>
              {(units.data || []).map((unit) => <option key={unit.id} value={unit.id}>{unit.name} ({unit.code})</option>)}
            </select>
          </label>
        </div>
      </section>
      <section className="premium-card" style={{ padding: 20, marginBottom: 20 }}>
        <h2 style={{ fontSize: '1rem', marginBottom: 12 }}>Productos destino</h2>
        <div className="admin-catalog-checkbox-grid">
          {products.map((product) => <label className="premium-checkbox-card" key={product.id}><input type="checkbox" checked={selectedProductIds.includes(product.id)} onChange={() => { invalidatePreview(); setSelectedProductIds((ids) => ids.includes(product.id) ? ids.filter((id) => id !== product.id) : [...ids, product.id]); }} /> {product.name} <small>{product.sku}</small></label>)}
        </div>
      </section>
      <section className="premium-card" style={{ padding: 20, marginBottom: 20 }}>
        <div className="admin-catalog-tool__header"><h2 style={{ fontSize: '1rem' }}>Componentes comunes</h2><button type="button" className="premium-add-btn" onClick={() => { invalidatePreview(); setComponents((rows) => [...rows, emptyComponent()]); }}><Plus size={16} /> Agregar componente</button></div>
        <div style={{ overflowX: 'auto' }}><table className="premium-table"><thead><tr><th>Insumo</th><th>Unidad</th><th>Cantidad neta</th><th>Merma</th><th><span className="sr-only">Quitar</span></th></tr></thead><tbody>
          {components.map((component, index) => <tr key={index}><td><select value={component.item_id} onChange={(event) => { const item = activeItems.find((candidate) => candidate.id === event.target.value); updateComponent(index, { item_id: event.target.value, unit_id: item?.unit_id || '' }); }}><option value="">Selecciona un insumo</option>{activeItems.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.sku})</option>)}</select></td><td>{activeItems.find((item) => item.id === component.item_id)?.unit_code || '—'}</td><td><input value={component.net_quantity} inputMode="decimal" onChange={(event) => updateComponent(index, { net_quantity: event.target.value })} /></td><td><input value={component.waste_rate} inputMode="decimal" onChange={(event) => updateComponent(index, { waste_rate: event.target.value })} /></td><td><button type="button" aria-label="Quitar componente" disabled={components.length === 1} onClick={() => { invalidatePreview(); setComponents((rows) => rows.filter((_, rowIndex) => rowIndex !== index)); }}><Trash2 size={16} /></button></td></tr>)}
        </tbody></table></div>
      </section>
      <div className="admin-catalog-tool__actions"><button className="premium-add-btn" type="button" disabled={requestPreview.isPending || !selectedProductIds.length || !yieldUnitId} onClick={() => requestPreview.mutate()}>{requestPreview.isPending ? 'Preparando…' : 'Ver diferencias'}</button><button className="premium-add-btn" type="button" disabled={!preview || apply.isPending} onClick={() => apply.mutate()}>{apply.isPending ? 'Aplicando…' : 'Confirmar lote versionado'}</button></div>
      {preview && <section className="premium-card" style={{ padding: 20, marginTop: 20 }}><h2 style={{ fontSize: '1rem', marginBottom: 12 }}>Diferencias revisadas</h2><p className="premium-form-hint">Huella {preview.fingerprint}. Si cambia un destino, el servidor rechazará el lote completo.</p><p>Composición que el servidor normalizó: rendimiento {preview.normalized_payload.yield_quantity}, {preview.normalized_payload.components.length} componente(s).</p><ul>{preview.destinations.map((destination) => <li key={destination.product_id}><strong>{products.find((product) => product.id === destination.product_id)?.name || destination.product_id}</strong>: {destination.difference.changed ? 'cambio preparado' : 'sin diferencia con la receta activa'}; {destination.has_active_recipe ? ` versión activa esperada ${destination.expected_version}` : ' creará la primera receta activa'}.
        <div className="admin-catalog-difference"><p><strong>Rendimiento</strong>: {destination.difference.current_yield_quantity || '—'} {destination.difference.current_yield_unit_id ? unitLabel(destination.difference.current_yield_unit_id) : '—'} → {destination.difference.next_yield_quantity} {unitLabel(destination.difference.next_yield_unit_id)}</p><div><strong>Antes</strong>{destination.difference.current_components.length ? <ul>{destination.difference.current_components.map((component, index) => <li key={`${component.item_id}-${index}`}>{componentLabel(component)}</li>)}</ul> : <p>Sin componentes.</p>}</div><div><strong>Después</strong>{destination.difference.next_components.length ? <ul>{destination.difference.next_components.map((component, index) => <li key={`${component.item_id}-${index}`}>{componentLabel(component)}</li>)}</ul> : <p>Sin componentes.</p>}</div></div>
      </li>)}</ul></section>}
    </main>
  );
}
