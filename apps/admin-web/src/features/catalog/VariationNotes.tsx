import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Archive,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Edit3,
  Layers3,
  MessageSquareText,
  RotateCcw,
} from 'lucide-react';
import { Button, Input, Modal } from '@restaurantos/ui';
import { ApiError, fetchApi } from '@restaurantos/api-client';

interface Product {
  id: string;
  name: string;
  sku: string;
  category_id?: string;
  category_name?: string;
  station?: string;
  status: 'active' | 'inactive' | 'needs_review' | 'archived';
}

interface Category {
  id: string;
  name: string;
  status: string;
  display_order?: number;
}

interface CommentProduct {
  product_id: string;
  product_name: string;
  product_sku: string;
}

interface Comment {
  id: string;
  text: string;
  text_normalized: string;
  display_order: number;
  status: 'active' | 'archived';
  products: CommentProduct[];
}

interface PreviewItem {
  id?: string;
  text: string;
  text_normalized: string;
  status: 'created' | 'existing';
}

interface CommentPreview {
  items: PreviewItem[];
  created: PreviewItem[];
  existing: PreviewItem[];
  duplicates: string[];
  product_ids: string[];
}

type OperationalGroup = 'food' | 'drinks' | 'other';

const OPERATIONAL_GROUPS: {
  id: OperationalGroup;
  label: string;
  description: string;
}[] = [
  { id: 'food', label: 'Alimentos', description: 'Cocina' },
  { id: 'drinks', label: 'Bebidas', description: 'Barra y bebidas' },
  { id: 'other', label: 'Otros', description: 'Empaque y complementos' },
];

const card: React.CSSProperties = {
  background: '#fff',
  border: '1px solid #e2e8f0',
  borderRadius: 14,
};

function operationalGroupForStation(station?: string): OperationalGroup {
  if (station === 'kitchen') return 'food';
  if (station === 'drinks') return 'drinks';
  return 'other';
}

function parseVisibleComments(value: string): string[] {
  const seen = new Set<string>();
  return value
    .split(/(?:,|\n|\s{2,})/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => {
      const normalized = item
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/\s+/g, ' ')
        .toLocaleLowerCase();
      if (seen.has(normalized)) return false;
      seen.add(normalized);
      return true;
    });
}

export function orderCommentPreviewFingerprint(text: string, productIds: string[]): string {
  return JSON.stringify({
    comments: text,
    product_ids: [...new Set(productIds)].sort(),
  });
}

