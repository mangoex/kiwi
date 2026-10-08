import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import {
  Button,
  discardWorkspaceSnapshot,
  Input,
  readWorkspaceSnapshot,
  registerWorkspaceSnapshot,
} from '@restaurantos/ui';
import { ChevronDown, ChevronRight, Layers3, Plus, Save } from 'lucide-react';
import { getSessionUser } from '../../lib/branchContext';
import { clearWorkspaceReturn, rememberWorkspaceReturn } from '../../lib/workspaceReturn';
import { ModifierManager } from './ModifierManager';
import {
  categorySelectionState,
  toggleCategoryProducts,
  toggleProductSelection,
} from './orderCommentProductScope';
import './VariationNotes.css';
import './SharedModifierWorkspace.css';

type Product = {
  id: string;
  name: string;
  sku: string;
  category_id?: string;
  station?: string;
  status: string;
  catalog_scope?: string;
};
type Category = { id: string; name: string; status: string; display_order?: number };
type ModifierSet = {
  id: string;
  name: string;
  version: number;
  station: string;
  group_count: number;
  products: Array<{ id: string; name: string; sku: string; category_id: string; station: string }>;
};
type MutationIntent = { key: string; body: string };
type ScopeMutationIntent = MutationIntent & { setId: string };

function recoveryBody<T>(intent?: MutationIntent): T | null {
  if (!intent) return null;
  try {
    return JSON.parse(intent.body) as T;
  } catch {
    return null;
  }
}

