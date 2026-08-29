import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Input, Modal, Select } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, Factory, Plus, Trash2, AlertCircle, Layers, Box } from 'lucide-react';
import '../../premium-catalogs.css';
import { resolveBranchId } from '../../lib/branchContext';

interface Item { id: string; name: string; sku: string; base_unit_id: string; unit_code: string; item_type: string; }
interface RecipeComponent { item_id: string; net_quantity: string; waste_percent: string; }
interface Recipe { id: string; recipe_type: string; output_item_id: string; output_item_name: string; output_item_sku: string; yield_quantity: number; yield_unit_id: string; yield_unit_code: string; version: number; }
interface Movement { id: string; movement_type: string; quantity_delta: number; }
interface Batch { id: string; recipe_id: string; lot_code: string; planned_quantity: number; actual_quantity: number; total_cost: number; unit_cost: number; status: string; movements: Movement[]; }

const ProductionList = () => {
  const branchId = resolveBranchId();
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
      queryClient.invalidateQueries({ queryKey: ['inventory', 'stock'] }),
    ]);
  };
  const recipeMutation = useMutation({
    mutationFn: () => fetchApi('/production-recipes', { method: 'POST', body: JSON.stringify({
      ...recipeForm,
      branch_id: branchId || null,
      yield_unit_id: selectedOutput?.base_unit_id || '',
    }) }),
    onSuccess: async () => {
      setRecipeOpen(false);
      setRecipeForm({ output_item_id: '', yield_quantity: '1', components: [{ item_id: '', net_quantity: '1', waste_percent: '0' }] });
      setError('');
      await refresh();
    },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible guardar la subreceta.'),
  });
  const batchMutation = useMutation({
    mutationFn: () => fetchApi('/production-batches', { method: 'POST', body: JSON.stringify({ branch_id: branchId, ...batchForm }) }),
    onSuccess: async () => {
      setBatchOpen(false);
      setBatchForm({ recipe_id: '', lot_code: '', planned_quantity: '1', actual_quantity: '1', actual_waste_quantity: '0' });
      setError('');
      await refresh();
    },
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

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Producción y elaborados</h1>
          <p className="premium-header-subtitle">Versiona subrecetas y transforma insumos en lotes trazables.</p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <Button variant="secondary" onClick={() => setRecipeOpen(true)}>
            <Plus size={16} /> Nueva subreceta
          </Button>
          <button
            className="premium-add-btn"
            onClick={() => setBatchOpen(true)}
            disabled={!branchId || productionRecipes.length === 0}
          >
            <Factory size={18} />
            Nuevo lote
          </button>
        </div>
      </div>

      {!branchId && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>Selecciona o asigna una sucursal para gestionar producción.</span>
        </div>
      )}

      {error && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      <div className="premium-card" style={{ marginBottom: 32 }}>
        <div style={{ padding: '20px 24px 12px', borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#1e293b', margin: 0 }}>Recetas de producción activas</h2>
          <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '2px 0 0' }}>Fichas de elaboración y subrecetas estandarizadas</p>
        </div>
        {productionRecipes.length === 0 ? (
          <div className="premium-empty-state">
            <Layers size={56} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay subrecetas creadas</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Define la fórmula para transformar insumos en productos elaborados (salsas, masas, mezclas).</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Producto Elaborado</th>
                  <th>Versión</th>
                  <th>Rendimiento base</th>
                </tr>
              </thead>
              <tbody>
                {productionRecipes.map((recipe) => (
                  <tr key={recipe.id}>
                    <td style={{ color: '#64748b', fontWeight: 600 }}>{recipe.output_item_sku}</td>
                    <td><strong style={{ color: '#1e293b' }}>{recipe.output_item_name}</strong></td>
                    <td><Badge variant="info">v{recipe.version}</Badge></td>
                    <td><strong style={{ color: '#047857' }}>{Number(recipe.yield_quantity)} {recipe.yield_unit_code}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="premium-card">
        <div style={{ padding: '20px 24px 12px', borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#1e293b', margin: 0 }}>Lotes de producción</h2>
          <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '2px 0 0' }}>Historial y costeo de lotes fabricados localmente</p>
        </div>
        {batches.length === 0 ? (
          <div className="premium-empty-state">
            <Box size={56} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay lotes registrados</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Inicia un lote de producción para descontar ingredientes y dar entrada al elaborado.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Código de lote</th>
                  <th>Elaborado</th>
                  <th>Cant. Planeada</th>
                  <th>Cant. Real</th>
                  <th>Costo unitario</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((batch) => {
                  const recipe = productionRecipes.find((item) => item.id === batch.recipe_id);
                  return (
                    <tr key={batch.id}>
                      <td><strong style={{ color: '#1e293b' }}>{batch.lot_code}</strong></td>
                      <td><span style={{ fontWeight: 600, color: '#334155' }}>{recipe?.output_item_name || batch.recipe_id}</span></td>
                      <td>{Number(batch.planned_quantity)}</td>
                      <td><strong style={{ color: '#047857' }}>{Number(batch.actual_quantity)}</strong></td>
                      <td><strong>${Number(batch.unit_cost).toFixed(4)}</strong></td>
                      <td>
                        <Badge variant={batch.status === 'confirmed' ? 'success' : 'info'}>
                          {batch.status === 'confirmed' ? 'Confirmado' : 'Borrador'}
                        </Badge>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                          {batch.status === 'draft' && (
                            <Button variant="primary" onClick={() => void confirmBatch(batch.id)}>
                              <CheckCircle2 size={15} /> Confirmar lote
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={recipeOpen} onClose={() => setRecipeOpen(false)} title="Nueva receta de producción" maxWidth="720px">
        <div className="premium-form-layout">
          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Producto elaborado a producir</label>
              <Select
                value={recipeForm.output_item_id}
                onChange={(event) => setRecipeForm({ ...recipeForm, output_item_id: event.target.value })}
              >
                <option value="">Selecciona elaborado</option>
                {elaboratedItems.map((item) => (
                  <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>
                ))}
              </Select>
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">
                Rendimiento esperado {selectedOutput?.unit_code ? `(${selectedOutput.unit_code})` : ''}
              </label>
              <Input
                type="number"
                step="any"
                placeholder="1.00"
                value={recipeForm.yield_quantity}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setRecipeForm({ ...recipeForm, yield_quantity: event.target.value })}
              />
            </div>
          </div>

          <div className="premium-section-box">
            <div className="premium-section-title">
              <span>Componentes e insumos requeridos ({recipeForm.components.length})</span>
              <Button
                variant="secondary"
                onClick={() => setRecipeForm({
                  ...recipeForm,
                  components: [...recipeForm.components, { item_id: '', net_quantity: '1', waste_percent: '0' }],
                })}
              >
                <Plus size={15} /> Agregar insumo
              </Button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {recipeForm.components.map((component, index) => (
                <div key={index} className="premium-line-item">
                  <div style={{ flex: 1 }}>
                    <Select
                      value={component.item_id}
                      onChange={(event) => updateComponent(index, 'item_id', event.target.value)}
                    >
                      <option value="">Selecciona insumo</option>
                      {items.filter((item) => item.id !== recipeForm.output_item_id).map((item) => (
                        <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>
                      ))}
                    </Select>
                  </div>

                  <div style={{ width: '110px' }}>
                    <Input
                      type="number"
                      step="any"
                      placeholder="Cant. neta"
                      value={component.net_quantity}
                      onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateComponent(index, 'net_quantity', event.target.value)}
                      aria-label="Cantidad neta"
                    />
                  </div>

                  <div style={{ width: '100px' }}>
                    <Input
                      type="number"
                      step="any"
                      placeholder="Merma %"
                      value={component.waste_percent}
                      onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateComponent(index, 'waste_percent', event.target.value)}
                      aria-label="Merma porcentual"
                    />
                  </div>

                  {recipeForm.components.length > 1 && (
                    <button
                      type="button"
                      className="premium-action-btn delete"
                      title="Eliminar insumo"
                      onClick={() => setRecipeForm({
                        ...recipeForm,
                        components: recipeForm.components.filter((_, itemIndex) => itemIndex !== index),
                      })}
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="premium-footer-actions">
            <Button variant="secondary" onClick={() => setRecipeOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => recipeMutation.mutate()}
              disabled={recipeMutation.isPending || !recipeForm.output_item_id || recipeForm.components.some((c) => !c.item_id || !c.net_quantity)}
            >
              {recipeMutation.isPending ? 'Guardando...' : 'Guardar versión'}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={batchOpen} onClose={() => setBatchOpen(false)} title="Nuevo lote de producción" maxWidth="620px">
        <div className="premium-form-layout">
          <div className="premium-form-group">
            <label className="premium-form-label">Subreceta de producción</label>
            <Select
              value={batchForm.recipe_id}
              onChange={(event) => {
                const selected = productionRecipes.find((recipe) => recipe.id === event.target.value);
                setBatchForm({
                  ...batchForm,
                  recipe_id: event.target.value,
                  planned_quantity: String(selected?.yield_quantity || 1),
                  actual_quantity: String(selected?.yield_quantity || 1),
                });
              }}
            >
              <option value="">Selecciona una receta</option>
              {productionRecipes.map((recipe) => (
                <option key={recipe.id} value={recipe.id}>
                  {recipe.output_item_name} · v{recipe.version}
                </option>
              ))}
            </Select>
          </div>

          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Código de lote</label>
              <Input
                placeholder="Ej. LOT-20260829-01"
                value={batchForm.lot_code}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setBatchForm({ ...batchForm, lot_code: event.target.value })}
              />
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Cantidad planeada</label>
              <Input
                type="number"
                step="any"
                value={batchForm.planned_quantity}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setBatchForm({ ...batchForm, planned_quantity: event.target.value })}
              />
            </div>
          </div>

          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Cantidad real producida</label>
              <Input
                type="number"
                step="any"
                value={batchForm.actual_quantity}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setBatchForm({ ...batchForm, actual_quantity: event.target.value })}
              />
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Merma real obtenida</label>
              <Input
                type="number"
                step="any"
                value={batchForm.actual_waste_quantity}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setBatchForm({ ...batchForm, actual_waste_quantity: event.target.value })}
              />
            </div>
          </div>

          <div className="premium-footer-actions">
            <Button variant="secondary" onClick={() => setBatchOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => batchMutation.mutate()}
              disabled={batchMutation.isPending || !batchForm.recipe_id || !batchForm.lot_code || !batchForm.actual_quantity}
            >
              {batchMutation.isPending ? 'Guardando...' : 'Guardar borrador'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default ProductionList;
