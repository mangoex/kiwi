import React, { useEffect, useMemo, useRef, useState } from 'react';
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
} from './categoryOptionEditorState';
import './GroupSubgroupWorkspace.css';

import { CLASSIFICATIONS, categoryCommandPayload, categoryCommandAttempt, type CategoryDraft, type CategoryAttempt, type ClassificationCode } from './catalogClassification';

type CategoryStatus = 'active' | 'inactive';
type OptionStatus = 'active' | 'inactive' | 'archived';

interface Category {
  id: string;
  name: string;
  display_order: number;
  status: CategoryStatus;
  classification_code: ClassificationCode | null;
  configuration_version: number;
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

type SubgroupEditor = Pick<SubgroupValue, 'id' | 'name'>;

const failure = (reason: unknown) => reason instanceof ApiError
  ? reason.message
  : 'No se pudo completar la operación.';

export default function CategoriesList() {
  const client = useQueryClient();
  const [selectedCategoryId, setSelectedCategoryId] = useState('');
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [search, setSearch] = useState('');
  const [categoryForm, setCategoryForm] = useState<CategoryDraft>({ name: '', display_order: 0, status: 'active', classification_code: '', configuration_version: 0 });
  const hydratedCategoryId = useRef('');
  const categoryAttempt = useRef<CategoryAttempt | null>(null);
  const [categoryConflict, setCategoryConflict] = useState(false);
  const [subgroupName, setSubgroupName] = useState('');
  const [editingSubgroup, setEditingSubgroup] = useState<SubgroupEditor | null>(null);
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
  const activeSubgroupCount = coverage?.values.filter((value) => value.status === 'active').length || 0;
  const filteredCategories = categories.filter((category) => category.name.toLocaleLowerCase('es-MX').includes(search.trim().toLocaleLowerCase('es-MX')));

  useEffect(() => {
    if (selectedCategoryId || isCreatingCategory || categories.length === 0) return;
    setSelectedCategoryId(categories[0].id);
  }, [categories, isCreatingCategory, selectedCategoryId]);

  useEffect(() => {
    if (!selectedCategory || hydratedCategoryId.current === selectedCategory.id) return;
    hydratedCategoryId.current = selectedCategory.id;
    categoryAttempt.current = null;
    setCategoryConflict(false);
    setCategoryForm({
      name: selectedCategory.name,
      display_order: selectedCategory.display_order,
      status: selectedCategory.status,
      classification_code: selectedCategory.classification_code ?? '',
      configuration_version: selectedCategory.configuration_version,
    });
  }, [selectedCategory]);

  useEffect(() => {
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
      const payload = categoryCommandPayload(categoryForm, !selectedCategoryId);
      const target = selectedCategoryId ? `/categories/${selectedCategoryId}` : '/categories';
      categoryAttempt.current = categoryCommandAttempt(categoryAttempt.current, target, payload, () => crypto.randomUUID());
      return fetchApi<{ id: string }>(target, {
        method: selectedCategoryId ? 'PUT' : 'POST',
        headers: { 'Idempotency-Key': categoryAttempt.current.key },
        body: JSON.stringify(payload),
      });
    },
    onSuccess: async (saved) => {
      const wasCreating = !selectedCategoryId;
      hydratedCategoryId.current = '';
      categoryAttempt.current = null;
      setCategoryConflict(false);
      setIsCreatingCategory(false);
      setSelectedCategoryId(saved.id);
      setNotice({ tone: 'success', text: wasCreating ? 'Grupo creado.' : 'Grupo actualizado.' });
      await refreshWorkspace();
    },
    onError: (reason) => {
      const conflict = Boolean(selectedCategoryId) && reason instanceof ApiError && (reason.status === 409 || reason.code === 'category_version_conflict');
      setCategoryConflict(conflict);
      setNotice({ tone: 'error', text: conflict ? 'El grupo cambió o el comando entró en conflicto. Tu borrador se conserva; recarga para revisar la versión vigente.' : failure(reason) });
    },
  });

