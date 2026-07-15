import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Plus, Search } from 'lucide-react';
import { Button, Input, Modal } from '@restaurantos/ui';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { centsToMxn, mxnToCentsExact, surchargeMxnError } from './ingredientVariationMoney';

interface Product { id: string; name: string; sku: string; category_id?: string; status?: string; }
interface Category { id: string; name: string; status: string; }
interface Ingredient { id: string; name: string; sku: string; unit_code?: string; item_type: string; status: string; }
interface Assignment { product_id: string; product_name: string; product_sku: string; category_name: string; allow_add: boolean; add_quantity: string; charge_additional: boolean; add_price_delta_cents: number; }
interface Extra { id: string; inventory_item_name: string; inventory_item_sku: string; unit_code: string; add_label: string; portion_quantity?: string; sale_price_cents?: number; station?: 'kitchen' | 'drinks' | 'packing' | null; display_order?: number; status: 'active' | 'archived' | 'needs_review'; related_products: number; active_add_assignments: number; active_remove_assignments: number; warnings: string[]; assignments?: Assignment[]; }
interface Form { add_quantity: string; charge_additional: boolean; add_price_delta_mxn: string; }
interface CanonicalForm { portion_quantity: string; sale_price_mxn: string; station: 'kitchen' | 'drinks' | 'packing'; display_order: string; }
interface Preview { product_id: string; product_name: string; sku?: string; category?: string; compatible: boolean; reason?: string; }

const emptyForm: Form = { add_quantity: '1', charge_additional: false, add_price_delta_mxn: '' };
const emptyCanonicalForm: CanonicalForm = { portion_quantity: '1', sale_price_mxn: '0.00', station: 'kitchen', display_order: '0' };
const card: React.CSSProperties = { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 16 };
const errorMessage = (reason: unknown, fallback: string) => reason instanceof ApiError ? reason.message : fallback;
const assignmentPayload = (form: Form, productIds: string[], categoryIds: string[]) => ({ product_ids: productIds, category_ids: categoryIds, allow_add: true, allow_remove: false, add_quantity: form.add_quantity, remove_quantity: '0', charge_additional: form.charge_additional, add_price_delta_cents: form.charge_additional ? mxnToCentsExact(form.add_price_delta_mxn) : 0 });
type AssignmentPayload = ReturnType<typeof assignmentPayload>;

export function ingredientExtraPreviewFingerprint(variationId: string, form: Form, productIds: string[], categoryIds: string[]): string | null {
  try {
    return JSON.stringify({ variation_id: variationId, product_ids: [...new Set(productIds)].sort(), category_ids: [...new Set(categoryIds)].sort(), add_quantity: form.add_quantity.trim(), charge_additional: form.charge_additional, add_price_delta_cents: form.charge_additional ? mxnToCentsExact(form.add_price_delta_mxn) : 0 });
  } catch {
    return null;
  }
}

