import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { Button, Input, Select, Badge } from '@restaurantos/ui';
import {
  categoryOptionEditorState,
  categoryOptionEditorHydrationKey,
  categoryOptionValueEditorState,
  type CategoryOptionValueEditorState,
} from './categoryOptionEditorState';
import { Layers, Plus, CheckCircle2, AlertCircle, Edit, Check, X, ShieldAlert, Sparkles, Filter } from 'lucide-react';
import '../../premium-catalogs.css';

type Category = { id: string; name: string; display_order: number };
type Product = { id: string; name: string; sku: string; category_id?: string; status: string };
type Value = {
  id: string; code: string; name: string; display_order: number;
  status: 'active' | 'inactive' | 'archived';
};
type Coverage = {
  category_id: string;
  group: { id: string; code: string; name: string; status: 'active' | 'inactive' | 'archived' } | null;
  values: Value[];
  complete: boolean;
  incomplete_products: Product[];
  products: Array<Product & { assignment: { value_id: string; value_code: string; value_name: string; value_status: string } | null; incomplete: boolean }>;
};

const failure = (reason: unknown) => reason instanceof ApiError ? reason.message : 'No se pudo completar la operación.';

export default function CategoryOptionManager() {
  const client = useQueryClient();
  const [categoryId, setCategoryId] = useState('');
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [groupStatus, setGroupStatus] = useState<'active' | 'inactive' | 'archived'>('inactive');
  const [valueCode, setValueCode] = useState('');
  const [valueName, setValueName] = useState('');
  const [editingValue, setEditingValue] = useState<CategoryOptionValueEditorState | null>(null);
  const [message, setMessage] = useState('');
  const categoriesQuery = useQuery<Category[]>({ queryKey: ['categories'], queryFn: () => fetchApi('/categories') });
  const coverageQuery = useQuery<Coverage>({
    queryKey: ['category-option-coverage', categoryId],
    queryFn: () => fetchApi(`/categories/${categoryId}/selection-group`),
    enabled: Boolean(categoryId),
  });
  const productsQuery = useQuery<Product[]>({ queryKey: ['catalog-products'], queryFn: () => fetchApi('/catalog/products') });
  const coverage = coverageQuery.data?.category_id === categoryId ? coverageQuery.data : undefined;
  const groupHydrationKey = categoryOptionEditorHydrationKey(coverage?.group);

  useEffect(() => {
    const state = categoryOptionEditorState(null);
    setCode(state.code); setName(state.name); setGroupStatus(state.status);
    setValueCode(''); setValueName(''); setEditingValue(null);
  }, [categoryId]);

  useEffect(() => {
    const state = categoryOptionEditorState(coverage?.group);
    setCode(state.code);
    setName(state.name);
    setGroupStatus(state.status);
  }, [groupHydrationKey]);

  const refresh = () => {
    void coverageQuery.refetch();
    void client.invalidateQueries({ queryKey: ['categories'] });
  };

  const groupMutation = useMutation({
    mutationFn: (status: 'inactive' | 'active' | 'archived') => fetchApi(`/categories/${categoryId}/selection-group`, { method: 'POST', body: JSON.stringify({ code, name, selection_mode: 'single', is_required: true, status }) }),
    onSuccess: () => { setMessage('Selector guardado.'); refresh(); }, onError: (reason) => setMessage(failure(reason)),
  });

  const valueMutation = useMutation({
    mutationFn: () => fetchApi(`/catalog/category-option-groups/${coverage?.group?.id}/values`, { method: 'POST', body: JSON.stringify({ code: valueCode, name: valueName, status: 'active' }) }),
    onSuccess: () => { setValueCode(''); setValueName(''); setMessage('Opción guardada.'); refresh(); }, onError: (reason) => setMessage(failure(reason)),
  });

  const updateValueMutation = useMutation({
    mutationFn: (value: CategoryOptionValueEditorState) => fetchApi(`/catalog/category-option-groups/${coverage?.group?.id}/values/${value.id}`, { method: 'PUT', body: JSON.stringify({ code: value.code, name: value.name, display_order: value.displayOrder, status: value.status }) }),
    onSuccess: () => { setEditingValue(null); setMessage('Opción actualizada.'); refresh(); }, onError: (reason) => setMessage(failure(reason)),
  });

  const assignmentMutation = useMutation({
    mutationFn: ({ productId, optionValueId }: { productId: string; optionValueId: string }) => fetchApi(`/catalog/category-option-groups/${coverage?.group?.id}/assignments/${productId}`, { method: 'PUT', body: JSON.stringify({ option_value_id: optionValueId }) }),
    onSuccess: () => { setMessage('Producto asignado.'); refresh(); }, onError: (reason) => setMessage(failure(reason)),
  });

  return (
    <main style={{ maxWidth: 1120, padding: '0 0 40px 0' }}>
      <div style={{ marginBottom: 32 }}>
        <h1 className="premium-header-title">Selector previo de categoría</h1>
        <p className="premium-header-subtitle">
          Configuración corporativa; no cambia precios, recetas ni disponibilidad de sucursal.
        </p>
      </div>

      <div className="premium-card" style={{ padding: 24, marginBottom: 24 }}>
        <div className="premium-form-group" style={{ maxWidth: 480 }}>
          <label className="premium-form-label" style={{ fontSize: '0.95rem' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Filter size={18} color="#2563eb" /> Categoría a configurar
            </span>
          </label>
          <Select
            value={categoryId}
            onChange={(event) => { setCategoryId(event.target.value); setMessage(''); }}
          >
            <option value="">Selecciona una categoría</option>
            {(categoriesQuery.data || []).map((category) => (
              <option key={category.id} value={category.id}>{category.name}</option>
            ))}
          </Select>
        </div>
      </div>

      {categoriesQuery.isLoading || productsQuery.isLoading ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Cargando configuración…</div>
      ) : categoriesQuery.isError || productsQuery.isError ? (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '14px 18px', borderRadius: 12, marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>No fue posible cargar la configuración.</span>
          <Button variant="secondary" onClick={refresh}>Reintentar</Button>
        </div>
      ) : null}

      {categoryId && (
        <>
          {coverageQuery.isLoading ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Cargando cobertura…</div>
          ) : coverageQuery.isError ? (
            <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '14px 18px', borderRadius: 12, marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>No fue posible cargar la cobertura.</span>
              <Button variant="secondary" onClick={refresh}>Reintentar</Button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              {/* Card 1: Configuración del Selector Previo */}
              <section className="premium-card" style={{ padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                  <div>
                    <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#1e293b', margin: 0 }}>Selector previo</h2>
                    <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '2px 0 0' }}>Define el grupo obligatorio de selección antes de añadir al pedido</p>
                  </div>
                  {coverage?.group && (
                    <Badge variant={coverage.group.status === 'active' ? 'success' : coverage.group.status === 'archived' ? 'default' : 'warning'}>
                      {coverage.group.status === 'active' ? 'Activo' : coverage.group.status === 'archived' ? 'Archivado' : 'Inactivo'}
                    </Badge>
                  )}
                </div>

                <div className="premium-form-layout">
                  <div className="premium-form-grid">
                    <div className="premium-form-group">
                      <label className="premium-form-label">Código</label>
                      <Input
                        placeholder="Ej. size, type, bread"
                        value={code}
                        onChange={(event: React.ChangeEvent<HTMLInputElement>) => setCode(event.target.value)}
                      />
                    </div>

                    <div className="premium-form-group">
                      <label className="premium-form-label">Nombre visible</label>
                      <Input
                        placeholder="Ej. Tamaño, Tipo de pan"
                        value={name}
                        onChange={(event: React.ChangeEvent<HTMLInputElement>) => setName(event.target.value)}
                      />
                    </div>

                    <div className="premium-form-group">
                      <label className="premium-form-label">Estado</label>
                      <Select
                        value={groupStatus}
                        onChange={(event) => setGroupStatus(event.target.value as 'active' | 'inactive' | 'archived')}
                      >
                        <option value="inactive">Inactivo</option>
                        <option value="active">Activo</option>
                        <option value="archived">Archivado</option>
                      </Select>
                    </div>
                  </div>

                  {!coverage?.complete && coverage?.group && (
                    <div role="alert" style={{ background: '#fffbeb', color: '#92400e', border: '1px solid #fef3c7', padding: '12px 16px', borderRadius: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <AlertCircle size={18} />
                      <span>La activación se rechaza hasta completar la cobertura.</span>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 12 }}>
                    <Button
                      variant="primary"
                      onClick={() => groupMutation.mutate(groupStatus)}
                      disabled={!code || !name || groupMutation.isPending || (groupStatus === 'active' && !coverage?.complete)}
                    >
                      Guardar selector
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => groupMutation.mutate('active')}
                      disabled={!coverage?.group || !coverage.complete || groupMutation.isPending}
                    >
                      <CheckCircle2 size={16} color="#059669" /> Activar
                    </Button>
                    {coverage?.group && (
                      <Button
                        variant="secondary"
                        onClick={() => groupMutation.mutate('archived')}
                        disabled={groupMutation.isPending}
                      >
                        Archivar selector
                      </Button>
                    )}
                  </div>
                </div>
              </section>

              {/* Card 2: Opciones del Selector */}
              {coverage?.group && (
                <section className="premium-card" style={{ padding: 24 }}>
                  <div style={{ marginBottom: 20 }}>
                    <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#1e293b', margin: 0 }}>Opciones</h2>
                    <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '2px 0 0' }}>Valores seleccionables (ej. Chico, Mediano, Grande)</p>
                  </div>

                  <div className="premium-section-box" style={{ marginBottom: 20 }}>
                    <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#334155' }}>Nueva opción</span>
                    <div className="premium-form-grid" style={{ alignItems: 'flex-end' }}>
                      <div className="premium-form-group">
                        <label className="premium-form-label">Código</label>
                        <Input
                          placeholder="Ej. small"
                          value={valueCode}
                          onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValueCode(event.target.value)}
                        />
                      </div>
                      <div className="premium-form-group">
                        <label className="premium-form-label">Nombre</label>
                        <Input
                          placeholder="Ej. Chico (250 ml)"
                          value={valueName}
                          onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValueName(event.target.value)}
                        />
                      </div>
                      <Button
                        variant="primary"
                        onClick={() => valueMutation.mutate()}
                        disabled={!valueCode || !valueName || valueMutation.isPending}
                        style={{ height: '42px' }}
                      >
                        <Plus size={16} /> Agregar opción
                      </Button>
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {coverage.values.length === 0 ? (
                      <div style={{ padding: 20, textAlign: 'center', color: '#64748b', fontSize: '0.9rem' }}>
                        No hay opciones configuradas. Agrega al menos una opción para asignar a productos.
                      </div>
                    ) : (
                      coverage.values.map((value) => {
                        const editing = editingValue?.id === value.id ? editingValue : null;
                        return (
                          <div key={value.id} className="premium-line-item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                            {editing ? (
                              <div className="premium-form-layout">
                                <div className="premium-form-grid">
                                  <div className="premium-form-group">
                                    <label className="premium-form-label">Código</label>
                                    <Input
                                      aria-label={`Código de ${value.name}`}
                                      value={editing.code}
                                      onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditingValue({ ...editing, code: event.target.value })}
                                    />
                                  </div>
                                  <div className="premium-form-group">
                                    <label className="premium-form-label">Nombre</label>
                                    <Input
                                      aria-label={`Nombre de ${value.name}`}
                                      value={editing.name}
                                      onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditingValue({ ...editing, name: event.target.value })}
                                    />
                                  </div>
                                  <div className="premium-form-group">
                                    <label className="premium-form-label">Orden</label>
                                    <Input
                                      type="number"
                                      aria-label={`Orden de ${value.name}`}
                                      value={editing.displayOrder}
                                      onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditingValue({ ...editing, displayOrder: Number(event.target.value) })}
                                    />
                                  </div>
                                  <div className="premium-form-group">
                                    <label className="premium-form-label">Estado</label>
                                    <Select
                                      aria-label={`Estado de ${value.name}`}
                                      value={editing.status}
                                      onChange={(event) => setEditingValue({ ...editing, status: event.target.value as Value['status'] })}
                                    >
                                      <option value="active">Activo</option>
                                      <option value="inactive">Inactivo</option>
                                      <option value="archived">Archivado</option>
                                    </Select>
                                  </div>
                                </div>
                                <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                                  <Button
                                    variant="secondary"
                                    onClick={() => setEditingValue(null)}
                                    disabled={updateValueMutation.isPending}
                                  >
                                    Cancelar
                                  </Button>
                                  <Button
                                    variant="primary"
                                    onClick={() => updateValueMutation.mutate(editing)}
                                    disabled={updateValueMutation.isPending || !editing.code || !editing.name}
                                  >
                                    Guardar opción
                                  </Button>
                                </div>
                              </div>
                            ) : (
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                  <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#1e293b' }}>{value.name}</span>
                                  <code style={{ background: '#f1f5f9', padding: '2px 8px', borderRadius: 6, fontSize: '0.8rem', color: '#475467' }}>
                                    {value.code}
                                  </code>
                                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>orden {value.display_order}</span>
                                  <Badge variant={value.status === 'active' ? 'success' : 'default'}>
                                    {value.status}
                                  </Badge>
                                </div>
                                <Button
                                  variant="secondary"
                                  onClick={() => setEditingValue(categoryOptionValueEditorState(value))}
                                  disabled={updateValueMutation.isPending}
                                >
                                  <Edit size={14} /> Editar
                                </Button>
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </section>
              )}

              {/* Card 3: Cobertura de Productos */}
              {coverage?.group && (
                <section className="premium-card" style={{ padding: 24 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                    <div>
                      <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#1e293b', margin: 0 }}>Cobertura</h2>
                      <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '2px 0 0' }}>Todos los productos de la categoría deben tener una opción asignada</p>
                    </div>
                    <Badge variant={coverage.complete ? 'success' : 'warning'}>
                      {coverage.complete ? 'Cobertura completa.' : `${coverage.incomplete_products.length} Productos incompletos.`}
                    </Badge>
                  </div>

                  <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#334155', marginBottom: 16 }}>
                    Productos de la categoría
                  </h3>

                  {!coverage.complete && (
                    <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <AlertCircle size={18} />
                      <span>{coverage.incomplete_products.length} producto(s) incompleto(s).</span>
                    </div>
                  )}

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {coverage.products.map((product) => (
                      <div
                        key={product.id}
                        className="premium-line-item"
                        style={{
                          justifyContent: 'space-between',
                          borderLeft: product.incomplete ? '4px solid #ef4444' : '1px solid #e2e8f0',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div>
                            <strong style={{ color: product.incomplete ? '#b91c1c' : '#1e293b', fontSize: '0.95rem' }}>
                              {product.name}
                            </strong>
                            <br />
                            <small style={{ color: '#64748b' }}>{product.sku}</small>
                          </div>
                          {product.incomplete && (
                            <Badge variant="warning">Incompleto</Badge>
                          )}
                        </div>

                        <div style={{ width: 240, maxWidth: '50%' }}>
                          <Select
                            value={product.assignment?.value_id || ''}
                            onChange={(event) => event.target.value && assignmentMutation.mutate({ productId: product.id, optionValueId: event.target.value })}
                          >
                            <option value="">Sin asignación</option>
                            {coverage.values.filter((value) => value.status === 'active').map((value) => (
                              <option key={value.id} value={value.id}>{value.name}</option>
                            ))}
                          </Select>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </>
      )}

      {message && (
        <div role="status" style={{ marginTop: 24, background: '#eff6ff', color: '#1e40af', border: '1px solid #dbeafe', padding: '12px 16px', borderRadius: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{message}</span>
          <Button variant="secondary" onClick={refresh}>Reintentar</Button>
        </div>
      )}
    </main>
  );
}
