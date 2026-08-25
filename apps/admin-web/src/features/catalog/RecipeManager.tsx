import React, { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Trash2, Sparkles, ChefHat } from 'lucide-react';
import { RecipeAiAssistantModal } from './RecipeAiAssistantModal';
import '../../premium-catalogs.css';

export interface RecipeWorkspaceItem {
  id: string;
  name: string;
  unit_id: string;
  unit_code: string;
  last_unit_cost?: number;
  average_unit_cost?: number;
}

interface Component {
  item_id: string;
  unit_id: string;
  net_quantity: string;
  waste_rate: string;
  unit_code?: string;
  gross_quantity?: string;
}

interface Recipe {
  id?: string;
  yield_quantity: string;
  yield_unit_id: string;
  components: Component[];
  latest_cost?: Record<string, string | number> | null;
}

interface Props {
  productId: string;
  productName: string;
  isOpen: boolean;
  onClose: () => void;
  branchId?: string | null;
  items?: RecipeWorkspaceItem[];
}

export const RecipeManager = ({ productId, productName, isOpen, onClose, branchId = null, items = [] }: Props) => {
  const queryClient = useQueryClient();
  const intentKey = useRef(`recipe-${productId}-${crypto.randomUUID()}`);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [formData, setFormData] = useState<Recipe>({ yield_quantity: '1', yield_unit_id: items[0]?.unit_id || '', components: [] });
  const scopeQuery = branchId === null ? '' : `?branch_id=${encodeURIComponent(branchId)}`;

  const { data: recipe, isLoading } = useQuery<Recipe>({
    queryKey: ['recipes', productId, branchId],
    queryFn: () => fetchApi<Recipe>(`/products/${productId}/recipe${scopeQuery}`),
    enabled: isOpen,
  });

  useEffect(() => {
    if (recipe?.id) {
      setFormData({
        yield_quantity: String(recipe.yield_quantity),
        yield_unit_id: recipe.yield_unit_id || items[0]?.unit_id || '',
        components: (recipe.components || []).map((c) => ({
          item_id: c.item_id,
          unit_id: c.unit_id || (items.find((it) => it.id === c.item_id)?.unit_id || items[0]?.unit_id || ''),
          net_quantity: String(c.net_quantity),
          waste_rate: String(c.waste_rate ?? '0'),
        })),
      });
    } else {
      setFormData({ yield_quantity: '1', yield_unit_id: items[0]?.unit_id || '', components: [] });
    }
    setError('');
    setSuccessMsg('');
  }, [recipe, items]);

  const save = useMutation({
    mutationFn: () => {
      const cleanComponents = formData.components
        .filter((c) => c.item_id && parseFloat(c.net_quantity) > 0)
        .map((c) => {
          const matched = items.find((it) => it.id === c.item_id);
          const rawWaste = parseFloat(c.waste_rate) || 0;
          const normalizedWaste = rawWaste >= 1 ? rawWaste / 100 : rawWaste;
          return {
            item_id: c.item_id,
            unit_id: c.unit_id || matched?.unit_id || (items[0]?.unit_id || ''),
            net_quantity: String(c.net_quantity),
            waste_rate: String(normalizedWaste),
          };
        });

      if (cleanComponents.length === 0) {
        throw new Error('Debes agregar al menos un ingrediente válido con cantidad mayor a cero.');
      }

      const defaultUnit = items[0]?.unit_id || '';
      const payload = {
        branch_id: branchId && branchId.trim() !== '' ? branchId : null,
        expected_active_recipe_id: recipe?.id || null,
        yield_quantity: formData.yield_quantity || '1',
        yield_unit_id: formData.yield_unit_id || defaultUnit,
        components: cleanComponents,
      };

      return fetchApi<Recipe>(`/products/${productId}/recipe`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': intentKey.current },
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (saved: Recipe) => {
      queryClient.invalidateQueries({ queryKey: ['recipes', productId, branchId] });
      queryClient.invalidateQueries({ queryKey: ['recipes-workspace'] });
      intentKey.current = `recipe-${productId}-${crypto.randomUUID()}`;
      setSuccessMsg('¡Receta guardada exitosamente!');
      setTimeout(() => {
        onClose();
      }, 700);
    },
    onError: (cause: any) => {
      let message = '';
      if (cause?.detail && Array.isArray(cause.detail)) {
        message = cause.detail.map((d: any) => `${d.loc ? d.loc.join(' → ') : 'Campo'}: ${d.msg}`).join(' | ');
      } else if (cause?.message) {
        message = cause.message;
      } else if (typeof cause === 'string') {
        message = cause;
      } else {
        message = 'No fue posible guardar la receta.';
      }
      setError(
        message.includes('recipe_version_conflict')
          ? 'La receta cambió en otra sesión. Cierra y vuelve a abrir para ver la última versión.'
          : message.includes('idempotency')
          ? 'El reintento no coincide con la intención original.'
          : message
      );
    },
  });

  const add = () => {
    setFormData((old) => ({
      ...old,
      components: [
        ...old.components,
        { item_id: '', unit_id: items[0]?.unit_id || '', net_quantity: '1', waste_rate: '0' },
      ],
    }));
  };

  const update = (index: number, key: keyof Component, value: string) => {
    setFormData((old) => ({
      ...old,
      components: old.components.map((component, i) => (i === index ? { ...component, [key]: value } : component)),
    }));
  };

  const handleApplyFromAi = (
    newComponents: Array<{ item_id: string; unit_id: string; net_quantity: string; waste_rate: string }>
  ) => {
    const merged: Record<string, { item_id: string; unit_id: string; net_quantity: number; waste_rate: number }> = {};
    for (const c of newComponents) {
      if (!c.item_id) continue;
      const matched = items.find((it) => it.id === c.item_id);
      const unit_id = c.unit_id || matched?.unit_id || items[0]?.unit_id || '';
      const qty = parseFloat(c.net_quantity) || 0;
      const rawWaste = parseFloat(c.waste_rate) || 0;
      const waste = rawWaste >= 1 ? rawWaste / 100 : rawWaste;

      if (merged[c.item_id]) {
        merged[c.item_id].net_quantity += qty;
        merged[c.item_id].waste_rate = Math.max(merged[c.item_id].waste_rate, waste);
      } else {
        merged[c.item_id] = { item_id: c.item_id, unit_id, net_quantity: qty, waste_rate: waste };
      }
    }

    setFormData((old) => ({
      ...old,
      components: Object.values(merged).map((c) => ({
        item_id: c.item_id,
        unit_id: c.unit_id,
        net_quantity: String(c.net_quantity),
        waste_rate: String(c.waste_rate * 100),
      })),
    }));
  };

  // Cálculo en vivo del costo teórico
  const liveTotalCost = formData.components.reduce((acc, comp) => {
    const it = items.find((entry) => entry.id === comp.item_id);
    const unitCost = Number(it?.last_unit_cost || it?.average_unit_cost || 0);
    const qty = parseFloat(comp.net_quantity) || 0;
    const rawWaste = parseFloat(comp.waste_rate) || 0;
    const waste = rawWaste >= 1 ? rawWaste / 100 : rawWaste;
    const gross = waste > 0 && waste < 1 ? qty / (1 - waste) : qty;
    return acc + gross * unitCost;
  }, 0);

  const yieldQty = parseFloat(formData.yield_quantity) || 1;
  const costPerPortion = liveTotalCost / yieldQty;

  if (!isOpen) return null;

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title={`Receta: ${productName}`} size="xl" maxWidth="940px">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando componentes de receta…</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {error && (
              <div role="alert" style={{ padding: 12, borderRadius: 8, background: 'rgba(239, 68, 68, 0.1)', color: 'var(--color-red)', fontWeight: 500 }}>
                ⚠️ {error}
              </div>
            )}
            {successMsg && (
              <div role="status" style={{ padding: 12, borderRadius: 8, background: 'rgba(34, 197, 94, 0.1)', color: 'var(--color-green)', fontWeight: 600 }}>
                ✅ {successMsg}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, paddingBottom: 12, borderBottom: '1px solid var(--color-border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <ChefHat size={20} style={{ color: '#16a34a' }} />
                <label style={{ fontWeight: 600, fontSize: '0.9375rem' }}>
                  Rendimiento (Porciones preparadas):
                </label>
                <Input
                  type="number"
                  min="1"
                  step="any"
                  value={formData.yield_quantity}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, yield_quantity: e.target.value })}
                  style={{ width: 85 }}
                />
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <Button
                  variant="secondary"
                  onClick={() => setIsAiModalOpen(true)}
                  size="sm"
                  style={{ color: '#047857', borderColor: '#10b981', background: '#ecfdf5', fontWeight: 600 }}
                >
                  <Sparkles size={15} style={{ marginRight: 6 }} /> Asistente IA (Pegar Receta)
                </Button>
                <Button variant="secondary" onClick={add} size="sm" style={{ fontWeight: 600 }}>
                  <Plus size={15} style={{ marginRight: 6 }} /> Agregar Ingrediente
                </Button>
              </div>
            </div>

            {formData.components.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', border: '1px dashed var(--color-border)', borderRadius: 12 }}>
                <p style={{ color: 'var(--color-text-muted)', marginBottom: 12 }}>
                  Esta receta aún no tiene ingredientes o empaques registrados.
                </p>
                <Button variant="secondary" onClick={add} size="sm">
                  <Plus size={14} style={{ marginRight: 4 }} /> Agregar primer insumo manual
                </Button>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="premium-table" style={{ margin: 0 }}>
                  <thead>
                    <tr>
                      <th style={{ minWidth: 260 }}>Insumo / Ingrediente</th>
                      <th style={{ width: 140, textAlign: 'right' }}>Cantidad Neta</th>
                      <th style={{ width: 130, textAlign: 'right' }}>
                        <span title="Porcentaje de desperdicio estimado al limpiar o preparar el insumo (0% = 0)">
                          Merma (%)
                        </span>
                      </th>
                      <th style={{ width: 130, textAlign: 'right' }}>Costo Teórico</th>
                      <th style={{ width: 60, textAlign: 'center' }}>Quitar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {formData.components.map((component, index) => {
                      const itemObj = items.find((entry) => entry.id === component.item_id);
                      const unitCost = Number(itemObj?.last_unit_cost || itemObj?.average_unit_cost || 0);
                      const qty = parseFloat(component.net_quantity) || 0;
                      const rawWaste = parseFloat(component.waste_rate) || 0;
                      const waste = rawWaste >= 1 ? rawWaste / 100 : rawWaste;
                      const gross = waste > 0 && waste < 1 ? qty / (1 - waste) : qty;
                      const subtotal = gross * unitCost;

                      return (
                        <tr key={index}>
                          <td>
                            <select
                              value={component.item_id}
                              onChange={(e) => {
                                const item = items.find((entry) => entry.id === e.target.value);
                                update(index, 'item_id', e.target.value);
                                update(index, 'unit_id', item?.unit_id || items[0]?.unit_id || '');
                              }}
                              style={{
                                width: '100%',
                                padding: '8px 10px',
                                borderRadius: 8,
                                border: '1px solid var(--color-border)',
                                background: 'var(--color-surface)',
                                color: 'var(--color-text)',
                                fontWeight: 500,
                              }}
                            >
                              <option value="">Selecciona un insumo...</option>
                              {items.map((item) => (
                                <option key={item.id} value={item.id}>
                                  {item.name} · {item.unit_code} {item.last_unit_cost ? `($${Number(item.last_unit_cost).toFixed(2)}/${item.unit_code})` : ''}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
                              <Input
                                type="number"
                                min="0.000001"
                                step="any"
                                value={component.net_quantity}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => update(index, 'net_quantity', e.target.value)}
                                placeholder="0.000"
                                style={{ width: 85, textAlign: 'right' }}
                              />
                              <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', minWidth: 32 }}>
                                {itemObj?.unit_code || ''}
                              </span>
                            </div>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                              <Input
                                type="number"
                                min="0"
                                max="0.999999"
                                step="any"
                                value={component.waste_rate}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => update(index, 'waste_rate', e.target.value)}
                                placeholder="0"
                                style={{ width: 65, textAlign: 'right' }}
                              />
                              <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>%</span>
                            </div>
                          </td>
                          <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--color-green)' }}>
                            ${subtotal.toFixed(2)}
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <button
                              aria-label="Quitar insumo"
                              className="premium-action-btn delete"
                              onClick={() => setFormData((old) => ({ ...old, components: old.components.filter((_, i) => i !== index) }))}
                              title="Quitar de la receta"
                              style={{ display: 'inline-flex', padding: 6 }}
                            >
                              <Trash2 size={16} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 18px', background: 'rgba(34, 197, 94, 0.08)', borderRadius: 10, border: '1px solid rgba(34, 197, 94, 0.2)' }}>
              <div>
                <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Costo Total Estimado:</span>
                <span style={{ marginLeft: 8, fontSize: '1.125rem', fontWeight: 700, color: 'var(--color-green)' }}>
                  ${liveTotalCost.toFixed(2)} MXN
                </span>
                <span style={{ marginLeft: 16, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                  (${costPerPortion.toFixed(2)} por porción)
                </span>
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                <Button variant="secondary" onClick={onClose}>Cancelar</Button>
                <Button
                  variant="primary"
                  disabled={save.isPending || formData.components.length === 0}
                  onClick={() => save.mutate()}
                >
                  {save.isPending ? 'Guardando Receta…' : 'Guardar Receta'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {isAiModalOpen && (
        <RecipeAiAssistantModal
          isOpen={isAiModalOpen}
          onClose={() => setIsAiModalOpen(false)}
          productId={productId}
          productName={productName}
          items={items}
          onApplyIngredients={handleApplyFromAi}
        />
      )}
    </>
  );
};