export default function IngredientExtras() {
  const client = useQueryClient();
  const [search, setSearch] = useState(''); const [status, setStatus] = useState('active');
  const [createOpen, setCreateOpen] = useState(false); const [detailId, setDetailId] = useState('');
  const [itemSearch, setItemSearch] = useState(''); const [itemId, setItemId] = useState(''); const [label, setLabel] = useState('');
  const [portionQuantity, setPortionQuantity] = useState('1'); const [salePriceMxn, setSalePriceMxn] = useState(''); const [station, setStation] = useState<CanonicalForm['station']>('kitchen'); const [displayOrder, setDisplayOrder] = useState('0');
  const [feedback, setFeedback] = useState(''); const [operationalError, setOperationalError] = useState('');
  const extras = useQuery<Extra[]>({ queryKey: ['ingredient-extras', search, status], queryFn: () => fetchApi(`/catalog/ingredient-variations?search=${encodeURIComponent(search)}&status=${status}`) });
  const items = useQuery<Ingredient[]>({ queryKey: ['ingredient-extra-items', itemSearch], queryFn: () => fetchApi('/inventory/items'), enabled: createOpen });
  const inventory = useMemo(() => (items.data || []).filter((item) => item.item_type === 'ingredient' && item.status === 'active' && `${item.name} ${item.sku}`.toLowerCase().includes(itemSearch.toLowerCase())), [items.data, itemSearch]);
  const visible = (extras.data || []).filter((extra) => extra.active_add_assignments > 0 || extra.related_products === 0);
  const chosen = inventory.find((item) => item.id === itemId);
  const refresh = () => client.invalidateQueries({ queryKey: ['ingredient-extras'] });
  const resetCreate = () => { setCreateOpen(false); setItemSearch(''); setItemId(''); setLabel(''); setPortionQuantity('1'); setSalePriceMxn(''); setStation('kitchen'); setDisplayOrder('0'); };
  const openCreate = () => { resetCreate(); setFeedback(''); setOperationalError(''); setCreateOpen(true); };
  const create = useMutation<Extra>({ mutationFn: () => {
    const priceCents = mxnToCentsExact(salePriceMxn);
    if (priceCents < 0) throw new Error('El precio de venta debe ser un importe válido.');
    return fetchApi('/catalog/ingredient-variations', { method: 'POST', body: JSON.stringify({ inventory_item_id: itemId, add_label: label || undefined, portion_quantity: portionQuantity, sale_price_cents: priceCents, station, display_order: Number(displayOrder) }) });
  }, onMutate: () => setOperationalError(''), onSuccess: (extra) => { resetCreate(); setDetailId(extra.id); setFeedback('Ingrediente adicional corporativo creado. Está disponible para cualquier producto.'); void refresh(); }, onError: (reason) => setOperationalError(errorMessage(reason, 'No fue posible crear el ingrediente adicional.')) });
  const statusMutation = useMutation({ mutationFn: (extra: Extra) => fetchApi(`/catalog/ingredient-variations/${extra.id}`, { method: 'PUT', body: JSON.stringify({ status: extra.status === 'active' ? 'archived' : 'active' }) }), onMutate: () => setOperationalError(''), onSuccess: () => { setOperationalError(''); void refresh(); }, onError: (reason) => setOperationalError(errorMessage(reason, 'No fue posible cambiar el estado del ingrediente adicional.')) });

  return <div style={{ padding: 24, maxWidth: 1120, background: '#f8fafc' }}>
    <header style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 18 }}><Plus color="#10b981" /><div><h1 style={{ margin: 0 }}>Ingredientes adicionales</h1><p style={{ color: '#64748b', marginBottom: 0 }}>Porciones extra con cantidad exacta, inventario y costo interno. El cargo al cliente es opcional y explícito.</p></div></header>
    <section style={{ ...card, display: 'flex', gap: 8, flexWrap: 'wrap' }}><div style={{ position: 'relative', flex: 1, minWidth: 220 }}><Search size={16} style={{ left: 10, top: 11, position: 'absolute', color: '#64748b' }} /><Input value={search} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setSearch(event.target.value)} placeholder="Buscar adicional, insumo o SKU" style={{ paddingLeft: 32 }} /></div><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="active">Activos</option><option value="needs_review">Requieren revisión</option><option value="archived">Archivados</option></select><Button onClick={openCreate}>Nuevo ingrediente adicional</Button></section>
    {operationalError && <p role="alert" style={{ color: '#b91c1c' }}>{operationalError}</p>}
    {extras.isLoading ? <p>Cargando ingredientes adicionales…</p> : extras.isError ? <div role="alert"><p>{errorMessage(extras.error, 'No fue posible cargar ingredientes adicionales.')}</p><Button onClick={() => void extras.refetch()}>Reintentar</Button></div> : visible.length === 0 ? <p style={{ color: '#64748b' }}>No hay ingredientes adicionales para este filtro.</p> : <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>{visible.map((extra) => <article key={extra.id} style={card}><strong>{extra.inventory_item_name}</strong> <span style={{ color: '#64748b' }}>· {extra.inventory_item_sku} · {extra.unit_code}</span><p>Porción: {extra.portion_quantity || 'Sin configurar'} · Precio: {extra.sale_price_cents == null ? 'Sin configurar' : `$${centsToMxn(extra.sale_price_cents)}`} · Estación: {extra.station || 'Sin configurar'}</p><p>Adicional: {extra.active_add_assignments ? extra.add_label : 'Disponible para cualquier producto'} · {extra.related_products} productos relacionados</p><p>{extra.warnings.length ? extra.warnings.join(', ') : 'Sin advertencias'}</p>{extra.active_remove_assignments > 0 && <p role="note" style={{ color: '#92400e' }}><AlertTriangle size={14} /> Acciones de retiro heredadas no disponibles: crea “Sin …” en Comentarios del pedido.</p>}<div style={{ display: 'flex', gap: 8 }}><Button variant="secondary" onClick={() => setDetailId(extra.id)}>Editar y productos</Button><Button variant="secondary" disabled={statusMutation.isPending || extra.status === 'needs_review'} onClick={() => statusMutation.mutate(extra)}>{extra.status === 'active' ? 'Archivar' : 'Reactivar'}</Button></div></article>)}</div>}
    <Modal isOpen={createOpen} onClose={resetCreate} title="Nuevo ingrediente adicional"><div style={{ display: 'grid', gap: 10 }}>{operationalError && <p role="alert">{operationalError}</p>}<label>Buscar insumo por nombre o SKU<Input value={itemSearch} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setItemSearch(event.target.value)} placeholder="Aguacate, AGU-01…" /></label>{inventory.map((item) => <button key={item.id} type="button" onClick={() => { setItemId(item.id); setLabel(`Porción extra de ${item.name}`); setOperationalError(''); }} style={{ textAlign: 'left', border: itemId === item.id ? '2px solid #10b981' : '1px solid #e2e8f0', borderRadius: 8, padding: 8 }}>{item.name} · {item.sku} · {item.unit_code || 'unidad base'}</button>)}<label>Etiqueta visible<Input value={label} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setLabel(event.target.value)} placeholder={chosen ? `Porción extra de ${chosen.name}` : 'Porción extra de…'} /></label><label>Cantidad Decimal<Input inputMode="decimal" value={portionQuantity} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setPortionQuantity(event.target.value)} placeholder="0.250" /></label><label>Precio de venta (MXN)<Input inputMode="decimal" value={salePriceMxn} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setSalePriceMxn(event.target.value)} placeholder="15.00" /></label><label>Estación<select value={station} onChange={(event) => setStation(event.target.value as CanonicalForm['station'])} style={{ width: '100%', padding: 9, border: '1px solid #cbd5e1', borderRadius: 8 }}><option value="kitchen">Cocina</option><option value="drinks">Bebidas</option><option value="packing">Empaque</option></select></label><label>Orden de despliegue<Input inputMode="numeric" value={displayOrder} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setDisplayOrder(event.target.value)} /></label><p style={{ color: '#64748b' }}>La configuración corporativa aplica a cualquier producto; no existen overrides por sucursal.</p><Button disabled={!itemId || !portionQuantity.trim() || !salePriceMxn.trim() || create.isPending} onClick={() => create.mutate()}>Crear adicional</Button></div></Modal>
    {detailId && <ExtraDetail key={detailId} id={detailId} onClose={() => setDetailId('')} onFeedback={setFeedback} />}{feedback && <p role="status">{feedback}</p>}
  </div>;
}