function ProductScope({
  products,
  categories,
  selected,
  onChange,
}: {
  products: Product[];
  categories: Category[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const [expanded, setExpanded] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const active = products.filter((product) => product.status === 'active' && product.catalog_scope !== 'branch');
  const selectedStation = active.find((product) => selected.includes(product.id))?.station;
  const visibleCategories = categories
    .filter((category) => category.status === 'active')
    .filter((category) => active.some((product) => product.category_id === category.id))
    .sort((a, b) => (a.display_order || 0) - (b.display_order || 0) || a.name.localeCompare(b.name));

  return <div style={{ display: 'grid', gap: 8 }}>
    <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar producto o SKU" />
    <p style={{ margin: 0, color: '#64748b', fontSize: 13 }}>
      Los productos de una configuración comparten estación de preparación. Puedes crear otro set para una estación distinta.
    </p>
    {visibleCategories.map((category) => {
      const categoryProducts = active.filter((product) => product.category_id === category.id);
      const compatibleProducts = categoryProducts.filter((product) => !selectedStation || product.station === selectedStation);
      const ids = compatibleProducts.map((product) => product.id);
      const state = categorySelectionState(ids, selected);
      const open = expanded.includes(category.id);
      return <section key={category.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 10 }}>
          <input
            type="checkbox"
            aria-label={`Seleccionar productos de ${category.name}`}
            aria-checked={state === 'partial' ? 'mixed' : state === 'all'}
            ref={(node) => { if (node) node.indeterminate = state === 'partial'; }}
            checked={state === 'all' && ids.length > 0}
            disabled={ids.length === 0}
            onChange={(event) => onChange(toggleCategoryProducts(selected, ids, event.target.checked))}
          />
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setExpanded((current) => current.includes(category.id)
              ? current.filter((id) => id !== category.id)
              : [...current, category.id])}
            style={{ flex: 1, border: 0, background: 'transparent', display: 'flex', gap: 8, cursor: 'pointer', textAlign: 'left' }}
          >
            <strong style={{ flex: 1 }}>{category.name}</strong>
            <span style={{ color: '#64748b' }}>{categoryProducts.length}</span>
            {open ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
          </button>
        </div>
        {open && <div style={{ display: 'grid', gap: 7, padding: '0 12px 12px 38px' }}>
          {categoryProducts
            .filter((product) => {
              const term = search.trim().toLocaleLowerCase();
              return !term || product.name.toLocaleLowerCase().includes(term) || product.sku.toLocaleLowerCase().includes(term);
            })
            .map((product) => {
              const compatible = !selectedStation || product.station === selectedStation || selected.includes(product.id);
              return <label key={product.id} style={{ display: 'flex', gap: 8, color: compatible ? '#334155' : '#94a3b8' }}>
                <input
                  type="checkbox"
                  checked={selected.includes(product.id)}
                  disabled={!compatible}
                  onChange={(event) => onChange(toggleProductSelection(selected, product.id, event.target.checked))}
                />
                <span style={{ flex: 1 }}>{product.name}</span><small>{product.sku}</small>
              </label>;
            })}
        </div>}
      </section>;
    })}
    <strong style={{ color: selected.length ? '#047857' : '#64748b' }}>
      {selected.length} {selected.length === 1 ? 'producto seleccionado' : 'productos seleccionados'}
    </strong>
  </div>;
}

export default function SharedModifierWorkspace() {
  const client = useQueryClient();
  const actorId = getSessionUser().id || 'unknown';
  const createRecoveryKey = `shared-modifier-create:${actorId}`;
  const scopeRecoveryKey = `shared-modifier-scope:${actorId}`;
  const [createRecovery] = useState(() => readWorkspaceSnapshot<MutationIntent>(createRecoveryKey));
  const [scopeRecovery] = useState(() => readWorkspaceSnapshot<ScopeMutationIntent>(scopeRecoveryKey));
  const [createDraft] = useState(() => (
    recoveryBody<{ name: string; product_ids: string[] }>(createRecovery)
  ));
  const [scopeDraft] = useState(() => (
    recoveryBody<{ expected_version: number; product_ids: string[] }>(scopeRecovery)
  ));
  const [selectedSetId, setSelectedSetId] = useState(scopeRecovery?.setId || '');
  const [creating, setCreating] = useState(Boolean(createDraft));
  const [name, setName] = useState(createDraft?.name || '');
  const [newProductIds, setNewProductIds] = useState<string[]>(createDraft?.product_ids || []);
  const [scopeProductIds, setScopeProductIds] = useState<string[]>([]);
  const [message, setMessage] = useState(
    createRecovery || scopeRecovery
      ? 'Recuperamos una operación pendiente. Reintenta para confirmar el mismo comando.'
      : '',
  );
  const createIntent = useRef<MutationIntent | null>(createRecovery || null);
  const scopeIntent = useRef<ScopeMutationIntent | null>(scopeRecovery || null);

  const products = useQuery<Product[]>({ queryKey: ['products'], queryFn: () => fetchApi('/catalog/products') });
  const categories = useQuery<Category[]>({ queryKey: ['categories'], queryFn: () => fetchApi('/categories') });
  const sets = useQuery<ModifierSet[]>({ queryKey: ['modifier-sets'], queryFn: () => fetchApi('/catalog/modifier-sets') });
  const selectedSet = useMemo(
    () => (sets.data || []).find((item) => item.id === selectedSetId) || null,
    [selectedSetId, sets.data],
  );

  useEffect(() => {
    if (!selectedSetId && sets.data?.length) setSelectedSetId(sets.data[0].id);
  }, [selectedSetId, sets.data]);
  useEffect(() => {
    if (!selectedSet) return;
    if (scopeIntent.current?.setId === selectedSet?.id && scopeDraft) {
      setScopeProductIds(scopeDraft.product_ids);
      return;
    }
    setScopeProductIds(selectedSet.products.map((product) => product.id));
    scopeIntent.current = null;
  }, [scopeDraft, selectedSet]);
  useEffect(() => {
    discardWorkspaceSnapshot(createRecoveryKey);
    return registerWorkspaceSnapshot(createRecoveryKey, () => createIntent.current);
  }, [createRecoveryKey]);
  useEffect(() => {
    discardWorkspaceSnapshot(scopeRecoveryKey);
    return registerWorkspaceSnapshot(scopeRecoveryKey, () => scopeIntent.current);
  }, [scopeRecoveryKey]);

  const changeName = (value: string) => {
    createIntent.current = null;
    setName(value);
  };
  const changeNewProducts = (ids: string[]) => {
    createIntent.current = null;
    setNewProductIds(ids);
  };
  const changeScopeProducts = (ids: string[]) => {
    scopeIntent.current = null;
    setScopeProductIds(ids);
  };

  const createSet = useMutation({
    mutationFn: () => {
      createIntent.current ??= {
        key: crypto.randomUUID(),
        body: JSON.stringify({ name: name.trim(), product_ids: newProductIds }),
      };
      rememberWorkspaceReturn('/modifiers');
      return fetchApi<ModifierSet>('/catalog/modifier-sets', {
        method: 'POST',
        headers: { 'Idempotency-Key': createIntent.current.key },
        body: createIntent.current.body,
      });
    },
    onSuccess: async (created) => {
      createIntent.current = null;
      clearWorkspaceReturn('/modifiers');
      discardWorkspaceSnapshot(createRecoveryKey);
      await client.invalidateQueries({ queryKey: ['modifier-sets'] });
      setSelectedSetId(created.id);
      setCreating(false);
      setName('');
      setNewProductIds([]);
      setMessage('Configuración compartida creada. Ahora agrega sus grupos y opciones.');
    },
    onError: (error) => setMessage(error instanceof ApiError ? error.message : 'No fue posible crear la configuración.'),
  });
  const saveScope = useMutation({
    mutationFn: () => {
      scopeIntent.current ??= {
        setId: selectedSet!.id,
        key: crypto.randomUUID(),
        body: JSON.stringify({
          expected_version: selectedSet!.version,
          product_ids: scopeProductIds,
        }),
      };
      rememberWorkspaceReturn('/modifiers');
      return fetchApi<{ version: number }>(`/catalog/modifier-sets/${selectedSet!.id}/products`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': scopeIntent.current.key },
        body: scopeIntent.current.body,
      });
    },
    onSuccess: async () => {
      scopeIntent.current = null;
      clearWorkspaceReturn('/modifiers');
      discardWorkspaceSnapshot(scopeRecoveryKey);
      await client.invalidateQueries({ queryKey: ['modifier-sets'] });
      await client.invalidateQueries({ queryKey: ['modifier-configuration', `/catalog/modifier-sets/${selectedSet!.id}/configuration`] });
      setMessage('Productos relacionados actualizados. Las ventas anteriores no cambiaron.');
    },
    onError: (error) => setMessage(error instanceof ApiError ? error.message : 'No fue posible actualizar los productos.'),
  });

  const updateKnownVersion = (version: number) => {
    client.setQueryData<ModifierSet[]>(['modifier-sets'], (current) => current?.map((item) => (
      item.id === selectedSetId ? { ...item, version } : item
    )));
  };

  if (products.isLoading || categories.isLoading || sets.isLoading) return <p role="status">Cargando modificadores compartidos…</p>;
  if (products.isError || categories.isError || sets.isError) return <p role="alert">No fue posible cargar el catálogo compartido.</p>;

  return <div className="premium-catalog-page">
    <div className="premium-page-header">
      <div><h1>Modificadores</h1><p>Configura grupos una sola vez y relaciónalos con varios productos.</p></div>
      <Button variant="primary" onClick={() => setCreating((value) => !value)}><Plus size={16} /> Nuevo set</Button>
    </div>
    {message && <p className="admin-catalog-message" role="status">{message}</p>}
    {creating && <section style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: 20, marginBottom: 18 }}>
      <h2>Nueva configuración compartida</h2>
      <label className="premium-form-group">Nombre
        <Input value={name} onChange={(event) => changeName(event.target.value)} placeholder="Ej. Aderezos para ensaladas" />
      </label>
      <ProductScope products={products.data || []} categories={categories.data || []} selected={newProductIds} onChange={changeNewProducts} />
      <div style={{ marginTop: 14 }}><Button disabled={!name.trim() || !newProductIds.length || createSet.isPending} onClick={() => createSet.mutate()}><Save size={16} /> Crear configuración</Button></div>
    </section>}
    <div className="shared-modifier-layout">
      <aside style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: 12 }}>
        <strong style={{ display: 'block', padding: 8 }}>Configuraciones</strong>
        {(sets.data || []).length === 0 && <p style={{ color: '#64748b', padding: 8 }}>Todavía no hay configuraciones compartidas.</p>}
        {(sets.data || []).map((item) => <button key={item.id} type="button" onClick={() => setSelectedSetId(item.id)} style={{ width: '100%', padding: 11, marginBottom: 5, borderRadius: 9, border: item.id === selectedSetId ? '1px solid #10b981' : '1px solid transparent', background: item.id === selectedSetId ? '#ecfdf5' : 'transparent', textAlign: 'left', cursor: 'pointer' }}>
          <Layers3 size={16} /> <strong>{item.name}</strong>
          <small style={{ display: 'block', marginTop: 4, color: '#64748b' }}>{item.products.length} productos · {item.group_count} grupos · v{item.version}</small>
        </button>)}
      </aside>
      <main style={{ minWidth: 0 }}>
        {selectedSet && <>
          <section style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: 20, marginBottom: 18 }}>
            <h2>Productos relacionados con {selectedSet.name}</h2>
            <ProductScope products={products.data || []} categories={categories.data || []} selected={scopeProductIds} onChange={changeScopeProducts} />
            <div style={{ marginTop: 14 }}><Button disabled={!scopeProductIds.length || saveScope.isPending || JSON.stringify([...scopeProductIds].sort()) === JSON.stringify(selectedSet.products.map((product) => product.id).sort())} onClick={() => saveScope.mutate()}><Save size={16} /> Guardar productos</Button></div>
          </section>
          <ModifierManager
            key={selectedSet.id}
            productId={selectedSet.id}
            productName={selectedSet.name}
            endpointBase={`/catalog/modifier-sets/${selectedSet.id}/configuration`}
            allowProductComponents={false}
            showCompoundTools={false}
            onSaved={updateKnownVersion}
          />
        </>}
      </main>
    </div>
  </div>;
}
