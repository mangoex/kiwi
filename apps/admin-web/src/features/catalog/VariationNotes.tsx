import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, Edit3, MessageSquareText, RotateCcw, Search } from 'lucide-react';
import { Button, Input, Modal } from '@restaurantos/ui';
import { ApiError, fetchApi } from '@restaurantos/api-client';

interface Product {
  id: string;
  name: string;
  sku: string;
  category_id?: string;
  category_name?: string;
  status?: string;
}

interface Category { id: string; name: string; status: string; }
interface CommentProduct { product_id: string; product_name: string; product_sku: string; }
interface Comment {
  id: string;
  text: string;
  text_normalized: string;
  display_order: number;
  status: 'active' | 'archived';
  products: CommentProduct[];
}
interface PreviewItem { id?: string; text: string; text_normalized: string; status: 'created' | 'existing'; }
interface CommentPreview {
  items: PreviewItem[];
  created: PreviewItem[];
  existing: PreviewItem[];
  duplicates: string[];
  product_ids: string[];
}

const card: React.CSSProperties = { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 16 };

function parseVisibleComments(value: string): string[] {
  const seen = new Set<string>();
  return value.split(/[,\n]/).map((item) => item.trim()).filter(Boolean).filter((item) => {
    const normalized = item.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').toLocaleLowerCase();
    if (seen.has(normalized)) return false;
    seen.add(normalized);
    return true;
  });
}