  const groupMutation = useMutation({
    mutationFn: (status: 'active' | 'inactive') => fetchApi(`/categories/${selectedCategoryId}/selection-group`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),
    onSuccess: async (_, status) => {
      setNotice({ tone: 'success', text: status === 'active' ? 'Los subgrupos ya se muestran en POS.' : 'Los subgrupos se ocultaron del POS.' });
      await refreshWorkspace();
    },
    onError: (reason) => setNotice({ tone: 'error', text: failure(reason) }),
  });

  const subgroupMutation = useMutation({
    mutationFn: async () => {
      const group = coverage?.group || await fetchApi<{ id: string }>(`/categories/${selectedCategoryId}/selection-group`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      return fetchApi(`/catalog/category-option-groups/${group.id}/values`, {
        method: 'POST',
        body: JSON.stringify({ name: subgroupName.trim().toLocaleUpperCase('es-MX') }),
      });
    },
    onSuccess: async () => {
      setSubgroupName('');
      setNotice({ tone: 'success', text: 'Subgrupo creado.' });
      await refreshWorkspace();
    },
    onError: (reason) => setNotice({ tone: 'error', text: failure(reason) }),
  });

  const updateSubgroupMutation = useMutation({
    mutationFn: (value: SubgroupEditor) => fetchApi(`/catalog/category-option-groups/${coverage?.group?.id}/values/${value.id}`, {
      method: 'PUT',
      body: JSON.stringify({ name: value.name.trim().toLocaleUpperCase('es-MX') }),
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
    hydratedCategoryId.current = '';
    categoryAttempt.current = null;
    setCategoryConflict(false);
    setCategoryForm({ name: '', display_order: categories.length, status: 'active', classification_code: '', configuration_version: 0 });
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
        <button type="button" className="premium-add-btn" disabled={categoryMutation.isPending} onClick={startNewCategory}>
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
                    disabled={categoryMutation.isPending}
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
            <fieldset className="group-detail-form" disabled={categoryMutation.isPending} style={{ border: 0, margin: 0, minWidth: 0 }}>
              <label>
                <span>Nombre del grupo</span>
                <Input value={categoryForm.name} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setCategoryForm({ ...categoryForm, name: event.target.value.toLocaleUpperCase('es-MX') })} placeholder="Ej. CERVEZAS" />
              </label>
              <label>
                <span>Clasificación comercial</span>
                <Select aria-label="Clasificación comercial" value={categoryForm.classification_code} onChange={(event) => setCategoryForm({ ...categoryForm, classification_code: event.target.value as ClassificationCode | '' })}>
                  <option value="">{selectedCategoryId ? 'Pendiente de clasificación' : 'Selecciona una clasificación'}</option>
                  {CLASSIFICATIONS.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
                </Select>
                <small>Se hereda a los productos. No cambia su área de impresión.</small>
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
              <Button variant="primary" onClick={() => categoryMutation.mutate()} disabled={!categoryForm.name.trim() || (!selectedCategoryId && !categoryForm.classification_code) || categoryConflict || categoryMutation.isPending}>
                <Save size={16} /> {categoryMutation.isPending ? 'Guardando…' : 'Guardar grupo'}
              </Button>
              {categoryConflict && <Button variant="secondary" onClick={async () => {
                const refreshed = await categoriesQuery.refetch();
                if (refreshed.isError) return;
                const current = refreshed.data?.find((item) => item.id === selectedCategoryId);
                if (!current) return;
                setCategoryForm({ name: current.name, display_order: current.display_order, status: current.status, classification_code: current.classification_code ?? '', configuration_version: current.configuration_version });
                categoryAttempt.current = null;
                setCategoryConflict(false);
                setNotice({ tone: 'success', text: 'Versión vigente cargada. Revisa los datos antes de guardar.' });
              }}>Descartar borrador y cargar versión vigente</Button>}
            </fieldset>
          </section>

          <section className="premium-card subgroup-panel" aria-label="Catálogo de subgrupos opcional">
            <div className="group-panel-heading inline">
              <div><span>Subgrupos</span><strong>Opcional</strong></div>
              {coverage?.group && <Badge variant={coverage.group.status === 'active' ? 'success' : 'default'}>{coverage.group.status === 'active' ? 'Visible en POS' : 'No visible en POS'}</Badge>}
            </div>

            {!selectedCategoryId ? (
              <div className="group-subgroup-empty large"><FolderTree size={38} /><strong>Guarda primero el grupo</strong><span>Después podrás crear sus subgrupos.</span></div>
            ) : coverageQuery.isLoading ? (
              <div className="group-subgroup-empty large" role="status">Cargando subgrupos…</div>
            ) : coverageQuery.isError ? (
              <div className="group-subgroup-empty large error" role="alert"><AlertCircle size={30} /><strong>No fue posible cargar los subgrupos.</strong><Button variant="secondary" onClick={() => void coverageQuery.refetch()}>Reintentar</Button></div>
            ) : (
              <div className="subgroup-content">
                {!coverage?.group && (
                  <div className="subgroup-intro">
                    <FolderTree size={24} aria-hidden="true" />
                    <div><strong>Este grupo abre productos directamente</strong><span>Agrega el primer subgrupo sólo si ayuda al cajero a encontrar productos más rápido.</span></div>
                  </div>
                )}

                {coverage?.group && (
                  <div className="subgroup-publish">
                    <div>
                      <strong>{coverage.group.status === 'active' ? 'Los subgrupos están visibles en POS' : 'Los productos se muestran directamente'}</strong>
                      <span>{coverage.group.status === 'active'
                        ? 'Ocultarlos conserva los subgrupos y sus asignaciones.'
                        : coverage.complete && activeSubgroupCount > 0
                          ? 'La cobertura está completa y puedes mostrarlos al cajero.'
                          : `${coverage.incomplete_products.length} producto(s) necesitan un subgrupo antes de publicarlos.`}</span>
                    </div>
                    <Button
                      variant={coverage.group.status === 'active' ? 'secondary' : 'primary'}
                      onClick={() => groupMutation.mutate(coverage.group?.status === 'active' ? 'inactive' : 'active')}
                      disabled={groupMutation.isPending || (coverage.group.status !== 'active' && (!coverage.complete || activeSubgroupCount === 0))}
                    >
                      {coverage.group.status === 'active' ? 'Ocultar subgrupos del POS' : 'Mostrar subgrupos en POS'}
                    </Button>
                  </div>
                )}

                <div className="subgroup-list" aria-label="Subgrupos del grupo seleccionado">
                  {!coverage?.values.length ? <p className="subgroup-empty-copy">Aún no hay subgrupos.</p> : coverage.values.map((value) => {
                    const editing = editingSubgroup?.id === value.id ? editingSubgroup : null;
                    return (
                      <div className="subgroup-row" key={value.id}>
                        {editing ? (
                          <div className="subgroup-edit-grid">
                            <Input aria-label={`Nombre de ${value.name}`} value={editing.name} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditingSubgroup({ ...editing, name: event.target.value })} />
                            <div className="subgroup-edit-actions"><button type="button" onClick={() => setEditingSubgroup(null)} aria-label={`Cancelar edición de ${value.name}`}><X size={16} /></button><button type="button" onClick={() => updateSubgroupMutation.mutate(editing)} aria-label={`Guardar ${value.name}`}><Save size={16} /></button></div>
                          </div>
                        ) : (
                          <>
                            <span><strong>{value.name}</strong></span>
                            <Badge variant={value.status === 'active' ? 'success' : 'default'}>{value.status === 'active' ? 'Activo' : value.status === 'inactive' ? 'Inactivo' : 'Archivado'}</Badge>
                            <button type="button" onClick={() => setEditingSubgroup({ id: value.id, name: value.name })} aria-label={`Editar ${value.name}`}><Edit3 size={16} /></button>
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div className="subgroup-create-row">
                  <Input aria-label="Nombre del nuevo subgrupo" value={subgroupName} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setSubgroupName(event.target.value.toLocaleUpperCase('es-MX'))} placeholder="Nombre del subgrupo" />
                  <Button variant="primary" onClick={() => subgroupMutation.mutate()} disabled={!subgroupName.trim() || subgroupMutation.isPending}><Plus size={16} /> Agregar</Button>
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
