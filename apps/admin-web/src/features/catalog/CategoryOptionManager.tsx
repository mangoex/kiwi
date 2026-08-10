import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { Button, Input } from '@restaurantos/ui';
import {
  categoryOptionEditorState,
  categoryOptionEditorHydrationKey,
  categoryOptionValueEditorState,
  type CategoryOptionValueEditorState,
} from './categoryOptionEditorState';

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

  return <main style={{ maxWidth: 1120, padding: 24 }}>
    <h1>Selector previo de categoría</h1>
    <p>Configuración corporativa; no cambia precios, recetas ni disponibilidad de sucursal.</p>
    <label>Categoría<select value={categoryId} onChange={(event) => { setCategoryId(event.target.value); setMessage(''); }}><option value="">Selecciona una categoría</option>{(categoriesQuery.data || []).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
    {categoriesQuery.isLoading || productsQuery.isLoading ? <p>Cargando configuración…</p> : categoriesQuery.isError || productsQuery.isError ? <div role="alert">No fue posible cargar la configuración. <button onClick={refresh}>Reintentar</button></div> : null}
    {categoryId && <>
      {coverageQuery.isLoading ? <p>Cargando cobertura…</p> : coverageQuery.isError ? <div role="alert">No fue posible cargar la cobertura. <button onClick={refresh}>Reintentar</button></div> : <>
        <section style={{ marginTop: 20, padding: 16, border: '1px solid #dbe3ea', borderRadius: 10 }}>
          <h2>Selector previo</h2>
          <label>Código<Input value={code} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setCode(event.target.value)} /></label>
          <label>Nombre visible<Input value={name} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setName(event.target.value)} /></label>
          <label>Estado<select value={groupStatus} onChange={(event) => setGroupStatus(event.target.value as 'active' | 'inactive' | 'archived')}><option value="inactive">Inactivo</option><option value="active">Activo</option><option value="archived">Archivado</option></select></label>
          <Button onClick={() => groupMutation.mutate(groupStatus)} disabled={!code || !name || groupMutation.isPending || (groupStatus === 'active' && !coverage?.complete)}>Guardar selector</Button>
          <Button onClick={() => groupMutation.mutate('active')} disabled={!coverage?.group || !coverage.complete || groupMutation.isPending}>Activar</Button>
          {coverage?.group && <Button onClick={() => groupMutation.mutate('archived')} disabled={groupMutation.isPending}>Archivar selector</Button>}
          {!coverage?.complete && coverage?.group && <p role="alert">La activación se rechaza hasta completar la cobertura.</p>}
        </section>
        {coverage?.group && <section style={{ marginTop: 20, padding: 16, border: '1px solid #dbe3ea', borderRadius: 10 }}>
          <h2>Opciones</h2>
          <label>Código<Input value={valueCode} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValueCode(event.target.value)} /></label>
          <label>Nombre<Input value={valueName} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValueName(event.target.value)} /></label>
          <Button onClick={() => valueMutation.mutate()} disabled={!valueCode || !valueName || valueMutation.isPending}>Agregar opción</Button>
          <ul>{coverage.values.map((value) => {
            const editing = editingValue?.id === value.id ? editingValue : null;
            return <li key={value.id}>{editing ? <div>
              <label>Código<Input aria-label={`Código de ${value.name}`} value={editing.code} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditingValue({ ...editing, code: event.target.value })} /></label>
              <label>Nombre<Input aria-label={`Nombre de ${value.name}`} value={editing.name} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditingValue({ ...editing, name: event.target.value })} /></label>
              <label>Orden<Input type="number" aria-label={`Orden de ${value.name}`} value={editing.displayOrder} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditingValue({ ...editing, displayOrder: Number(event.target.value) })} /></label>
              <label>Estado<select aria-label={`Estado de ${value.name}`} value={editing.status} onChange={(event) => setEditingValue({ ...editing, status: event.target.value as Value['status'] })}><option value="active">Activo</option><option value="inactive">Inactivo</option><option value="archived">Archivado</option></select></label>
              <Button onClick={() => updateValueMutation.mutate(editing)} disabled={updateValueMutation.isPending || !editing.code || !editing.name}>Guardar opción</Button>
              <Button onClick={() => setEditingValue(null)} disabled={updateValueMutation.isPending}>Cancelar</Button>
            </div> : <div>{value.name} · {value.code} · orden {value.display_order} · {value.status} <Button onClick={() => setEditingValue(categoryOptionValueEditorState(value))} disabled={updateValueMutation.isPending}>Editar</Button></div>}</li>;
          })}</ul>
        </section>}
        {coverage?.group && <section style={{ marginTop: 20, padding: 16, border: '1px solid #dbe3ea', borderRadius: 10 }}>
          <h2>Cobertura</h2>
          <p>{coverage.complete ? 'Cobertura completa.' : `${coverage.incomplete_products.length} Productos incompletos.`}</p>
          <h3>Productos de la categoría</h3>
          {!coverage.complete && <p role="alert">{coverage.incomplete_products.length} producto(s) incompleto(s).</p>}
          {coverage.products.map((product) => <label key={product.id} style={{ display: 'block', color: product.incomplete ? '#b91c1c' : undefined }}>{product.name}{product.incomplete ? ' · Incompleto' : ''} <select value={product.assignment?.value_id || ''} onChange={(event) => event.target.value && assignmentMutation.mutate({ productId: product.id, optionValueId: event.target.value })}><option value="">Sin asignación</option>{coverage.values.filter((value) => value.status === 'active').map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>)}
        </section>}
      </>}
    </>}
    {message && <p role="status">{message} <button onClick={refresh}>Reintentar</button></p>}
  </main>;
}
