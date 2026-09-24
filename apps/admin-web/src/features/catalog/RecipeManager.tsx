import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Trash2, Sparkles, ChefHat } from 'lucide-react';
import { RecipeAiAssistantModal } from './RecipeAiAssistantModal';
import { percentToRate, rateToPercent } from './recipeDecimal';
export { percentToRate, rateToPercent } from './recipeDecimal';
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
  waste_percent?: string;
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
  requestedRecipeId?: string | null;
  salePriceCents?: number | null;
}

export const RecipeManager = ({
  productId,
  productName,
  isOpen,
  onClose,
  branchId = null,
  items = [],
  requestedRecipeId = null,
  salePriceCents = null,
}: Props) => {
  const queryClient = useQueryClient();
  const defaultYieldUnitId = items.find((item) => item.unit_code.toLocaleUpperCase('es-MX') === 'PZA')?.unit_id || '';
  const intentKey = useRef(`recipe-${productId}-${crypto.randomUUID()}`);
  const confirmedRecipeIdRef = useRef<string | null>(null);
  const loadedRecipeKeyRef = useRef<string | null>(null);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [ingredientFilter, setIngredientFilter] = useState('');
  const [hasVersionConflict, setHasVersionConflict] = useState(false);
  const [formData, setFormData] = useState<Recipe>({ yield_quantity: '1', yield_unit_id: defaultYieldUnitId, components: [] });
  const scopeQuery = branchId === null ? '' : `?branch_id=${encodeURIComponent(branchId)}`;

  const {
    data: recipe,
    isLoading,
    isError: recipeLoadFailed,
    refetch: refetchRecipe,
  } = useQuery<Recipe>({
    queryKey: ['recipes', productId, branchId],
    queryFn: () => fetchApi<Recipe>(`/products/${productId}/recipe${scopeQuery}`),
    enabled: isOpen,
  });

  useEffect(() => {
    const recipeKey = `${productId}:${branchId ?? 'corporate'}:${recipe?.id ?? 'empty'}`;
    if (loadedRecipeKeyRef.current === recipeKey) return;
    loadedRecipeKeyRef.current = recipeKey;
    if (recipe?.id) {
      setFormData({
        yield_quantity: String(recipe.yield_quantity),
        yield_unit_id: recipe.yield_unit_id || defaultYieldUnitId,
        components: (recipe.components || []).map((c) => ({
          item_id: c.item_id,
          unit_id: c.unit_id || (items.find((it) => it.id === c.item_id)?.unit_id || items[0]?.unit_id || ''),
          net_quantity: String(c.net_quantity),
          waste_rate: String(c.waste_rate ?? '0'),
          waste_percent: rateToPercent(String(c.waste_rate ?? '0')),
          gross_quantity: c.gross_quantity == null ? undefined : String(c.gross_quantity),
        })),
      });
    } else {
      setFormData({ yield_quantity: '1', yield_unit_id: defaultYieldUnitId, components: [] });
    }
    const isConfirmedRefresh = Boolean(recipe?.id && recipe.id === confirmedRecipeIdRef.current);
    if (!isConfirmedRefresh) {
      setError('');
      setSuccessMsg('');
    }
    setHasVersionConflict(false);
    setIngredientFilter('');
  }, [branchId, defaultYieldUnitId, items, productId, recipe]);

  const save = useMutation({
    mutationFn: () => {
      const invalidWaste = formData.components.some((component) => {
        const visiblePercent = component.waste_percent?.trim() || '';
        if (!component.item_id) return false;
        return !visiblePercent
          || !component.waste_rate
          || (component.waste_rate !== '0' && !component.waste_rate.startsWith('0.'));
      });
      if (invalidWaste) {
        throw new Error('La merma debe ser un porcentaje entre 0 y 99.9999. Puedes usar punto o coma decimal.');
      }
      const cleanComponents = formData.components
        .filter((c) => c.item_id && parseFloat(c.net_quantity) > 0)
        .map((c) => {
          const matched = items.find((it) => it.id === c.item_id);
          return {
            item_id: c.item_id,
            unit_id: c.unit_id || matched?.unit_id || (items[0]?.unit_id || ''),
            net_quantity: String(c.net_quantity),
            waste_rate: String(c.waste_rate || '0'),
          };
        });

      if (cleanComponents.length === 0) {
        throw new Error('Debes agregar al menos un ingrediente válido con cantidad mayor a cero.');
      }

      const payload = {
        branch_id: branchId && branchId.trim() !== '' ? branchId : null,
        expected_active_recipe_id: recipe?.id || null,
        yield_quantity: formData.yield_quantity || '1',
        yield_unit_id: formData.yield_unit_id || '',
        components: cleanComponents,
      };

      return fetchApi<Recipe>(`/products/${productId}/recipe`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': intentKey.current },
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (saved: Recipe) => {
      confirmedRecipeIdRef.current = saved.id || null;
      queryClient.setQueryData(['recipes', productId, branchId], saved);
      queryClient.invalidateQueries({ queryKey: ['recipes', productId, branchId] });
      queryClient.invalidateQueries({ queryKey: ['product-recipe', productId, branchId] });
      queryClient.invalidateQueries({ queryKey: ['recipes-workspace'] });
      intentKey.current = `recipe-${productId}-${crypto.randomUUID()}`;
      setHasVersionConflict(false);
      setSuccessMsg('Receta guardada y versionada. Puedes revisar el resultado o volver al producto.');
    },
    onError: (cause: any) => {
      const errorCode = typeof cause?.code === 'string' ? cause.code : '';
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
      const isVersionConflict = errorCode === 'recipe_version_conflict'
        || message.includes('recipe_version_conflict');
      const isIdempotencyConflict = errorCode.includes('idempotency')
        || message.includes('idempotency');
      setError(
        isVersionConflict
          ? 'La receta cambió en otra sesión. Cierra y vuelve a abrir para ver la última versión.'
          : isIdempotencyConflict
          ? 'El reintento no coincide con la intención original.'
          : message
      );
      setHasVersionConflict(isVersionConflict);
    },
  });

  const prepareRecipeEdit = () => {
    if (error && !hasVersionConflict) {
      intentKey.current = `recipe-${productId}-${crypto.randomUUID()}`;
      setError('');
    }
    if (successMsg) setSuccessMsg('');
  };

  const add = () => {
    prepareRecipeEdit();
    setFormData((old) => ({
      ...old,
      components: [
        ...old.components,
        { item_id: '', unit_id: items[0]?.unit_id || '', net_quantity: '1', waste_rate: '0', waste_percent: '0' },
      ],
    }));
  };

  const update = (index: number, key: keyof Component, value: string) => {
    prepareRecipeEdit();
    setFormData((old) => ({
      ...old,
      components: old.components.map((component, i) => (i === index ? { ...component, [key]: value } : component)),
    }));
  };

  const updateWastePercent = (index: number, value: string) => {
    prepareRecipeEdit();
    const fraction = percentToRate(value);
    setFormData((old) => ({
      ...old,
      components: old.components.map((component, i) => (
        i === index ? { ...component, waste_percent: value, waste_rate: fraction } : component
      )),
    }));
  };

  const handleApplyFromAi = (
    newComponents: Array<{ item_id: string; unit_id: string; net_quantity: string; waste_rate: string }>
  ) => {
    prepareRecipeEdit();
    setFormData((old) => ({
      ...old,
      components: newComponents.filter((c) => c.item_id).map((c) => ({
        item_id: c.item_id,
        unit_id: c.unit_id || items.find((item) => item.id === c.item_id)?.unit_id || items[0]?.unit_id || '',
        net_quantity: c.net_quantity,
        waste_rate: c.waste_rate || '0',
        waste_percent: rateToPercent(c.waste_rate || '0'),
      })),
    }));
  };

  const authoritativeTotalCost = recipe?.latest_cost?.total_cost;
  const authoritativeCostPerPortion = recipe?.latest_cost?.cost_per_yield_unit;
  const requestedVersionChanged = Boolean(requestedRecipeId && recipe?.id && recipe.id !== requestedRecipeId);

  // Cálculo de costo teórico estimado en tiempo real por componente
  const estimatedComponentsCost = useMemo(() => {
    return formData.components.map((c) => {
      const item = items.find((it) => it.id === c.item_id);
      const unitCost = Number(item?.last_unit_cost ?? item?.average_unit_cost ?? 0);
      const netVal = parseFloat(c.net_quantity) || 0;
      const wasteVal = parseFloat(c.waste_rate) || 0;
      const factor = wasteVal > 0 && wasteVal < 1 ? (1 - wasteVal) : 1;
      const gross = factor > 0 ? netVal / factor : netVal;
      return {
        unitCost,
        gross,
        totalComponentCost: gross * unitCost,
      };
    });
  }, [formData.components, items]);

  const liveTotalCost = useMemo(() => {
    return estimatedComponentsCost.reduce((sum, c) => sum + c.totalComponentCost, 0);
  }, [estimatedComponentsCost]);

  const yieldQty = parseFloat(formData.yield_quantity) || 1;
  const liveCostPerPortion = yieldQty > 0 ? liveTotalCost / yieldQty : 0;

  const hasAuthoritative = authoritativeTotalCost != null
    && (typeof authoritativeTotalCost === 'string' || typeof authoritativeTotalCost === 'number')
    && Number.isFinite(Number(authoritativeTotalCost));

  const displayTotalCost = hasAuthoritative
    ? `$${Number(authoritativeTotalCost).toFixed(2)} MXN`
    : liveTotalCost > 0
    ? `$${liveTotalCost.toFixed(2)} MXN`
    : 'No disponible';

  const displayCostPerPortion = hasAuthoritative
    ? `$${Number(authoritativeCostPerPortion).toFixed(2)} MXN`
    : liveCostPerPortion > 0
    ? `$${liveCostPerPortion.toFixed(2)} MXN`
    : 'No disponible';

  const isEstimated = !hasAuthoritative && liveTotalCost > 0;

  const yieldUnits = useMemo(() => {
    const seen = new Set<string>();
    const units = items.flatMap((item) => {
      if (!item.unit_id || seen.has(item.unit_id)) return [];
      seen.add(item.unit_id);
      return [{ id: item.unit_id, code: item.unit_code }];
    });
    if (formData.yield_unit_id && !seen.has(formData.yield_unit_id)) {
      units.unshift({ id: formData.yield_unit_id, code: 'Unidad vigente' });
    }
    return units;
  }, [formData.yield_unit_id, items]);

  const filteredItems = useMemo(() => {
    const query = ingredientFilter.trim().toLocaleLowerCase('es-MX');
    if (!query) return items;
    return items.filter((item) => (
      item.name.toLocaleLowerCase('es-MX').includes(query)
      || item.unit_code.toLocaleLowerCase('es-MX').includes(query)
    ));
  }, [ingredientFilter, items]);

  if (!isOpen) return null;

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title={`Receta: ${productName}`} size="xl" maxWidth="940px">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando componentes de receta…</div>
        ) : recipeLoadFailed ? (
          <div role="alert" style={{ padding: 24, borderRadius: 8, background: 'rgba(239, 68, 68, 0.1)', color: 'var(--color-red)' }}>
            <p>No fue posible consultar la receta vigente. No se habilitó la edición para evitar sobrescribir una versión desconocida.</p>
            <Button variant="secondary" onClick={() => void refetchRecipe()}>
              Reintentar lectura de receta
            </Button>
          </div>
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
            {requestedRecipeId && recipe?.id === requestedRecipeId && (
              <p role="status" className="premium-form-hint">Versión efectiva solicitada: {recipe.id}</p>
            )}
            {requestedRecipeId && recipe?.id && recipe.id !== requestedRecipeId && (
              <p role="alert">La versión efectiva cambió desde la consulta de usos. Cierra y vuelve a consultar para evitar editar una versión distinta.</p>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, paddingBottom: 12, borderBottom: '1px solid var(--color-border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <ChefHat size={20} style={{ color: '#16a34a' }} />
                <label htmlFor={`recipe-yield-${productId}`} style={{ fontWeight: 600, fontSize: '0.9375rem' }}>
                  Rendimiento:
                </label>
                <Input
                  id={`recipe-yield-${productId}`}
                  type="number"
                  min="0.000001"
                  step="any"
                  value={formData.yield_quantity}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    prepareRecipeEdit();
                    setFormData({ ...formData, yield_quantity: e.target.value });
                  }}
                  style={{ width: 85 }}
                />
                <label htmlFor={`recipe-yield-unit-${productId}`} style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                  Unidad de rendimiento:
                </label>
                <select
                  id={`recipe-yield-unit-${productId}`}
                  aria-label="Unidad de rendimiento"
                  value={formData.yield_unit_id}
                  onChange={(event) => {
                    prepareRecipeEdit();
                    setFormData({ ...formData, yield_unit_id: event.target.value });
                  }}
                  style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-surface)' }}
                >
                  <option value="">Unidad predeterminada por el servidor</option>
                  {yieldUnits.map((unit) => <option key={unit.id} value={unit.id}>{unit.code}</option>)}
                </select>
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

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <label htmlFor={`recipe-ingredient-filter-${productId}`} style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                Buscar ingrediente
              </label>
              <Input
                id={`recipe-ingredient-filter-${productId}`}
                type="search"
                value={ingredientFilter}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setIngredientFilter(event.target.value)}
                placeholder="Filtrar insumos por nombre o unidad"
                style={{ flex: 1, minWidth: 220 }}
              />
              <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                {filteredItems.length} de {items.length}
              </span>
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
                      <th style={{ width: 140, textAlign: 'right' }}>Cantidad neta</th>
                      <th style={{ width: 130, textAlign: 'right' }}>
                        <span title="Porcentaje de merma; el servidor vuelve a calcular cantidad bruta y costo">
                          Merma (%)
                        </span>
                      </th>
                      <th style={{ width: 130, textAlign: 'right' }}>Cantidad bruta</th>
                      <th style={{ width: 130, textAlign: 'right' }}>Costo preliminar</th>
                      <th style={{ width: 60, textAlign: 'center' }}>Quitar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {formData.components.map((component, index) => {
                      const itemObj = items.find((entry) => entry.id === component.item_id);
                      const visibleItems = itemObj && !filteredItems.some((entry) => entry.id === itemObj.id)
                        ? [itemObj, ...filteredItems]
                        : filteredItems;
                      return (
                        <tr key={index}>
                          <td>
                            <select
                              aria-label={`Insumo ${index + 1}`}
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
                              {visibleItems.map((item) => (
                                <option key={item.id} value={item.id}>
                                  {item.name} · {item.unit_code} {item.last_unit_cost ? `($${Number(item.last_unit_cost).toFixed(2)}/${item.unit_code})` : ''}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
                              <Input
                                aria-label={`Cantidad neta de ${itemObj?.name || `ingrediente ${index + 1}`}`}
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
                                aria-label={`Merma porcentual de ${itemObj?.name || `ingrediente ${index + 1}`}`}
                                type="text"
                                inputMode="decimal"
                                value={component.waste_percent ?? rateToPercent(component.waste_rate)}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateWastePercent(index, e.target.value)}
                                placeholder="0"
                                style={{ width: 80, textAlign: 'right' }}
                              />
                              <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>%</span>
                            </div>
                          </td>
                          <td style={{ textAlign: 'right', fontFamily: 'monospace', color: 'var(--color-text-muted)' }}>
                            {estimatedComponentsCost[index]?.gross > 0
                              ? `${estimatedComponentsCost[index].gross.toFixed(6)} ${itemObj?.unit_code || ''}`
                              : '—'}
                          </td>
                          <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--color-green)' }}>
                            {estimatedComponentsCost[index]?.totalComponentCost > 0
                              ? `$${estimatedComponentsCost[index].totalComponentCost.toFixed(2)}`
                              : itemObj?.last_unit_cost
                              ? `$0.00`
                              : <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem', fontWeight: 400 }}>Pendiente</span>}
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <button
                              aria-label="Quitar insumo"
                              className="premium-action-btn delete"
                              onClick={() => {
                                prepareRecipeEdit();
                                setFormData((old) => ({ ...old, components: old.components.filter((_, i) => i !== index) }));
                              }}
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

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap', padding: '14px 18px', background: 'rgba(34, 197, 94, 0.08)', borderRadius: 10, border: '1px solid rgba(34, 197, 94, 0.2)' }}>
              <div>
                <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                  {hasAuthoritative ? 'Costo confirmado por backend:' : 'Costo preliminar:'}
                </span>
                <span style={{ marginLeft: 8, fontSize: '1.125rem', fontWeight: 700, color: 'var(--color-green)' }}>
                  {displayTotalCost}
                </span>
                {isEstimated && (
                  <span style={{ marginLeft: 6, fontSize: '0.75rem', background: '#fef3c7', color: '#92400e', padding: '2px 6px', borderRadius: 4, fontWeight: 600 }}>
                    Estimado catálogo
                  </span>
                )}
                <span style={{ marginLeft: 16, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                  ({displayCostPerPortion} por unidad de rendimiento)
                </span>
                {salePriceCents != null && (
                  <span style={{ display: 'block', marginTop: 5, fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                    Precio de venta actual: ${(salePriceCents / 100).toFixed(2)} MXN
                  </span>
                )}
                <span style={{ display: 'block', marginTop: 5, fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                  {hasAuthoritative
                    ? 'El costo corresponde a la última lectura efectiva del backend.'
                    : 'Vista previa del navegador; Python recalcula cantidades y costo al guardar.'}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                <Button variant="secondary" onClick={onClose}>Volver al producto</Button>
                <Button
                  variant="primary"
                  disabled={save.isPending || formData.components.length === 0 || requestedVersionChanged || hasVersionConflict}
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
