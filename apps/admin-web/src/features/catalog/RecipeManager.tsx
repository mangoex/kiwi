import React, { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Trash2 } from 'lucide-react';

export interface RecipeWorkspaceItem { id: string; name: string; unit_id: string; unit_code: string; }
interface Component { item_id: string; unit_id: string; net_quantity: string; waste_rate: string; unit_code?: string; gross_quantity?: string; }
interface Recipe { id?: string; yield_quantity: string; yield_unit_id: string; components: Component[]; latest_cost?: Record<string, string | number> | null; }
interface Props { productId: string; productName: string; isOpen: boolean; onClose: () => void; branchId?: string | null; items?: RecipeWorkspaceItem[]; }

/** Recipe-only editor: its inputs arrive from /recipes/workspace, never catalog or inventory routes. */
export const RecipeManager = ({ productId, productName, isOpen, onClose, branchId = null, items = [] }: Props) => {
  const queryClient = useQueryClient();
  const intentKey = useRef(`recipe-${productId}-${crypto.randomUUID()}`);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState<Recipe>({ yield_quantity: '1', yield_unit_id: items[0]?.unit_id || '', components: [] });
  const scopeQuery = branchId === null ? '' : `?branch_id=${encodeURIComponent(branchId)}`;
  const { data: recipe, isLoading } = useQuery<Recipe>({
    queryKey: ['recipes', productId, branchId], queryFn: () => fetchApi<Recipe>(`/products/${productId}/recipe${scopeQuery}`), enabled: isOpen,
  });
  useEffect(() => {
    if (recipe?.id) setFormData({ yield_quantity: String(recipe.yield_quantity), yield_unit_id: recipe.yield_unit_id, components: recipe.components.map((c) => ({ ...c, net_quantity: String(c.net_quantity), waste_rate: String(c.waste_rate ?? '0') })) });
    else setFormData({ yield_quantity: '1', yield_unit_id: items[0]?.unit_id || '', components: [] });
    setError('');
  }, [recipe, items]);
  const save = useMutation({
    mutationFn: () => fetchApi<Recipe>(`/products/${productId}/recipe`, { method: 'PUT', headers: { 'Idempotency-Key': intentKey.current }, body: JSON.stringify({ branch_id: branchId, expected_active_recipe_id: recipe?.id || null, ...formData }) }),
    onSuccess: (saved: Recipe) => { queryClient.setQueryData(['recipes', productId, branchId], saved); intentKey.current = `recipe-${productId}-${crypto.randomUUID()}`; onClose(); },
    onError: (cause: unknown) => { const message = cause instanceof Error ? cause.message : ''; setError(message.includes('recipe_version_conflict') ? 'La receta cambió en otra sesión. Revísala e inténtalo de nuevo.' : message.includes('idempotency') ? 'El reintento no coincide con la intención original.' : 'No fue posible guardar la receta.'); },
  });
  const add = () => setFormData((old) => ({ ...old, components: [...old.components, { item_id: '', unit_id: '', net_quantity: '1', waste_rate: '0' }] }));
  const update = (index: number, key: keyof Component, value: string) => setFormData((old) => ({ ...old, components: old.components.map((component, i) => i === index ? { ...component, [key]: value } : component) }));
  if (!isOpen) return null;
  return <Modal isOpen={isOpen} onClose={onClose} title={`Receta: ${productName}`}>
    {isLoading ? <div style={{ padding: 20 }}>Cargando receta…</div> : <div style={{ display: 'grid', gap: 14 }}>
      {error && <div role="alert" style={{ color: 'var(--color-red)' }}>{error}</div>}
      <label>Rendimiento <Input value={formData.yield_quantity} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, yield_quantity: e.target.value })} /></label>
      <Button variant="secondary" onClick={add} size="sm"><Plus size={14} /> Agregar insumo</Button>
      {formData.components.map((component, index) => <div key={index} style={{ display: 'grid', gridTemplateColumns: '1fr 110px 100px 32px', gap: 8 }}>
        <select value={component.item_id} onChange={(e) => { const item = items.find((entry) => entry.id === e.target.value); update(index, 'item_id', e.target.value); update(index, 'unit_id', item?.unit_id || ''); }}><option value="">Selecciona un insumo</option>{items.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>)}</select>
        <Input type="number" min="0.000001" step="any" value={component.net_quantity} onChange={(e: React.ChangeEvent<HTMLInputElement>) => update(index, 'net_quantity', e.target.value)} />
        <Input type="number" min="0" max="0.999999" step="any" value={component.waste_rate} onChange={(e: React.ChangeEvent<HTMLInputElement>) => update(index, 'waste_rate', e.target.value)} />
        <button aria-label="Quitar insumo" onClick={() => setFormData((old) => ({ ...old, components: old.components.filter((_, i) => i !== index) }))}><Trash2 size={16} /></button>
      </div>)}
      {recipe?.latest_cost && <p>Costo autorizado: {String(recipe.latest_cost.total_cost ?? '—')}</p>}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button variant="primary" disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Guardando…' : 'Guardar receta'}</Button></div>
    </div>}
  </Modal>;
};
