import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Badge, Button, Input, Select } from '@restaurantos/ui';
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Edit3,
  FolderTree,
  Plus,
  Save,
  Search,
  Tags,
  X,
} from 'lucide-react';
import {
  categoryOptionEditorHydrationKey,
  categoryOptionEditorState,
  categoryOptionValueEditorState,
  type CategoryOptionValueEditorState,
} from './categoryOptionEditorState';
import './GroupSubgroupWorkspace.css';

type CategoryStatus = 'active' | 'inactive';
type OptionStatus = 'active' | 'inactive' | 'archived';

interface Category {
  id: string;
  name: string;
  display_order: number;
  status: CategoryStatus;
}

interface Product {
  id: string;
  name: string;
  sku: string;
  category_id?: string;
  status: string;
}

interface SubgroupValue {
  id: string;
  code: string;
  name: string;
  display_order: number;
  status: OptionStatus;
}

interface Coverage {
  category_id: string;
  group: { id: string; code: string; name: string; status: OptionStatus } | null;
  values: SubgroupValue[];
  complete: boolean;
  incomplete_products: Product[];
  products: Array<Product & {
    assignment: {
      value_id: string;
      value_code: string;
      value_name: string;
      value_status: string;
    } | null;
    incomplete: boolean;
  }>;
}

const failure = (reason: unknown) => reason instanceof ApiError
  ? reason.message
  : 'No se pudo completar la operación.';

const normalizeSubgroupCode = (value: string) => value
  .trim()
  .toLocaleLowerCase('es-MX')
  .replace(/\s+/g, '-')
  .replace(/[^a-z0-9_-]/g, '');

