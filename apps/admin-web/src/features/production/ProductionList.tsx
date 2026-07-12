import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, Factory, Plus, Trash2 } from 'lucide-react';
import '../../premium-catalogs.css';

interface Item { id: string; name: string; sku: string; base_unit_id: string; unit_code: string; item_type: string; }
interface RecipeComponent { item_id: string; net_quantity: string; waste_percent: string; }
interface Recipe { id: string; recipe_type: string; output_item_id: string; output_item_name: string; output_item_sku: string; yield_quantity: number; yield_unit_id: string; yield_unit_code: string; version: number; }
interface Movement { id: string; movement_type: string; quantity_delta: number; }
interface Batch { id: string; recipe_id: string; lot_code: string; planned_quantity: number; actual_quantity: number; total_cost: number; unit_cost: number; status: string; movements: Movement[]; }

const currentBranchId = () => {
  const user = JSON.parse(localStorage.getItem('user') || '{}') as { assigned_branch_id?: string };
  return localStorage.getItem('admin_branch_id') || localStorage.getItem('pos_branch_id') || user.assigned_branch_id || '';
};

const ProductionList = () => {
  const branchId = currentBranchId();
  const queryClient = useQueryClient();
  const [recipeOpen, setRecipeOpen] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [error, setError] = useState('');
  const [recipeForm, setRecipeForm] = useState({ output_item_id: '', yield_quantity: '1', components: [{ item_id: '', net_quantity: '1', waste_percent: '0' }] as RecipeComponent[] });
  const [batchForm, setBatchForm] = useState({ recipe_id: '', lot_code: '', planned_quantity: '1', actual_quantity: '1', actual_waste_quantity: '0' });

  const { data: items = [] } = useQuery<Item[]>({ queryKey: ['inventory', 'items'], queryFn: () => fetchApi('/inventory/items') });
  const { data: recipes = [] } = useQuery<Recipe[]>({ queryKey: ['recipes'], queryFn: () => fetchApi('/recipes') });
  const { data: batches = [] } = useQuery<Batch[]>({
    queryKey: ['production-batches', branchId],
    queryFn: () => fetchApi(`/production-batches?branch_id=${branchId}`),
    enabled: Boolean(branchId),
  });
  const productionRecipes = useMemo(() => recipes.filter((recipe) => recipe.recipe_type === 'production'), [recipes]);
  const elaboratedItems = items.filter((item) => item.item_type === 'elaborated');
  const selectedOutput = items.find((item) => item.id === recipeForm.output_item_id);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['recipes'] }),
      queryClient.invalidateQueries({ queryKey: ['production-batches'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory-costs'] }),
    ]);
  };
  const recipeMutation = useMutation({
    mutationFn: () => fetchApi('/production-recipes', { method: 'POST', body: JSON.stringify({
      ...recipeForm,
      branch_id: branchId || null,
      yield_unit_id: selectedOutput?.base_unit_id || '',
    }) }),
    onSuccess: async () => { setRecipeOpen(false); setError(''); await refresh(); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible guardar la subreceta.'),
  });
  const batchMutation = useMutation({
    mutationFn: () => fetchApi('/production-batches', { method: 'POST', body: JSON.stringify({ branch_id: branchId, ...batchForm }) }),
    onSuccess: async () => { setBatchOpen(false); setError(''); await refresh(); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible crear el lote.'),
  });

  const confirmBatch = async (batchId: string) => {
    const storageKey = `production_confirmation_${batchId}`;
    const key = localStorage.getItem(storageKey) || `production:${batchId}:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, key);
    try {
      await fetchApi(`/production-batches/${batchId}/confirm`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: '{}' });
      localStorage.removeItem(storageKey);
      setError('');
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible confirmar el lote.');
    }
  };
  const updateComponent = (index: number, field: keyof RecipeComponent, value: string) => setRecipeForm((current) => ({
    ...current,
    components: current.components.map((component, componentIndex) => componentIndex === index ? { ...component, [field]: value } : component),
  }));

  return <>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
      <div><h1 className="premium-header-title">Producción y elaborados</h1><p className="premium-header-subtitle">Versiona subrecetas y transforma insumos en lotes trazables.</p></div>
      <div style={{ display: 'flex', gap: 8 }}><Button variant="secondary" onClick={() => setRecipeOpen(true)}><Plus size={16} /> Nueva subreceta</Button><Button variant="primary" onClick={() => setBatchOpen(true)} disabled={!branchId || productionRecipes.length === 0}><Factory size={16} /> Nuevo lote</Button></div>
    </div>
    {!branchId && <div role="alert" style={{ color: '#b91c1c', marginBottom: 16 }}>Selecciona o asigna una sucursal para gestionar producción.</div>}
    {error && <div role="alert" style={{ color: '#b91c1c', marginBottom: 16 }}>{error}</div>}
    <div className="premium-card" style={{ overflowX: 'auto', marginBottom: 24 }}>
      <h2 style={{ padding: '16px 20px 0' }}>Recetas de producción activas</h2>
      <table className="premium-table"><thead><tr><th>SKU</th><th>Elaborado</th><th>Versión</th><th>Rendimiento</th></tr></thead><tbody>{productionRecipes.map((recipe) => <tr key={recipe.id}><td>{recipe.output_item_sku}</td><td>{recipe.output_item_name}</td><td>v{recipe.version}</td><td>{Number(recipe.yield_quantity)} {recipe.yield_unit_code}</td></tr>)}</tbody></table>
    </div>
    <div className="premium-card" style={{ overflowX: 'auto' }}>
      <h2 style={{ padding: '16px 20px 0' }}>Lotes</h2>
      <table className="premium-table"><thead><tr><th>Lote</th><th>Elaborado</th><th>Planeado</th><th>Real</th><th>Costo unitario</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{batches.map((batch) => { const recipe = productionRecipes.find((item) => item.id === batch.recipe_id); return <tr key={batch.id}><td>{batch.lot_code}</td><td>{recipe?.output_item_name || batch.recipe_id}</td><td>{Number(batch.planned_quantity)}</td><td>{Number(batch.actual_quantity)}</td><td>${Number(batch.unit_cost).toFixed(4)}</td><td><Badge variant={batch.status === 'confirmed' ? 'success' : 'info'}>{batch.status}</Badge></td><td>{batch.status === 'draft' && <Button variant="primary" onClick={() => void confirmBatch(batch.id)}><CheckCircle2 size={15} /> Confirmar</Button>}</td></tr>; })}</tbody></table>
    </div>

    <Modal isOpen={recipeOpen} onClose={() => setRecipeOpen(false)} title="Nueva receta de producción">
      <div style={{ display: 'grid', gap: 12 }}>
        <label>Elaborado<select value={recipeForm.output_item_id} onChange={(event) => setRecipeForm({ ...recipeForm, output_item_id: event.target.value })} style={{ width: '100%', padding: 10 }}><option value="">Selecciona</option>{elaboratedItems.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>)}</select></label>
        <Field label="Rendimiento" value={recipeForm.yield_quantity} setValue={(yield_quantity) => setRecipeForm({ ...recipeForm, yield_quantity })} />
        <strong>Componentes</strong>
        {recipeForm.components.map((component, index) => <div key={index} style={{ display: 'grid', gridTemplateColumns: '1fr 90px 80px 32px', gap: 8 }}>
          <select value={component.item_id} onChange={(event) => updateComponent(index, 'item_id', event.target.value)} style={{ padding: 8 }}><option value="">Insumo</option>{items.filter((item) => item.id !== recipeForm.output_item_id).map((item) => <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>)}</select>
          <Input value={component.net_quantity} onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateComponent(index, 'net_quantity', event.target.value)} aria-label="Cantidad neta" />
          <Input value={component.waste_percent} onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateComponent(index, 'waste_percent', event.target.value)} aria-label="Merma porcentual" />
          <button type="button" onClick={() => setRecipeForm({ ...recipeForm, components: recipeForm.components.filter((_, itemIndex) => itemIndex !== index) })} style={{ border: 0, background: 'none' }}><Trash2 size={16} /></button>
        </div>)}
        <Button variant="secondary" onClick={() => setRecipeForm({ ...recipeForm, components: [...recipeForm.components, { item_id: '', net_quantity: '1', waste_percent: '0' }] })}><Plus size={15} /> Agregar componente</Button>
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}><Button variant="primary" onClick={() => recipeMutation.mutate()} disabled={recipeMutation.isPending}>Guardar versión</Button></div>
    </Modal>

    <Modal isOpen={batchOpen} onClose={() => setBatchOpen(false)} title="Nuevo lote de producción">
      <div style={{ display: 'grid', gap: 12 }}>
        <label>Receta<select value={batchForm.recipe_id} onChange={(event) => { const selected = productionRecipes.find((recipe) => recipe.id === event.target.value); setBatchForm({ ...batchForm, recipe_id: event.target.value, planned_quantity: String(selected?.yield_quantity || 1), actual_quantity: String(selected?.yield_quantity || 1) }); }} style={{ width: '100%', padding: 10 }}><option value="">Selecciona</option>{productionRecipes.map((recipe) => <option key={recipe.id} value={recipe.id}>{recipe.output_item_name} · v{recipe.version}</option>)}</select></label>
        <Field label="Código de lote" value={batchForm.lot_code} setValue={(lot_code) => setBatchForm({ ...batchForm, lot_code })} />
        <Field label="Cantidad planeada" value={batchForm.planned_quantity} setValue={(planned_quantity) => setBatchForm({ ...batchForm, planned_quantity })} />
        <Field label="Cantidad real producida" value={batchForm.actual_quantity} setValue={(actual_quantity) => setBatchForm({ ...batchForm, actual_quantity })} />
        <Field label="Merma real" value={batchForm.actual_waste_quantity} setValue={(actual_waste_quantity) => setBatchForm({ ...batchForm, actual_waste_quantity })} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}><Button variant="primary" onClick={() => batchMutation.mutate()} disabled={batchMutation.isPending}>Guardar borrador</Button></div>
    </Modal>
  </>;
};

const Field = ({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) => <label style={{ display: 'grid', gap: 4 }}><span>{label}</span><Input value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValue(event.target.value)} /></label>;

export default ProductionList;
