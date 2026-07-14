import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, Edit3, MessageSquareText, Plus, RotateCcw, Search } from 'lucide-react';
import { Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';

interface Product { id: string; name: string; sku: string; }
interface Note { id: string; name: string; display_order: number; status: 'active' | 'archived'; }

const card: React.CSSProperties = { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 16 };

/** POS-VAR-001 only. Inventory-backed extras live at /admin/ingredient-extras. */
export default function VariationNotes() {
  const client = useQueryClient();
  const [productId, setProductId] = useState('');
  const [productSearch, setProductSearch] = useState('');
  const [name, setName] = useState('');
  const [editing, setEditing] = useState<Note | null>(null);
  const [statusTarget, setStatusTarget] = useState<Note | null>(null);
  const [feedback, setFeedback] = useState('');
  const products = useQuery<Product[]>({ queryKey: ['products'], queryFn: () => fetchApi('/catalog/products') });
  const notes = useQuery<Note[]>({ queryKey: ['variation-notes', productId], queryFn: () => fetchApi(`/catalog/variation-notes?product_id=${encodeURIComponent(productId)}`), enabled: Boolean(productId) });
  const refresh = () => client.invalidateQueries({ queryKey: ['variation-notes', productId] });
  const create = useMutation({ mutationFn: () => fetchApi(`/products/${productId}/variation-notes`, { method: 'POST', body: JSON.stringify({ name }) }), onSuccess: () => { setName(''); setFeedback('Comentario creado.'); void refresh(); } });
  const save = useMutation({ mutationFn: () => { if (!editing) throw new Error('No hay comentario seleccionado.'); return fetchApi(`/variation-notes/${editing.id}`, { method: 'PUT', body: JSON.stringify({ name: editing.name, display_order: editing.display_order }) }); }, onSuccess: () => { setEditing(null); setFeedback('Comentario actualizado.'); void refresh(); } });
  const changeStatus = useMutation({ mutationFn: () => { if (!statusTarget) throw new Error('No hay comentario seleccionado.'); return fetchApi(`/variation-notes/${statusTarget.id}`, { method: 'PUT', body: JSON.stringify({ status: statusTarget.status === 'active' ? 'archived' : 'active' }) }); }, onSuccess: () => { setStatusTarget(null); void refresh(); } });
  const visibleProducts = useMemo(() => (products.data || []).filter((product) => `${product.name} ${product.sku}`.toLowerCase().includes(productSearch.toLowerCase())), [products.data, productSearch]);
  const statusActionLabel = statusTarget?.status === 'active' ? 'Archivar comentario' : 'Reactivar comentario';

  return <div style={{ padding: 24, maxWidth: 1120, background: '#f8fafc' }}>
    <header style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 18 }}><MessageSquareText color="#10b981" /><div><h1 style={{ margin: 0 }}>Comentarios del pedido</h1><p style={{ color: '#64748b', marginBottom: 0 }}>Indicaciones para cocina; no cambian precio, receta ni inventario.</p></div></header>
    <section style={card}>
      <p style={{ marginTop: 0, color: '#64748b' }}>Ejemplos: Sin cebolla, Sin lechuga, Sin azúcar, Azúcar de dieta.</p>
      <label style={{ display: 'grid', gap: 6, maxWidth: 520 }}>Buscar o seleccionar producto<div style={{ position: 'relative' }}><Search size={16} style={{ left: 10, top: 11, position: 'absolute', color: '#64748b' }} /><Input value={productSearch} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setProductSearch(event.target.value)} placeholder="Nombre o SKU" style={{ paddingLeft: 32 }} /></div><select value={productId} onChange={(event) => setProductId(event.target.value)}><option value="">Selecciona un producto</option>{visibleProducts.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.sku})</option>)}</select></label>
      {products.isLoading && <p>Cargando productos…</p>}{products.isError && <p role="alert">No fue posible cargar productos. <button onClick={() => void products.refetch()}>Reintentar</button></p>}
      {productId && <><div style={{ display: 'flex', gap: 8, marginTop: 18 }}><Input value={name} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setName(event.target.value)} placeholder="Nuevo comentario para cocina" /><Button disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}><Plus size={16} /> Agregar</Button></div>
        {notes.isLoading ? <p>Cargando comentarios…</p> : notes.isError ? <p role="alert">No fue posible cargar comentarios. <button onClick={() => void notes.refetch()}>Reintentar</button></p> : (notes.data || []).length === 0 ? <p style={{ color: '#64748b' }}>No hay comentarios para este producto.</p> : (notes.data || []).map((note) => <div key={note.id} style={{ ...card, display: 'flex', marginTop: 8, gap: 8, alignItems: 'center' }}><span style={{ flex: 1 }}>{note.name}</span><span style={{ color: '#64748b' }}>{note.status === 'active' ? 'Activo' : 'Archivado'}</span><button aria-label={`Editar ${note.name}`} onClick={() => setEditing(note)}><Edit3 size={16} /></button><button aria-label={`Cambiar estado ${note.name}`} onClick={() => setStatusTarget(note)}>{note.status === 'active' ? <Archive size={16} /> : <RotateCcw size={16} />}</button></div>)}</>}
    </section>
    <Modal isOpen={Boolean(editing)} onClose={() => setEditing(null)} title="Editar comentario"><label>Etiqueta<Input value={editing?.name || ''} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setEditing((current) => current && { ...current, name: event.target.value })} /></label><Button disabled={save.isPending || !editing?.name.trim()} onClick={() => save.mutate()}>Guardar cambios</Button></Modal>
    <Modal isOpen={Boolean(statusTarget)} onClose={() => setStatusTarget(null)} title={statusActionLabel}><p>Los pedidos históricos permanecen intactos.</p><Button disabled={changeStatus.isPending} onClick={() => changeStatus.mutate()}>{statusTarget?.status === 'active' ? 'Archivar' : 'Reactivar'}</Button></Modal>
    {feedback && <p role="status">{feedback}</p>}
  </div>;
}
