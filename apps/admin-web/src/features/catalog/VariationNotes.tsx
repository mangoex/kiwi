import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, Edit3, MessageSquareText, Plus, RotateCcw, Search } from 'lucide-react';
import { Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';

interface Product { id: string; name: string; sku: string; }
interface Note { id: string; name: string; display_order: number; status: 'active' | 'archived'; product_name: string; }

export default function VariationNotes() {
  const client = useQueryClient();
  const [productId, setProductId] = useState('');
  const [search, setSearch] = useState('');
  const [name, setName] = useState('');
  const [editing, setEditing] = useState<Note | null>(null);
  const [error, setError] = useState('');
  const products = useQuery<Product[]>({ queryKey: ['products'], queryFn: () => fetchApi('/catalog/products') });
  const notes = useQuery<Note[]>({
    queryKey: ['variation-notes', productId],
    queryFn: () => fetchApi(`/catalog/variation-notes?product_id=${encodeURIComponent(productId)}`),
    enabled: Boolean(productId),
  });
  const refresh = () => client.invalidateQueries({ queryKey: ['variation-notes', productId] });
  const create = useMutation({
    mutationFn: () => fetchApi(`/products/${productId}/variation-notes`, { method: 'POST', body: JSON.stringify({ name }) }),
    onSuccess: () => { setName(''); setError(''); void refresh(); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible crear la nota.'),
  });
  const save = useMutation({
    mutationFn: async () => {
      if (!editing) throw new Error('No hay una nota seleccionada.');
      return fetchApi(`/variation-notes/${editing.id}`, { method: 'PUT', body: JSON.stringify({ name: editing.name, display_order: editing.display_order, status: editing.status }) });
    },
    onSuccess: () => { setEditing(null); setError(''); void refresh(); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible guardar la nota.'),
  });
  const filteredProducts = useMemo(() => (products.data || []).filter((p) => `${p.name} ${p.sku}`.toLowerCase().includes(search.toLowerCase())), [products.data, search]);

  return <div style={{ padding: 24, maxWidth: 980 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}><MessageSquareText color="#10b981" /><div><h1 style={{ margin: 0 }}>Variaciones y cambios</h1><p style={{ margin: '4px 0', color: '#64748b' }}>Notas táctiles por producto, sin precio, receta ni inventario.</p></div></div>
    {error && <p role="alert" style={{ color: '#b91c1c' }}>{error}</p>}
    <label style={{ display: 'grid', gap: 6, maxWidth: 480 }}>Buscar o seleccionar producto
      <div style={{ position: 'relative' }}><Search size={16} style={{ position: 'absolute', top: 11, left: 10, color: '#64748b' }} /><Input value={search} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)} placeholder="Nombre o SKU" style={{ paddingLeft: 32 }} /></div>
      <select value={productId} onChange={(e) => setProductId(e.target.value)} style={{ padding: 10, borderRadius: 8, border: '1px solid #cbd5e1' }}><option value="">Selecciona un producto</option>{filteredProducts.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.sku})</option>)}</select>
    </label>
    {productId && <section style={{ marginTop: 24 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'end', flexWrap: 'wrap' }}><label style={{ display: 'grid', gap: 5, minWidth: 240 }}>Nueva nota<Input value={name} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)} maxLength={120} placeholder="Ej. Sin cebolla" /></label><Button onClick={() => create.mutate()} disabled={!name.trim() || create.isPending}><Plus size={16} /> Agregar</Button></div>
      {notes.isLoading ? <p>Cargando notas…</p> : (notes.data || []).length === 0 ? <p style={{ color: '#64748b' }}>Aún no hay notas para este producto.</p> : <div style={{ display: 'grid', gap: 8, marginTop: 16 }}>{notes.data?.map((note) => <div key={note.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: 12, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10 }}><span style={{ flex: 1 }}>{note.name}</span><span style={{ fontSize: 12, color: note.status === 'active' ? '#047857' : '#64748b' }}>{note.status === 'active' ? 'Activa' : 'Archivada'}</span><button aria-label={`Editar ${note.name}`} onClick={() => setEditing(note)} style={{ border: 0, background: 'transparent', cursor: 'pointer' }}><Edit3 size={17} /></button><button aria-label={note.status === 'active' ? `Archivar ${note.name}` : `Reactivar ${note.name}`} onClick={() => { setEditing({ ...note, status: note.status === 'active' ? 'archived' : 'active' }); }} style={{ border: 0, background: 'transparent', cursor: 'pointer' }}>{note.status === 'active' ? <Archive size={17} /> : <RotateCcw size={17} />}</button></div>)}</div>}
    </section>}
    <Modal isOpen={Boolean(editing)} onClose={() => setEditing(null)} title="Editar nota"><div style={{ display: 'grid', gap: 12 }}><label>Etiqueta<Input value={editing?.name || ''} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEditing((current) => current && { ...current, name: e.target.value })} maxLength={120} /></label><label>Orden<Input type="number" value={editing?.display_order || 0} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEditing((current) => current && { ...current, display_order: Number(e.target.value) })} /></label><Button onClick={() => save.mutate()} disabled={save.isPending}>Guardar</Button></div></Modal>
  </div>;
}