function ExtraDetail({ id, onClose, onFeedback }: { id: string; onClose: () => void; onFeedback: (value: string) => void }) {
  const client = useQueryClient();
  const [productIds, setProductIds] = useState<string[]>([]);
  const [categoryIds, setCategoryIds] = useState<string[]>([]);
  const [form, setForm] = useState<Form>(emptyForm);
  const [preview, setPreview] = useState<Preview[]>([]);
  const [previewFingerprint, setPreviewFingerprint] = useState<string | null>(null);
  const [editing, setEditing] = useState<Assignment | null>(null);
  const [editForm, setEditForm] = useState<Form>(emptyForm);
  const [canonicalForm, setCanonicalForm] = useState<CanonicalForm>(emptyCanonicalForm);
  const [mainError, setMainError] = useState('');
  const [editError, setEditError] = useState('');
  const detail = useQuery<Extra>({ queryKey: ['ingredient-extra', id], queryFn: () => fetchApi(`/catalog/ingredient-variations/${id}`) });
  const products = useQuery<Product[]>({ queryKey: ['products'], queryFn: () => fetchApi('/catalog/products') });
  const categories = useQuery<Category[]>({ queryKey: ['categories'], queryFn: () => fetchApi('/categories') });
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['ingredient-extras'] });
    void client.invalidateQueries({ queryKey: ['ingredient-extra', id] });
  };
  const currentFingerprint = ingredientExtraPreviewFingerprint(id, form, productIds, categoryIds);
  const currentPayload = (): AssignmentPayload => assignmentPayload(form, productIds, categoryIds);
  const clearPreview = () => { setPreview([]); setPreviewFingerprint(null); };
  useEffect(() => {
    if (previewFingerprint && previewFingerprint !== currentFingerprint) clearPreview();
  }, [currentFingerprint, previewFingerprint]);

  const previewMutation = useMutation<Preview[], Error, { fingerprint: string; payload: AssignmentPayload }>({
    mutationFn: ({ payload }) => fetchApi(`/catalog/ingredient-variations/${id}/assignments/preview`, { method: 'POST', body: JSON.stringify(payload) }),
    onMutate: () => { setMainError(''); clearPreview(); },
    onSuccess: (rows, request) => { setPreview(rows); setPreviewFingerprint(request.fingerprint); setMainError(''); },
    onError: (reason) => setMainError(errorMessage(reason, 'No fue posible generar el preview.')),
  });
  const apply = useMutation<unknown, Error, { fingerprint: string; payload: AssignmentPayload }>({
    mutationFn: ({ fingerprint, payload }) => {
      if (!previewFingerprint || !currentFingerprint || fingerprint !== previewFingerprint || fingerprint !== currentFingerprint) {
        throw new Error('La configuración cambió después del preview. Solicita un nuevo preview antes de relacionar.');
      }
      return fetchApi(`/catalog/ingredient-variations/${id}/assignments`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify(payload),
      });
    },
    onMutate: () => setMainError(''),
    onSuccess: () => {
      setProductIds([]); setCategoryIds([]); setForm(emptyForm); clearPreview(); setMainError('');
      onFeedback('Productos relacionados.'); refresh();
    },
    onError: (reason) => setMainError(errorMessage(reason, 'No fue posible relacionar los productos.')),
  });
  const update = useMutation({
    mutationFn: () => {
      if (!editing) throw new Error('No hay relación seleccionada.');
      return fetchApi(`/catalog/ingredient-variations/${id}/assignments/${editing.product_id}`, {
        method: 'PUT', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify(assignmentPayload(editForm, [], [])),
      });
    },
    onMutate: () => setEditError(''),
    onSuccess: () => { setEditing(null); setEditError(''); onFeedback('Relación actualizada.'); refresh(); },
    onError: (reason) => setEditError(errorMessage(reason, 'No fue posible actualizar la relación.')),
  });
  const unlink = useMutation({
    mutationFn: (assignment: Assignment) => fetchApi(`/catalog/ingredient-variations/${id}/assignments/${assignment.product_id}`, { method: 'DELETE' }),
    onMutate: () => setMainError(''), onSuccess: () => { setMainError(''); refresh(); },
    onError: (reason) => setMainError(errorMessage(reason, 'No fue posible desvincular la relación.')),
  });
  useEffect(() => {
    if (!detail.data) return;
    setCanonicalForm({
      portion_quantity: String(detail.data.portion_quantity || '1'),
      sale_price_mxn: detail.data.sale_price_cents == null ? '0.00' : centsToMxn(detail.data.sale_price_cents),
      station: detail.data.station || 'kitchen',
      display_order: String(detail.data.display_order || 0),
    });
  }, [detail.data]);
  const canonicalUpdate = useMutation({
    mutationFn: () => fetchApi(`/catalog/ingredient-variations/${id}`, {
      method: 'PUT',
      body: JSON.stringify({
        portion_quantity: canonicalForm.portion_quantity,
        sale_price_cents: mxnToCentsExact(canonicalForm.sale_price_mxn),
        station: canonicalForm.station,
        display_order: Number(canonicalForm.display_order),
      }),
    }),
    onMutate: () => setMainError(''),
    onSuccess: () => { setMainError(''); onFeedback('Configuración corporativa actualizada.'); refresh(); },
    onError: (reason) => setMainError(errorMessage(reason, 'No fue posible actualizar la configuración corporativa.')),
  });
  const activeProducts = (products.data || []).filter((product) => !product.status || product.status === 'active');
  const currentPreview = previewFingerprint === currentFingerprint ? preview : [];
  const incompatible = currentPreview.filter((row) => !row.compatible);
  const surchargeError = surchargeMxnError(form.charge_additional, form.add_price_delta_mxn);
  const editSurchargeError = surchargeMxnError(editForm.charge_additional, editForm.add_price_delta_mxn);
  const toggle = (values: string[], value: string) => values.includes(value) ? values.filter((entry) => entry !== value) : [...values, value];
  const previewApproved = Boolean(previewFingerprint) && previewFingerprint === currentFingerprint && currentPreview.length > 0 && incompatible.length === 0;
  const requestPreview = () => {
    if (!currentFingerprint) { setMainError('Configura un importe válido antes de solicitar preview.'); return; }
    previewMutation.mutate({ fingerprint: currentFingerprint, payload: currentPayload() });
  };
  const requestApply = () => {
    if (!previewApproved || !currentFingerprint) {
      setMainError('La configuración cambió después del preview. Solicita un nuevo preview antes de relacionar.');
      return;
    }
    apply.mutate({ fingerprint: currentFingerprint, payload: currentPayload() });
  };
  const openEdit = (assignment: Assignment) => {
    setEditing(assignment); setEditError('');
    setEditForm({ add_quantity: assignment.add_quantity, charge_additional: assignment.charge_additional, add_price_delta_mxn: centsToMxn(assignment.add_price_delta_cents) });
  };

  return <>
    <Modal isOpen onClose={onClose} title="Productos relacionados">
      <div style={{ display: 'grid', gap: 12 }}>
        <p>Se relacionarán los productos activos actuales; los productos futuros no se agregan automáticamente.</p>
        {mainError && <p role="alert">{mainError}</p>}
        {detail.isLoading ? <p>Cargando detalle…</p> : detail.isError ? <p role="alert">{errorMessage(detail.error, 'No fue posible cargar el detalle.')} <button onClick={() => void detail.refetch()}>Reintentar</button></p> : <>
          <section style={card}>
            <h3>Configuración corporativa</h3>
            <p style={{ color: '#64748b' }}>Esta porción, precio y estación aplican a cualquier producto relacionado o no relacionado.</p>
            <div style={{ display: 'grid', gap: 8 }}>
              <label>Cantidad Decimal<Input inputMode="decimal" value={canonicalForm.portion_quantity} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setCanonicalForm({ ...canonicalForm, portion_quantity: event.target.value })} /></label>
              <label>Precio de venta (MXN)<Input inputMode="decimal" value={canonicalForm.sale_price_mxn} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setCanonicalForm({ ...canonicalForm, sale_price_mxn: event.target.value })} /></label>
              <label>Estación<select value={canonicalForm.station} onChange={(event) => setCanonicalForm({ ...canonicalForm, station: event.target.value as CanonicalForm['station'] })} style={{ width: '100%', padding: 9, border: '1px solid #cbd5e1', borderRadius: 8 }}><option value="kitchen">Cocina</option><option value="drinks">Bebidas</option><option value="packing">Empaque</option></select></label>
              <label>Orden de despliegue<Input inputMode="numeric" value={canonicalForm.display_order} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setCanonicalForm({ ...canonicalForm, display_order: event.target.value })} /></label>
              <Button disabled={canonicalUpdate.isPending || !canonicalForm.portion_quantity.trim() || !canonicalForm.sale_price_mxn.trim()} onClick={() => canonicalUpdate.mutate()}>Guardar configuración corporativa</Button>
            </div>
          </section>
          <section style={card}>
            <h3>Relaciones existentes</h3>
            {detail.data?.assignments?.length ? detail.data.assignments.filter((assignment) => assignment.allow_add).map((assignment) => <div key={assignment.product_id} style={{ borderTop: '1px solid #e2e8f0', padding: 8 }}>
              <strong>{assignment.product_name}</strong> · {assignment.product_sku} · {assignment.category_name}
              <p>Adicional: {assignment.add_quantity} {detail.data?.unit_code} · {assignment.charge_additional ? `+$${centsToMxn(assignment.add_price_delta_cents)}` : 'Sin cargo'}</p>
              <Button variant="secondary" onClick={() => openEdit(assignment)}>Editar</Button>{' '}
              <Button variant="secondary" disabled={unlink.isPending} onClick={() => unlink.mutate(assignment)}>Desvincular</Button>
            </div>) : <p>Sin productos relacionados.</p>}
          </section>
          <section style={card}>
            <h3>Agregar productos</h3><label>Productos activos actuales</label>
            {activeProducts.map((product) => <label key={product.id}><input type="checkbox" checked={productIds.includes(product.id)} onChange={() => setProductIds((current) => toggle(current, product.id))} /> {product.name} · {product.sku}</label>)}
            <h4>Categorías</h4>
            {(categories.data || []).filter((category) => category.status === 'active').map((category) => <label key={category.id}><input type="checkbox" checked={categoryIds.includes(category.id)} onChange={() => setCategoryIds((current) => toggle(current, category.id))} /> {category.name} ({activeProducts.filter((product) => product.category_id === category.id).length} productos activos actuales)</label>)}
            <ExtraForm form={form} onChange={setForm} error={surchargeError} />
            <Button disabled={(!productIds.length && !categoryIds.length) || Boolean(surchargeError) || previewMutation.isPending} onClick={requestPreview}>Ver preview</Button>
            {currentPreview.map((row) => <p key={row.product_id}>{row.product_name} · {row.sku} · {row.category}: {row.compatible ? 'Compatible' : row.reason}</p>)}
            {incompatible.length > 0 && <div role="alert"><p>Hay incompatibles. Desmárcalos y vuelve a consultar preview.</p>{incompatible.map((row) => <Button key={row.product_id} variant="secondary" onClick={() => setProductIds((current) => current.filter((productId) => productId !== row.product_id))}>Quitar {row.product_name}</Button>)}</div>}
            <Button disabled={!previewApproved || Boolean(surchargeError) || apply.isPending} onClick={requestApply}>Relacionar {currentPreview.length} productos</Button>
          </section>
        </>}
      </div>
    </Modal>
    <Modal isOpen={Boolean(editing)} onClose={() => { setEditing(null); setEditError(''); }} title="Editar ingrediente adicional">
      <div style={{ display: 'grid', gap: 8 }}><ExtraForm form={editForm} onChange={setEditForm} error={editSurchargeError} />{editError && <p role="alert">{editError}</p>}<Button disabled={Boolean(editSurchargeError) || update.isPending} onClick={() => update.mutate()}>Guardar relación</Button></div>
    </Modal>
  </>;
}

function ExtraForm({ form, onChange, error }: { form: Form; onChange: (value: Form) => void; error: string | null }) {
  return <><label>Cantidad Decimal (unidad base)<Input value={form.add_quantity} onChange={(event: React.ChangeEvent<HTMLInputElement>) => onChange({ ...form, add_quantity: event.target.value })} /></label><label><input type="checkbox" checked={form.charge_additional} onChange={(event) => onChange({ ...form, charge_additional: event.target.checked })} /> Cobrar adicional</label><label>Precio adicional (MXN)<Input inputMode="decimal" placeholder="0.00" disabled={!form.charge_additional} value={form.add_price_delta_mxn} onChange={(event: React.ChangeEvent<HTMLInputElement>) => onChange({ ...form, add_price_delta_mxn: event.target.value })} /></label>{error && <p role="alert">{error}</p>}<p style={{ color: '#64748b' }}>Sin cargo no modifica el total de venta. El costo promedio no define el precio.</p></>;
}