export default function VariationNotes() {
  const client = useQueryClient();
  const [text, setText] = useState('');
  const [productSearch, setProductSearch] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [preview, setPreview] = useState<CommentPreview | null>(null);
  const [editing, setEditing] = useState<Comment | null>(null);
  const [statusTarget, setStatusTarget] = useState<Comment | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const products = useQuery<Product[]>({ queryKey: ['products'], queryFn: () => fetchApi('/catalog/products') });
  const categories = useQuery<Category[]>({ queryKey: ['categories'], queryFn: () => fetchApi('/categories') });
  const notes = useQuery<Comment[]>({ queryKey: ['order-comments'], queryFn: () => fetchApi('/catalog/order-comments') });
  const parsedComments = useMemo(() => parseVisibleComments(text), [text]);
  const visibleProducts = useMemo(() => (products.data || []).filter((product) => {
    if (product.status && product.status !== 'active') return false;
    if (categoryId && product.category_id !== categoryId) return false;
    return `${product.name} ${product.sku}`.toLowerCase().includes(productSearch.toLowerCase());
  }), [products.data, productSearch, categoryId]);
  const selectedProducts = useMemo(() => (products.data || []).filter((product) => selectedProductIds.includes(product.id)), [products.data, selectedProductIds]);
  const refresh = () => { void client.invalidateQueries({ queryKey: ['order-comments'] }); };
  const requestPreview = useMutation<CommentPreview, Error>({
    mutationFn: () => fetchApi('/catalog/order-comments/bulk/preview', { method: 'POST', body: JSON.stringify({ comments: text, product_ids: selectedProductIds }) }),
    onMutate: () => { setError(''); setPreview(null); },
    onSuccess: (result) => setPreview(result),
    onError: (reason) => setError(reason instanceof ApiError ? reason.message : 'No fue posible generar el preview.'),
  });
  const apply = useMutation({
    mutationFn: () => fetchApi('/catalog/order-comments/bulk', { method: 'POST', body: JSON.stringify({ comments: text, product_ids: selectedProductIds }) }),
    onMutate: () => setError(''),
    onSuccess: () => { setText(''); setPreview(null); setFeedback('Comentarios guardados y relacionados.'); refresh(); },
    onError: (reason) => setError(reason instanceof ApiError ? reason.message : 'No fue posible guardar los comentarios.'),
  });
  const save = useMutation({
    mutationFn: () => {
      if (!editing) throw new Error('No hay comentario seleccionado.');
      return fetchApi(`/catalog/order-comments/${editing.id}`, { method: 'PUT', body: JSON.stringify({ text: editing.text, display_order: editing.display_order }) });
    },
    onSuccess: () => { setEditing(null); setFeedback('Comentario actualizado.'); refresh(); },
    onError: (reason) => setError(reason instanceof ApiError ? reason.message : 'No fue posible actualizar el comentario.'),
  });
  const changeStatus = useMutation({
    mutationFn: () => {
      if (!statusTarget) throw new Error('No hay comentario seleccionado.');
      return fetchApi(`/catalog/order-comments/${statusTarget.id}`, { method: 'PUT', body: JSON.stringify({ status: statusTarget.status === 'active' ? 'archived' : 'active' }) });
    },
    onSuccess: () => { setStatusTarget(null); setFeedback('Estado actualizado.'); refresh(); },
    onError: (reason) => setError(reason instanceof ApiError ? reason.message : 'No fue posible cambiar el estado.'),
  });
  const toggleProduct = (productId: string) => setSelectedProductIds((current) => current.includes(productId) ? current.filter((id) => id !== productId) : [...current, productId]);
  const selectVisible = () => setSelectedProductIds((current) => [...new Set([...current, ...visibleProducts.map((product) => product.id)])]);
  const clearSelection = () => setSelectedProductIds([]);
  const statusActionLabel = statusTarget?.status === 'active' ? 'Archivar comentario' : 'Reactivar comentario';
  const previewApproved = Boolean(preview && preview.product_ids.length === selectedProductIds.length && preview.items.length === parsedComments.length);

  return <div style={{ padding: 24, maxWidth: 1120, background: '#f8fafc' }}>
    <header style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 18 }}><MessageSquareText color="#10b981" /><div><h1 style={{ margin: 0 }}>Comentarios del pedido</h1><p style={{ color: '#64748b', marginBottom: 0 }}>Catálogo corporativo global. Indicaciones para cocina; no cambian precio, receta ni inventario.</p></div></header>
    <section style={{ ...card, display: 'grid', gap: 14 }}>
      <label style={{ display: 'grid', gap: 6, fontWeight: 600 }}>Comentarios corporativos<textarea aria-label="Comentarios corporativos" value={text} onChange={(event) => { setText(event.target.value); setPreview(null); }} placeholder="Sin azúcar, Sin lechuga\nSin cebolla" rows={7} maxLength={12000} style={{ width: '100%', minHeight: 150, resize: 'vertical', padding: 12, border: '1px solid #cbd5e1', borderRadius: 10, font: 'inherit', boxSizing: 'border-box' }} /></label>
      <div style={{ color: '#64748b', fontSize: 13 }}>{parsedComments.length} comentario(s) únicos · cada comentario admite hasta 120 caracteres · máximo 100 valores por guardado.</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 1fr) 180px', gap: 10 }}><label>Buscar productos<Input value={productSearch} onChange={(event) => setProductSearch(event.target.value)} placeholder="Nombre o SKU" /></label><label>Categoría<select value={categoryId} onChange={(event) => setCategoryId(event.target.value)} style={{ width: '100%', padding: 9, border: '1px solid #cbd5e1', borderRadius: 8 }}><option value="">Todas</option>{(categories.data || []).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label></div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><Button variant="secondary" onClick={selectVisible}>Seleccionar resultados ({visibleProducts.length})</Button><Button variant="secondary" onClick={clearSelection}>Limpiar selección</Button><span style={{ alignSelf: 'center', color: '#475569' }}>{selectedProductIds.length} producto(s) destino</span></div>
      <div aria-label="Productos seleccionados" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{selectedProducts.map((product) => <button key={product.id} type="button" onClick={() => toggleProduct(product.id)} style={{ border: '1px solid #a7f3d0', background: '#ecfdf5', color: '#047857', borderRadius: 999, padding: '5px 10px', cursor: 'pointer' }}>{product.name} ×</button>)}</div>
      <div style={{ maxHeight: 250, overflowY: 'auto', display: 'grid', gap: 6 }} aria-label="Seleccionar productos">{visibleProducts.map((product) => <label key={product.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: 8, border: '1px solid #e2e8f0', borderRadius: 8, background: selectedProductIds.includes(product.id) ? '#f0fdf4' : '#fff' }}><input type="checkbox" checked={selectedProductIds.includes(product.id)} onChange={() => toggleProduct(product.id)} /> <span>{product.name} <small style={{ color: '#64748b' }}>({product.sku})</small></span></label>)}</div>
      {error && <div role="alert" style={{ color: '#b91c1c' }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Button disabled={!parsedComments.length || !selectedProductIds.length || requestPreview.isPending} onClick={() => requestPreview.mutate()}>Ver preview</Button>{preview && <span style={{ color: '#475569' }}>{preview.created.length} nuevos · {preview.existing.length} existentes · {preview.duplicates.length} duplicados</span>}<Button disabled={!previewApproved || apply.isPending} onClick={() => apply.mutate()}>Confirmar comentarios</Button></div>
      {preview && <div role="status" style={{ background: '#f8fafc', borderRadius: 8, padding: 12 }}><strong>Preview antes de confirmar</strong><div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>{preview.items.map((item) => <span key={item.text_normalized} style={{ padding: '4px 8px', borderRadius: 999, background: item.status === 'created' ? '#dcfce7' : '#e0f2fe' }}>{item.text} · {item.status === 'created' ? 'nuevo' : 'existente'}</span>)}</div>{preview.duplicates.length > 0 && <p style={{ marginBottom: 0, color: '#92400e' }}>Duplicados del texto pegado: {preview.duplicates.join(', ')}</p>}</div>}
    </section>
    {products.isLoading || categories.isLoading ? <p>Cargando catálogo…</p> : products.isError ? <p role="alert">No fue posible cargar productos. <button onClick={() => void products.refetch()}>Reintentar</button></p> : null}
    {notes.isLoading ? <p>Cargando comentarios…</p> : notes.isError ? <p role="alert">No fue posible cargar comentarios. <button onClick={() => void notes.refetch()}>Reintentar</button></p> : <section style={{ marginTop: 18, display: 'grid', gap: 8 }}>{(notes.data || []).length === 0 ? <p style={{ color: '#64748b' }}>Aún no hay comentarios corporativos.</p> : (notes.data || []).map((note) => <article key={note.id} style={{ ...card, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}><div style={{ flex: 1 }}><strong>{note.text}</strong><div style={{ color: '#64748b', fontSize: 13 }}>{note.products.length} producto(s) relacionado(s) · {note.status === 'active' ? 'Activo' : 'Archivado'}</div></div><button aria-label={`Editar ${note.text}`} onClick={() => setEditing(note)}><Edit3 size={16} /></button><button aria-label={`Cambiar estado ${note.text}`} onClick={() => setStatusTarget(note)}>{note.status === 'active' ? <Archive size={16} /> : <RotateCcw size={16} />}</button></article>)}</section>}
    <Modal isOpen={Boolean(editing)} onClose={() => setEditing(null)} title="Editar comentario"><label>Texto del comentario<Input value={editing?.text || ''} onChange={(event) => setEditing((current) => current && { ...current, text: event.target.value })} /></label><Button disabled={save.isPending || !editing?.text.trim()} onClick={() => save.mutate()}>Guardar cambios</Button></Modal>
    <Modal isOpen={Boolean(statusTarget)} onClose={() => setStatusTarget(null)} title={statusActionLabel}><p>Las relaciones y pedidos históricos permanecen intactos.</p><Button disabled={changeStatus.isPending} onClick={() => changeStatus.mutate()}>{statusTarget?.status === 'active' ? 'Archivar' : 'Reactivar'}</Button></Modal>
    {feedback && <p role="status">{feedback}</p>}
  </div>;
}
