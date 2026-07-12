import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Trash2, Plus } from 'lucide-react';

interface RecipeComponent {
  item_id: string;
  item_name?: string;
  item_sku?: string;
  unit_code?: string;
  unit_id?: string;
  net_quantity: number;
  waste_rate?: number;
  waste_percent?: number;
  gross_quantity?: number;
}

interface Recipe {
  id?: string;
  version?: number;
  yield_quantity: number;
  yield_unit_id: string;
  components: RecipeComponent[];
  latest_cost?: {
    cost_before_waste: number;
    waste_cost: number;
    total_cost: number;
    cost_per_yield_unit: number;
  } | null;
}

interface Item {
  id: string;
  name: string;
  unit_code?: string;
}

interface Props {
  productId: string;
  productName: string;
  isOpen: boolean;
  onClose: () => void;
}

export const RecipeManager = ({ productId, productName, isOpen, onClose }: Props) => {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<Recipe>({ yield_quantity: 1, yield_unit_id: '', components: [] });

  const { data: recipe, isLoading } = useQuery<Recipe>({
    queryKey: ['products', productId, 'recipe'],
    queryFn: () => fetchApi(`/products/${productId}/recipe`),
    enabled: isOpen && !!productId,
  });

  const { data: items } = useQuery<Item[]>({
    queryKey: ['inventory', 'items'],
    queryFn: () => fetchApi('/inventory/items'),
    enabled: isOpen,
  });

  useEffect(() => {
    if (recipe) {
      setFormData({
        yield_quantity: recipe.yield_quantity || 1,
        yield_unit_id: recipe.yield_unit_id || '',
        components: (recipe.components || []).map((component) => ({
          ...component,
          net_quantity: Number(component.net_quantity ?? 0),
          waste_percent: Number(component.waste_percent ?? Number(component.waste_rate || 0) * 100),
          gross_quantity: Number(component.gross_quantity ?? 0),
        }))
      });
    } else {
      setFormData({ yield_quantity: 1, yield_unit_id: '', components: [] });
    }
  }, [recipe]);

  const saveMutation = useMutation({
    mutationFn: (data: Recipe) => {
      return fetchApi(`/products/${productId}/recipe`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products', productId, 'recipe'] });
      onClose();
    }
  });

  const addComponent = () => {
    setFormData(prev => ({
      ...prev,
      components: [...prev.components, { item_id: '', net_quantity: 1, waste_percent: 0 }]
    }));
  };

  const updateComponent = (index: number, field: keyof RecipeComponent, value: any) => {
    const newComps = [...formData.components];
    newComps[index] = { ...newComps[index], [field]: value };
    setFormData(prev => ({ ...prev, components: newComps }));
  };

  const removeComponent = (index: number) => {
    const newComps = formData.components.filter((_, i) => i !== index);
    setFormData(prev => ({ ...prev, components: newComps }));
  };

  if (!isOpen) return null;

  const grossQuantity = (component: RecipeComponent) => {
    const waste = Number(component.waste_percent || 0) / 100;
    return waste >= 1 ? 0 : Number(component.net_quantity || 0) / (1 - waste);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Receta: ${productName}`}>
      {isLoading ? (
        <div style={{ padding: 20 }}>Cargando receta...</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ fontWeight: 600 }}>Componentes (Insumos)</h4>
            <Button variant="secondary" onClick={addComponent} size="sm" style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <Plus size={14} /> Agregar
            </Button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: '300px', overflowY: 'auto' }}>
            {formData.components.length === 0 ? (
              <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>No hay componentes en esta receta.</p>
            ) : (
              formData.components.map((comp, idx) => (
                <div key={idx} style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 1fr) 110px 100px 120px 36px', gap: 8, alignItems: 'end' }}>
                  <div style={{ flex: 1 }}>
                    <select 
                      value={comp.item_id}
                      onChange={e => updateComponent(idx, 'item_id', e.target.value)}
                      style={{ width: '100%', padding: '8px', borderRadius: 4, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)' }}
                    >
                      <option value="">Selecciona un insumo</option>
                      {items?.map(it => (
                        <option key={it.id} value={it.id}>{it.name} ({it.unit_code})</option>
                      ))}
                    </select>
                  </div>
                  <label style={{ display: 'grid', gap: 4, fontSize: 12 }}>Cantidad neta
                    <Input 
                      type="number" 
                      min={0.000001}
                      step="any"
                      value={comp.net_quantity}
                      onChange={(e: any) => updateComponent(idx, 'net_quantity', Number(e.target.value) || 0)}
                    />
                  </label>
                  <label style={{ display: 'grid', gap: 4, fontSize: 12 }}>Merma %
                    <Input type="number" min={0} max={99.999} step="any" value={comp.waste_percent || 0} onChange={(e: any) => updateComponent(idx, 'waste_percent', Number(e.target.value) || 0)} />
                  </label>
                  <div style={{ fontSize: 12, paddingBottom: 10 }}><strong>{grossQuantity(comp).toFixed(4)}</strong> {comp.unit_code}<br /><span style={{ color: 'var(--color-text-muted)' }}>cantidad bruta</span></div>
                  <button onClick={() => removeComponent(idx)} style={{ color: 'var(--color-red)', background: 'none', border: 'none', cursor: 'pointer', padding: 8 }}>
                    <Trash2 size={16} />
                  </button>
                </div>
              ))
            )}
          </div>

          {recipe?.latest_cost && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, padding: 12, borderRadius: 8, background: 'var(--color-bg-subtle)' }}>
              <Cost label="Costo neto" value={recipe.latest_cost.cost_before_waste} />
              <Cost label="Costo de merma" value={recipe.latest_cost.waste_cost} />
              <Cost label="Costo total" value={recipe.latest_cost.total_cost} />
              <Cost label="Costo por rendimiento" value={recipe.latest_cost.cost_per_yield_unit} />
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 16 }}>
            <Button variant="secondary" onClick={onClose}>Cancelar</Button>
            <Button variant="primary" onClick={() => saveMutation.mutate(formData)} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Guardando...' : 'Guardar'}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};

const Cost = ({ label, value }: { label: string; value: number }) => (
  <div><span style={{ display: 'block', fontSize: 12, color: 'var(--color-text-muted)' }}>{label}</span><strong>${Number(value).toFixed(4)}</strong></div>
);