export default function CategoriesList() {
  const client = useQueryClient();
  const [selectedCategoryId, setSelectedCategoryId] = useState('');
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [search, setSearch] = useState('');
  const [categoryForm, setCategoryForm] = useState({ name: '', display_order: 0, status: 'active' as CategoryStatus });
  const [groupCode, setGroupCode] = useState('');
  const [groupName, setGroupName] = useState('');
  const [groupStatus, setGroupStatus] = useState<OptionStatus>('inactive');
  const [subgroupCode, setSubgroupCode] = useState('');
  const [subgroupName, setSubgroupName] = useState('');
  const [editingSubgroup, setEditingSubgroup] = useState<CategoryOptionValueEditorState | null>(null);
  const [notice, setNotice] = useState<{ tone: 'success' | 'error'; text: string } | null>(null);

  const categoriesQuery = useQuery<Category[]>({
    queryKey: ['categories'],
    queryFn: () => fetchApi('/categories'),
  });
  const coverageQuery = useQuery<Coverage>({
    queryKey: ['category-option-coverage', selectedCategoryId],
    queryFn: () => fetchApi(`/categories/${selectedCategoryId}/selection-group`),
    enabled: Boolean(selectedCategoryId),
  });

  const categories = useMemo(() => categoriesQuery.data || [], [categoriesQuery.data]);
  const selectedCategory = categories.find((category) => category.id === selectedCategoryId) || null;
  const coverage = coverageQuery.data?.category_id === selectedCategoryId ? coverageQuery.data : undefined;
  const groupHydrationKey = categoryOptionEditorHydrationKey(coverage?.group);
  const filteredCategories = categories.filter((category) => category.name.toLocaleLowerCase('es-MX').includes(search.trim().toLocaleLowerCase('es-MX')));

  useEffect(() => {
    if (selectedCategoryId || isCreatingCategory || categories.length === 0) return;
    setSelectedCategoryId(categories[0].id);
  }, [categories, isCreatingCategory, selectedCategoryId]);

  useEffect(() => {
    if (!selectedCategory) return;
    setCategoryForm({
      name: selectedCategory.name,
      display_order: selectedCategory.display_order,
      status: selectedCategory.status,
    });
  }, [selectedCategory]);

  useEffect(() => {
    const state = categoryOptionEditorState(coverage?.group);
    setGroupCode(state.code);
    setGroupName(state.name);
    setGroupStatus(state.status);
    setSubgroupCode('');
    setSubgroupName('');
    setEditingSubgroup(null);
  }, [groupHydrationKey, selectedCategoryId]);

  const refreshWorkspace = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['categories'] }),
      client.invalidateQueries({ queryKey: ['category-option-coverage', selectedCategoryId] }),
    ]);
  };

  const categoryMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        name: categoryForm.name.trim().toLocaleUpperCase('es-MX'),
        display_order: categoryForm.display_order,
        status: categoryForm.status,
      };
      if (selectedCategoryId) {
        return fetchApi<{ id: string }>(`/categories/${selectedCategoryId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      }
      return fetchApi<{ id: string }>('/categories', {
        method: 'POST',
        body: JSON.stringify({ name: payload.name, display_order: payload.display_order }),
      });
    },
    onSuccess: async (saved) => {
      const wasCreating = !selectedCategoryId;
      setIsCreatingCategory(false);
      setSelectedCategoryId(saved.id);
      setNotice({ tone: 'success', text: wasCreating ? 'Grupo creado.' : 'Grupo actualizado.' });
      await refreshWorkspace();
    },
    onError: (reason) => setNotice({ tone: 'error', text: failure(reason) }),
  });

  const groupMutation = useMutation({
    mutationFn: (status: OptionStatus) => fetchApi(`/categories/${selectedCategoryId}/selection-group`, {
      method: 'POST',
      body: JSON.stringify({
        code: groupCode || 'subgroup',
        name: groupName || 'Subgrupos',
        selection_mode: 'single',
        is_required: true,
        status,
      }),
    }),
    onSuccess: async () => {
      setNotice({ tone: 'success', text: 'Configuración de subgrupos guardada.' });
      await refreshWorkspace();
    },
    onError: (reason) => setNotice({ tone: 'error', text: failure(reason) }),
  });

  const subgroupMutation = useMutation({
    mutationFn: () => fetchApi(`/catalog/category-option-groups/${coverage?.group?.id}/values`, {
      method: 'POST',
      body: JSON.stringify({
        code: normalizeSubgroupCode(subgroupCode),
        name: subgroupName.trim().toLocaleUpperCase('es-MX'),
        status: 'active',
      }),
    }),
    onSuccess: async () => {
      setSubgroupCode('');
      setSubgroupName('');
      setNotice({ tone: 'success', text: 'Subgrupo creado.' });
      await refreshWorkspace();
    },
    onError: (reason) => setNotice({ tone: 'error', text: failure(reason) }),
  });

  const updateSubgroupMutation = useMutation({
    mutationFn: (value: CategoryOptionValueEditorState) => fetchApi(`/catalog/category-option-groups/${coverage?.group?.id}/values/${value.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        code: normalizeSubgroupCode(value.code),
        name: value.name.trim().toLocaleUpperCase('es-MX'),
        display_order: value.displayOrder,
        status: value.status,
      }),
    }),
    onSuccess: async () => {
      setEditingSubgroup(null);
      setNotice({ tone: 'success', text: 'Subgrupo actualizado.' });
      await refreshWorkspace();
    },
    onError: (reason) => setNotice({ tone: 'error', text: failure(reason) }),
  });

  const assignmentMutation = useMutation({
    mutationFn: ({ productId, optionValueId }: { productId: string; optionValueId: string }) => fetchApi(`/catalog/category-option-groups/${coverage?.group?.id}/assignments/${productId}`, {
      method: 'PUT',
      body: JSON.stringify({ option_value_id: optionValueId }),
    }),
    onSuccess: async () => {
      setNotice({ tone: 'success', text: 'Producto asignado al subgrupo.' });
      await refreshWorkspace();
    },
    onError: (reason) => setNotice({ tone: 'error', text: failure(reason) }),
  });

  const startNewCategory = () => {
    setIsCreatingCategory(true);
    setSelectedCategoryId('');
    setCategoryForm({ name: '', display_order: categories.length, status: 'active' });
    setNotice(null);
  };

  const isLoading = categoriesQuery.isLoading;
  const hasLoadError = categoriesQuery.isError;

  return (
    <main className="group-subgroup-workspace">
      <header className="group-subgroup-header">
        <div>
          <span className="group-subgroup-eyebrow">Catálogo para Punto de Venta</span>
          <h1 className="premium-header-title">Grupos y subgrupos</h1>
          <p className="premium-header-subtitle">Organiza el menú con el mismo recorrido que usa el cajero al capturar un pedido.</p>
        </div>
        <button type="button" className="premium-add-btn" onClick={startNewCategory}>
          <Plus size={18} /> Nuevo grupo
        </button>
      </header>

      {notice && (
        <div className={`group-subgroup-notice ${notice.tone}`} role={notice.tone === 'error' ? 'alert' : 'status'}>
          {notice.tone === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
          <span>{notice.text}</span>
          <button type="button" onClick={() => setNotice(null)} aria-label="Cerrar mensaje"><X size={16} /></button>
        </div>
      )}

      {isLoading ? (
        <div className="premium-card group-subgroup-feedback" role="status">Cargando grupos y subgrupos…</div>
      ) : hasLoadError ? (
        <div className="premium-card group-subgroup-feedback error" role="alert">
          <span>No fue posible cargar el catálogo.</span>
          <Button variant="secondary" onClick={() => void categoriesQuery.refetch()}>Reintentar</Button>
        </div>
      ) : (
        <div className="group-subgroup-layout">
          <aside className="premium-card group-master-panel" aria-label="Lista de grupos">
            <div className="group-panel-heading">
              <div><span>Grupos</span><strong>{categories.length}</strong></div>
              <div className="group-search-field">
                <Search size={16} aria-hidden="true" />
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar grupo" aria-label="Buscar grupo" />
              </div>
            </div>
            <div className="group-master-list">
              {filteredCategories.length === 0 ? (
                <div className="group-subgroup-empty"><Tags size={28} /><span>No hay grupos que coincidan.</span></div>
              ) : filteredCategories.map((category) => {
                const isSelected = category.id === selectedCategoryId;
                return (
                  <button
                    type="button"
                    key={category.id}
                    className={`group-master-row${isSelected ? ' active' : ''}`}
                    onClick={() => { setIsCreatingCategory(false); setSelectedCategoryId(category.id); setNotice(null); }}
                    aria-pressed={isSelected}
                  >
                    <span className="group-master-order">{String(category.display_order).padStart(2, '0')}</span>
                    <span className="group-master-copy"><strong>{category.name}</strong><small>{category.status === 'active' ? 'Activo' : 'Inactivo'}</small></span>
                    <ChevronRight size={17} aria-hidden="true" />
                  </button>
                );
              })}
            </div>
          </aside>

          <section className="premium-card group-detail-panel" aria-label="Detalle del grupo">
            <div className="group-panel-heading inline">
              <div>
                <span>{selectedCategoryId ? 'Detalle del grupo' : 'Nuevo grupo'}</span>
                <strong>{selectedCategory?.name || 'Sin guardar'}</strong>
              </div>
              {selectedCategory && <Badge variant={selectedCategory.status === 'active' ? 'success' : 'default'}>{selectedCategory.status === 'active' ? 'Activo' : 'Inactivo'}</Badge>}
            </div>
            <div className="group-detail-form">
              <label>
                <span>Nombre del grupo</span>
                <Input value={categoryForm.name} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setCategoryForm({ ...categoryForm, name: event.target.value.toLocaleUpperCase('es-MX') })} placeholder="Ej. CERVEZAS" />
              </label>
              <div className="group-detail-grid">
                <label>
                  <span>Orden en POS</span>
                  <Input type="number" min={0} value={categoryForm.display_order} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setCategoryForm({ ...categoryForm, display_order: Number(event.target.value) || 0 })} />
                </label>
                <label>
                  <span>Estado</span>
                  <Select value={categoryForm.status} onChange={(event) => setCategoryForm({ ...categoryForm, status: event.target.value as CategoryStatus })} disabled={!selectedCategoryId}>
                    <option value="active">Activo</option>
                    <option value="inactive">Inactivo</option>
                  </Select>
                </label>
              </div>
              <div className="group-behavior-note">
                <FolderTree size={19} aria-hidden="true" />
                <div><strong>Comportamiento en pedidos</strong><span>{coverage?.group?.status === 'active' ? 'El cajero elige un subgrupo antes de ver productos.' : 'El cajero ve directamente los productos de este grupo.'}</span></div>
              </div>
              <Button variant="primary" onClick={() => categoryMutation.mutate()} disabled={!categoryForm.name.trim() || categoryMutation.isPending}>
                <Save size={16} /> {categoryMutation.isPending ? 'Guardando…' : 'Guardar grupo'}
              </Button>
            </div>
          </section>

          <section className="premium-card subgroup-panel" aria-label="Catálogo de subgrupos opcional">
            <div className="group-panel-heading inline">
              <div><span>Subgrupos</span><strong>Opcional</strong></div>
              {coverage?.group && <Badge variant={coverage.group.status === 'active' ? 'success' : coverage.group.status === 'archived' ? 'default' : 'warning'}>{coverage.group.status === 'active' ? 'Activo en POS' : coverage.group.status === 'archived' ? 'Archivado' : 'En preparación'}</Badge>}
            </div>

            {!selectedCategoryId ? (
              <div className="group-subgroup-empty large"><FolderTree size={38} /><strong>Guarda primero el grupo</strong><span>Después podrás crear sus subgrupos.</span></div>
            ) : coverageQuery.isLoading ? (
              <div className="group-subgroup-empty large" role="status">Cargando subgrupos…</div>
            ) : coverageQuery.isError ? (
              <div className="group-subgroup-empty large error" role="alert"><AlertCircle size={30} /><strong>No fue posible cargar los subgrupos.</strong><Button variant="secondary" onClick={() => void coverageQuery.refetch()}>Reintentar</Button></div>
            ) : !coverage?.group ? (
              <div className="group-subgroup-empty large">
                <FolderTree size={38} />
                <strong>Este grupo abre productos directamente</strong>
                <span>Habilita subgrupos sólo cuando ayuden al cajero a encontrar productos más rápido.</span>
                <Button variant="primary" onClick={() => groupMutation.mutate('inactive')} disabled={groupMutation.isPending}>Habilitar subgrupos</Button>
              </div>
            ) : (
              <div className="subgroup-content">
                <div className="subgroup-settings">
                  <label><span>Nombre del nivel</span><Input value={groupName} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setGroupName(event.target.value)} placeholder="Subgrupos" /></label>
                  <label><span>Código interno</span><Input value={groupCode} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setGroupCode(normalizeSubgroupCode(event.target.value))} placeholder="subgroup" /></label>
                  <label><span>Estado del nivel</span><Select value={groupStatus} onChange={(event) => setGroupStatus(event.target.value as OptionStatus)}><option value="inactive">En preparación</option><option value="active">Activo en POS</option><option value="archived">Archivado</option></Select></label>
                  <div className="subgroup-actions">
                    <Button variant="secondary" onClick={() => groupMutation.mutate(groupStatus)} disabled={!groupCode || !groupName || groupMutation.isPending}>Guardar configuración</Button>
                    <Button variant="primary" onClick={() => groupMutation.mutate('active')} disabled={!coverage.complete || groupMutation.isPending}>Activar en POS</Button>
                  </div>
                </div>

                <div className="subgroup-list" aria-label="Subgrupos del grupo seleccionado">
                  {coverage.values.length === 0 ? <p className="subgroup-empty-copy">Aún no hay subgrupos.</p> : coverage.values.map((value) => {
                    const editing = editingSubgroup?.id === value.id ? editingSubgroup : null;
                    return (
                      <div className="subgroup-row" key={value.id}>
                        {editing ? (
                          <div className="subgroup-edit-grid">
                            <Input aria-label={`Código de ${value.name}`} value={editing.code} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditingSubgroup({ ...editing, code: event.target.value })} />
                            <Input aria-label={`Nombre de ${value.name}`} value={editing.name} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditingSubgroup({ ...editing, name: event.target.value })} />
                            <Input aria-label={`Orden de ${value.name}`} type="number" value={editing.displayOrder} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditingSubgroup({ ...editing, displayOrder: Number(event.target.value) || 0 })} />
                            <Select aria-label={`Estado de ${value.name}`} value={editing.status} onChange={(event) => setEditingSubgroup({ ...editing, status: event.target.value as OptionStatus })}><option value="active">Activo</option><option value="inactive">Inactivo</option><option value="archived">Archivado</option></Select>
                            <div className="subgroup-edit-actions"><button type="button" onClick={() => setEditingSubgroup(null)} aria-label={`Cancelar edición de ${value.name}`}><X size={16} /></button><button type="button" onClick={() => updateSubgroupMutation.mutate(editing)} aria-label={`Guardar ${value.name}`}><Save size={16} /></button></div>
                          </div>
                        ) : (
                          <>
                            <code>{value.code}</code>
                            <span><strong>{value.name}</strong><small>Orden {value.display_order}</small></span>
                            <Badge variant={value.status === 'active' ? 'success' : 'default'}>{value.status === 'active' ? 'Activo' : value.status === 'inactive' ? 'Inactivo' : 'Archivado'}</Badge>
                            <button type="button" onClick={() => setEditingSubgroup(categoryOptionValueEditorState(value))} aria-label={`Editar ${value.name}`}><Edit3 size={16} /></button>
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div className="subgroup-create-row">
                  <Input aria-label="Código del nuevo subgrupo" value={subgroupCode} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setSubgroupCode(event.target.value)} placeholder="Código" />
                  <Input aria-label="Nombre del nuevo subgrupo" value={subgroupName} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setSubgroupName(event.target.value.toLocaleUpperCase('es-MX'))} placeholder="Nombre del subgrupo" />
                  <Button variant="primary" onClick={() => subgroupMutation.mutate()} disabled={!normalizeSubgroupCode(subgroupCode) || !subgroupName.trim() || subgroupMutation.isPending}><Plus size={16} /> Agregar</Button>
                </div>
              </div>
            )}
          </section>

          {selectedCategoryId && coverage?.group && (
            <section className="premium-card group-products-panel" aria-label="Productos del grupo">
              <div className="group-panel-heading products">
                <div><span>Productos del grupo</span><strong>{coverage.products.length}</strong></div>
                <div className={`coverage-summary${coverage.complete ? ' complete' : ' incomplete'}`}>
                  {coverage.complete ? <CheckCircle2 size={17} /> : <AlertCircle size={17} />}
                  {coverage.complete ? 'Cobertura completa' : `${coverage.incomplete_products.length} sin subgrupo`}
                </div>
              </div>
              <div className="group-products-grid">
                {coverage.products.length === 0 ? (
                  <div className="group-subgroup-empty">Este grupo todavía no tiene productos activos.</div>
                ) : coverage.products.map((product) => (
                  <div className={`group-product-row${product.incomplete ? ' incomplete' : ''}`} key={product.id}>
                    <div><strong>{product.name}</strong><small>SKU {product.sku}</small></div>
                    <Select
                      aria-label={`Subgrupo de ${product.name}`}
                      value={product.assignment?.value_id || ''}
                      onChange={(event) => event.target.value && assignmentMutation.mutate({ productId: product.id, optionValueId: event.target.value })}
                      disabled={assignmentMutation.isPending}
                    >
                      <option value="">Sin subgrupo</option>
                      {coverage.values.filter((value) => value.status === 'active').map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}
                    </Select>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </main>
  );
}