export default function VariationNotes() {
  const client = useQueryClient();
  const [text, setText] = useState('');
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>([]);
  const [expandedGroups, setExpandedGroups] = useState<OperationalGroup[]>(['food']);
  const [preview, setPreview] = useState<CommentPreview | null>(null);
  const [previewFingerprint, setPreviewFingerprint] = useState<string | null>(null);
  const [editing, setEditing] = useState<Comment | null>(null);
  const [statusTarget, setStatusTarget] = useState<Comment | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const products = useQuery<Product[]>({
    queryKey: ['products'],
    queryFn: () => fetchApi('/catalog/products'),
  });
  const categories = useQuery<Category[]>({
    queryKey: ['categories'],
    queryFn: () => fetchApi('/categories'),
  });
  const notes = useQuery<Comment[]>({
    queryKey: ['order-comments'],
    queryFn: () => fetchApi('/catalog/order-comments'),
  });

  const activeProducts = useMemo(
    () => (products.data || []).filter((product) => product.status === 'active'),
    [products.data],
  );
  const categoryGroups = useMemo(() => {
    const activeCategories = (categories.data || [])
      .filter((category) => category.status === 'active')
      .sort((left, right) => (left.display_order || 0) - (right.display_order || 0) || left.name.localeCompare(right.name));

    return OPERATIONAL_GROUPS.map((group) => ({
      ...group,
      categories: activeCategories.filter((category) => {
        const categoryProducts = activeProducts.filter((product) => product.category_id === category.id);
        if (categoryProducts.length === 0) return false;
        const stationCounts = categoryProducts.reduce<Record<OperationalGroup, number>>(
          (counts, product) => ({
            ...counts,
            [operationalGroupForStation(product.station)]: counts[operationalGroupForStation(product.station)] + 1,
          }),
          { food: 0, drinks: 0, other: 0 },
        );
        const dominantGroup = (Object.entries(stationCounts) as [OperationalGroup, number][])
          .sort((left, right) => right[1] - left[1])[0][0];
        return dominantGroup === group.id;
      }),
    })).filter((group) => group.categories.length > 0);
  }, [activeProducts, categories.data]);

  const selectedProductIds = useMemo(
    () => activeProducts
      .filter((product) => product.category_id && selectedCategoryIds.includes(product.category_id))
      .map((product) => product.id),
    [activeProducts, selectedCategoryIds],
  );
  const parsedComments = useMemo(() => parseVisibleComments(text), [text]);
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['order-comments'] });
  };
  const currentPreviewFingerprint = orderCommentPreviewFingerprint(text, selectedProductIds);
  const invalidatePreview = () => {
    setPreview(null);
    setPreviewFingerprint(null);
  };

  const requestPreview = useMutation<
    CommentPreview,
    Error,
    { fingerprint: string; payload: { comments: string; product_ids: string[] } }
  >({
    mutationFn: ({ payload }) => fetchApi('/catalog/order-comments/bulk/preview', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
    onMutate: () => {
      setError('');
      invalidatePreview();
    },
    onSuccess: (result, request) => {
      setPreview(result);
      setPreviewFingerprint(request.fingerprint);
    },
    onError: (reason) => setError(
      reason instanceof ApiError ? reason.message : 'No fue posible generar la vista previa.',
    ),
  });

  const apply = useMutation<
    unknown,
    Error,
    { fingerprint: string; payload: { comments: string; product_ids: string[] } }
  >({
    mutationFn: ({ fingerprint, payload }) => {
      if (fingerprint !== previewFingerprint || fingerprint !== currentPreviewFingerprint) {
        throw new Error(
          'Los comentarios o las subcategorías cambiaron después de la vista previa. Revísalos de nuevo.',
        );
      }
      return fetchApi('/catalog/order-comments/bulk', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    onMutate: () => setError(''),
    onSuccess: () => {
      setText('');
      setSelectedCategoryIds([]);
      invalidatePreview();
      setFeedback('Comentarios guardados y aplicados a las subcategorías seleccionadas.');
      refresh();
    },
    onError: (reason) => setError(
      reason instanceof ApiError ? reason.message : 'No fue posible guardar los comentarios.',
    ),
  });

  const save = useMutation({
    mutationFn: () => {
      if (!editing) throw new Error('No hay comentario seleccionado.');
      return fetchApi(`/catalog/order-comments/${editing.id}`, {
        method: 'PUT',
        body: JSON.stringify({ text: editing.text, display_order: editing.display_order }),
      });
    },
    onSuccess: () => {
      setEditing(null);
      setFeedback('Comentario actualizado.');
      refresh();
    },
    onError: (reason) => setError(
      reason instanceof ApiError ? reason.message : 'No fue posible actualizar el comentario.',
    ),
  });

  const changeStatus = useMutation({
    mutationFn: () => {
      if (!statusTarget) throw new Error('No hay comentario seleccionado.');
      return fetchApi(`/catalog/order-comments/${statusTarget.id}`, {
        method: 'PUT',
        body: JSON.stringify({ status: statusTarget.status === 'active' ? 'archived' : 'active' }),
      });
    },
    onSuccess: () => {
      setStatusTarget(null);
      setFeedback('Estado actualizado.');
      refresh();
    },
    onError: (reason) => setError(
      reason instanceof ApiError ? reason.message : 'No fue posible cambiar el estado.',
    ),
  });

  const toggleGroup = (groupId: OperationalGroup) => {
    setExpandedGroups((current) => current.includes(groupId)
      ? current.filter((id) => id !== groupId)
      : [...current, groupId]);
  };
  const toggleCategory = (categoryId: string) => {
    invalidatePreview();
    setFeedback('');
    setSelectedCategoryIds((current) => current.includes(categoryId)
      ? current.filter((id) => id !== categoryId)
      : [...current, categoryId]);
  };
  const clearSelection = () => {
    invalidatePreview();
    setSelectedCategoryIds([]);
  };

  const statusActionLabel = statusTarget?.status === 'active'
    ? 'Archivar comentario'
    : 'Reactivar comentario';
  const currentPreview = previewFingerprint === currentPreviewFingerprint ? preview : null;
  const previewApproved = Boolean(
    currentPreview
      && currentPreview.product_ids.length === selectedProductIds.length
      && currentPreview.items.length === parsedComments.length,
  );
  const requestCurrentPreview = () => requestPreview.mutate({
    fingerprint: currentPreviewFingerprint,
    payload: { comments: text, product_ids: selectedProductIds },
  });
  const applyCurrentPreview = () => apply.mutate({
    fingerprint: currentPreviewFingerprint,
    payload: { comments: text, product_ids: selectedProductIds },
  });

  return (
    <div style={{ padding: 24, maxWidth: 1200, background: '#f8fafc' }}>
      <header style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 18 }}>
        <MessageSquareText color="#10b981" />
        <div>
          <h1 style={{ margin: 0 }}>Comentarios del pedido</h1>
          <p style={{ color: '#64748b', marginBottom: 0 }}>
            Configura indicaciones de cocina por subcategoría, sin cambiar precio, receta ni inventario.
          </p>
        </div>
      </header>

      <section style={{ ...card, overflow: 'hidden' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(300px, 0.9fr) minmax(380px, 1.1fr)',
          minHeight: 430,
        }}>
          <div style={{ padding: 22, borderRight: '1px solid #e2e8f0', background: '#fbfdff' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
              <div>
                <strong style={{ display: 'block', color: '#1e293b' }}>1. Elige subcategorías</strong>
                <span style={{ color: '#64748b', fontSize: 13 }}>Abre una categoría y marca las que correspondan.</span>
              </div>
              {selectedCategoryIds.length > 0 && (
                <button type="button" onClick={clearSelection} style={{ border: 0, background: 'transparent', color: '#059669', cursor: 'pointer' }}>
                  Limpiar
                </button>
              )}
            </div>

            {products.isLoading || categories.isLoading ? (
              <p>Cargando catálogo…</p>
            ) : products.isError || categories.isError ? (
              <div role="alert">
                <p>No fue posible cargar categorías y productos.</p>
                <Button variant="secondary" onClick={() => {
                  void products.refetch();
                  void categories.refetch();
                }}>Reintentar</Button>
              </div>
            ) : categoryGroups.length === 0 ? (
              <p style={{ color: '#64748b' }}>No hay subcategorías con productos activos.</p>
            ) : (
              <div style={{ display: 'grid', gap: 9 }}>
                {categoryGroups.map((group) => {
                  const expanded = expandedGroups.includes(group.id);
                  const selectedInGroup = group.categories.filter((category) => selectedCategoryIds.includes(category.id)).length;
                  return (
                    <section key={group.id} style={{ border: '1px solid #e2e8f0', borderRadius: 11, overflow: 'hidden', background: '#fff' }}>
                      <button
                        type="button"
                        aria-expanded={expanded}
                        onClick={() => toggleGroup(group.id)}
                        style={{
                          width: '100%',
                          border: 0,
                          background: selectedInGroup ? '#f0fdf4' : '#fff',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 10,
                          padding: '13px 14px',
                          cursor: 'pointer',
                          textAlign: 'left',
                        }}
                      >
                        <span style={{ width: 34, height: 34, borderRadius: 9, background: '#ecfdf5', color: '#059669', display: 'grid', placeItems: 'center' }}>
                          <Layers3 size={18} />
                        </span>
                        <span style={{ flex: 1 }}>
                          <strong style={{ display: 'block', color: '#1e293b' }}>{group.label}</strong>
                          <small style={{ color: '#64748b' }}>{group.description} · {group.categories.length} {group.categories.length === 1 ? 'subcategoría' : 'subcategorías'}</small>
                        </span>
                        {selectedInGroup > 0 && <span style={{ color: '#047857', fontSize: 12, fontWeight: 700 }}>{selectedInGroup} {selectedInGroup === 1 ? 'marcada' : 'marcadas'}</span>}
                        {expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                      </button>

                      {expanded && (
                        <div style={{ display: 'grid', gap: 2, padding: '4px 9px 10px 56px', borderTop: '1px solid #f1f5f9' }}>
                          {group.categories.map((category) => {
                            const checked = selectedCategoryIds.includes(category.id);
                            const productCount = activeProducts.filter((product) => product.category_id === category.id).length;
                            return (
                              <label
                                key={category.id}
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 9,
                                  padding: '9px 8px',
                                  borderRadius: 8,
                                  background: checked ? '#f0fdf4' : 'transparent',
                                  cursor: 'pointer',
                                }}
                              >
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() => toggleCategory(category.id)}
                                  style={{ width: 17, height: 17, accentColor: '#10b981' }}
                                />
                                <span style={{ flex: 1, color: '#334155', fontWeight: 600 }}>{category.name}</span>
                                <small style={{ color: '#64748b' }}>{productCount} {productCount === 1 ? 'producto' : 'productos'}</small>
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </section>
                  );
                })}
              </div>
            )}

            <div style={{ marginTop: 16, padding: 12, borderRadius: 10, background: selectedCategoryIds.length ? '#ecfdf5' : '#f1f5f9', color: selectedCategoryIds.length ? '#047857' : '#64748b' }}>
              <strong>{selectedCategoryIds.length} {selectedCategoryIds.length === 1 ? 'subcategoría' : 'subcategorías'}</strong>
              <span style={{ display: 'block', fontSize: 13 }}>{selectedProductIds.length} {selectedProductIds.length === 1 ? 'producto activo recibirá' : 'productos activos recibirán'} los comentarios.</span>
            </div>
          </div>

          <div style={{ padding: 22, display: 'flex', flexDirection: 'column' }}>
            <div style={{ marginBottom: 14 }}>
              <strong style={{ display: 'block', color: '#1e293b' }}>2. Escribe los comentarios</strong>
              <span style={{ color: '#64748b', fontSize: 13 }}>Sepáralos por coma, salto de línea o dos espacios.</span>
            </div>
            <textarea
              aria-label="Comentarios corporativos"
              value={text}
              onChange={(event) => {
                setText(event.target.value);
                setFeedback('');
                invalidatePreview();
              }}
              placeholder={'Sin cebolla, Sin lechuga\nSin azúcar  Azúcar de dieta'}
              rows={8}
              maxLength={12000}
              style={{
                width: '100%',
                minHeight: 174,
                resize: 'vertical',
                padding: 14,
                border: '1px solid #cbd5e1',
                borderRadius: 11,
                font: 'inherit',
                boxSizing: 'border-box',
                outlineColor: '#10b981',
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginTop: 8, color: '#64748b', fontSize: 13 }}>
              <span>{parsedComments.length} {parsedComments.length === 1 ? 'comentario único detectado' : 'comentarios únicos detectados'}</span>
              <span>Máximo 100 · 120 caracteres cada uno</span>
            </div>

            {parsedComments.length > 0 && (
              <div aria-label="Comentarios detectados" style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginTop: 14 }}>
                {parsedComments.slice(0, 12).map((comment) => (
                  <span key={comment} style={{ padding: '6px 9px', borderRadius: 999, background: '#f1f5f9', color: '#475569', fontSize: 13 }}>{comment}</span>
                ))}
                {parsedComments.length > 12 && <span style={{ padding: '6px 9px', color: '#64748b', fontSize: 13 }}>+{parsedComments.length - 12} más</span>}
              </div>
            )}

            <div style={{ marginTop: 'auto', paddingTop: 18 }}>
              {error && <div role="alert" style={{ color: '#b91c1c', marginBottom: 10 }}>{error}</div>}
              {feedback && <div role="status" style={{ color: '#047857', marginBottom: 10 }}>{feedback}</div>}
              <Button
                disabled={!parsedComments.length || !selectedProductIds.length || requestPreview.isPending}
                onClick={requestCurrentPreview}
              >
                <CheckCircle2 size={17} /> Revisar aplicación
              </Button>
            </div>
          </div>
        </div>

        {currentPreview && (
          <div role="status" style={{ borderTop: '1px solid #e2e8f0', padding: 18, background: '#f8fafc' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
              <div>
                <strong style={{ display: 'block', color: '#1e293b' }}>Vista previa lista</strong>
                <span style={{ color: '#64748b', fontSize: 13 }}>
                  {currentPreview.created.length} nuevos · {currentPreview.existing.length} existentes · {selectedProductIds.length} productos
                </span>
              </div>
              <Button disabled={!previewApproved || apply.isPending} onClick={applyCurrentPreview}>
                Aplicar comentarios
              </Button>
            </div>
            {currentPreview.duplicates.length > 0 && (
              <p style={{ marginBottom: 0, color: '#92400e' }}>Duplicados omitidos: {currentPreview.duplicates.join(', ')}</p>
            )}
          </div>
        )}
      </section>

      {notes.isLoading ? (
        <p>Cargando comentarios…</p>
      ) : notes.isError ? (
        <p role="alert">No fue posible cargar comentarios. <button onClick={() => void notes.refetch()}>Reintentar</button></p>
      ) : (
        <section style={{ marginTop: 18, display: 'grid', gap: 8 }}>
          {(notes.data || []).length === 0 ? (
            <p style={{ color: '#64748b' }}>Aún no hay comentarios corporativos.</p>
          ) : (notes.data || []).map((note) => (
            <article key={note.id} style={{ ...card, padding: 15, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ flex: 1 }}>
                <strong>{note.text}</strong>
                <div style={{ color: '#64748b', fontSize: 13 }}>{note.products.length} producto(s) relacionado(s) · {note.status === 'active' ? 'Activo' : 'Archivado'}</div>
              </div>
              <button aria-label={`Editar ${note.text}`} onClick={() => setEditing(note)}><Edit3 size={16} /></button>
              <button aria-label={`Cambiar estado ${note.text}`} onClick={() => setStatusTarget(note)}>{note.status === 'active' ? <Archive size={16} /> : <RotateCcw size={16} />}</button>
            </article>
          ))}
        </section>
      )}

      <Modal isOpen={Boolean(editing)} onClose={() => setEditing(null)} title="Editar comentario">
        <label>Texto del comentario<Input value={editing?.text || ''} onChange={(event) => setEditing((current) => current && { ...current, text: event.target.value })} /></label>
        <Button disabled={save.isPending || !editing?.text.trim()} onClick={() => save.mutate()}>Guardar cambios</Button>
      </Modal>
      <Modal isOpen={Boolean(statusTarget)} onClose={() => setStatusTarget(null)} title={statusActionLabel}>
        <p>Las relaciones y pedidos históricos permanecen intactos.</p>
        <Button disabled={changeStatus.isPending} onClick={() => changeStatus.mutate()}>{statusTarget?.status === 'active' ? 'Archivar' : 'Reactivar'}</Button>
      </Modal>
    </div>
  );
}
