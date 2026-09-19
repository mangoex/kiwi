import React, { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Button, Modal } from '@restaurantos/ui';
import { Plus, Trash2 } from 'lucide-react';
import { resolveBranchId } from '../../lib/branchContext';
import '../../premium-catalogs.css';

type Product = {
  id: string;
  name: string;
  sku: string;
  status?: string;
  catalog_scope?: 'organization' | 'branch';
  source_branch_id?: string | null;
};
type Component = { product_id: string; quantity: string; name?: string; sku?: string };
type Composition = { id: string; version: number; price_cents: number; currency: string; components: Component[] };
type CompositionView = {
  product: Product & { is_combo: boolean };
  branch_id: string | null;
  expected_version: number;
  current_composition: Composition | null;
  effective_composition: Composition | null;
};
type DraftComponent = { product_id: string; quantity: string };

const blank = (): DraftComponent => ({ product_id: '', quantity: '1' });
const isWholePositive = (value: string) => /^[1-9]\d*$/.test(value);
const hydrateWholeQuantity = (value: string) => /^\d+\.0+$/.test(value) ? value.slice(0, value.indexOf('.')) : value;
const errorMessage = (reason: unknown) => {
  if (reason instanceof ApiError && reason.code === 'combo_composition_version_conflict') {
    return 'La composición cambió en otra sesión. Tu borrador se conserva; recarga antes de volver a guardar.';
  }
  return reason instanceof ApiError ? reason.message : 'No fue posible guardar la composición.';
};

export function ComboCompositionModal({ product, onClose }: { product: Product; onClose: () => void }) {
  const client = useQueryClient();
  const [branchId, setBranchId] = useState<string | null>(() => resolveBranchId() || null);
  const [draft, setDraft] = useState<DraftComponent[]>([blank()]);
  const [expectedVersion, setExpectedVersion] = useState(0);
  const [isDirty, setIsDirty] = useState(false);
  const [message, setMessage] = useState('');
  const [requiresReview, setRequiresReview] = useState(false);
  const [reviewedVersion, setReviewedVersion] = useState<number | null>(null);
  const [reviewedComposition, setReviewedComposition] = useState<Composition | null>(null);
  const idempotencyKey = useRef('');
  const branches = useQuery<Product[]>({ queryKey: ['branches', 'combo-composition'], queryFn: () => fetchApi('/branches') });
  const catalog = useQuery<Product[]>({
    queryKey: ['catalog', 'products', 'combo-composition', branchId],
    // This route stays unscoped because its branch query requires POS
    // authority while composition requires recipes.manage.  Filter its
    // catalog metadata below using the selected composition scope.
    queryFn: () => fetchApi('/catalog/products'),
  });
  const composition = useQuery<CompositionView>({
    queryKey: ['product-composition', product.id, branchId],
    queryFn: () => fetchApi(`/products/${product.id}/composition${branchId ? `?branch_id=${encodeURIComponent(branchId)}` : ''}`),
    retry: false,
  });

  useEffect(() => {
    if (!composition.data || isDirty) return;
    const source = composition.data.current_composition || composition.data.effective_composition;
    setDraft(source?.components.map((component) => ({ product_id: component.product_id, quantity: hydrateWholeQuantity(component.quantity) })) || [blank()]);
    setExpectedVersion(composition.data.expected_version);
    idempotencyKey.current = '';
  }, [composition.data, isDirty]);

  const changeDraft = (next: DraftComponent[]) => {
    setDraft(next);
    setIsDirty(true);
    setMessage('');
    idempotencyKey.current = '';
  };
  const reviewCurrentVersion = async () => {
    const result = await composition.refetch();
    if (!result.isSuccess || !result.data) return;
    setExpectedVersion(result.data.expected_version);
    setReviewedVersion(result.data.expected_version);
    setReviewedComposition(result.data.current_composition || result.data.effective_composition);
    setRequiresReview(false);
    idempotencyKey.current = '';
    setMessage(`Versión vigente revisada: v${result.data.expected_version}. Tu borrador se conserva para que lo confirmes.`);
  };
  const save = useMutation({
    mutationFn: () => {
      if (!idempotencyKey.current) idempotencyKey.current = crypto.randomUUID();
      return fetchApi<Composition>(`/products/${product.id}/composition`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': idempotencyKey.current },
        body: JSON.stringify({ branch_id: branchId, expected_version: expectedVersion, components: draft }),
      });
    },
    onSuccess: (response) => {
      client.setQueryData<CompositionView>(['product-composition', product.id, branchId], (previous) => previous ? ({
        ...previous,
        expected_version: response.version,
        current_composition: response,
        effective_composition: response,
      }) : previous);
      setDraft(response.components.map((component) => ({ product_id: component.product_id, quantity: hydrateWholeQuantity(component.quantity) })));
      setExpectedVersion(response.version);
      setIsDirty(false);
      setMessage(`Composición versionada (v${response.version}). El precio canónico es ${response.currency} ${(response.price_cents / 100).toFixed(2)}.`);
      idempotencyKey.current = '';
      void client.invalidateQueries({ queryKey: ['product-composition', product.id, branchId] });
    },
    onError: (reason) => {
      const conflict = reason instanceof ApiError && reason.code === 'combo_composition_version_conflict';
      setRequiresReview(conflict);
      setMessage(errorMessage(reason));
    },
  });
  const duplicate = new Set(draft.map((component) => component.product_id).filter(Boolean)).size !== draft.filter((component) => component.product_id).length;
  const invalidQuantity = draft.some((component) => !isWholePositive(component.quantity));
  const incomplete = draft.some((component) => !component.product_id);
  const candidates = (catalog.data || []).filter((candidate) =>
    candidate.id !== product.id
    && candidate.status !== 'inactive'
    && (candidate.catalog_scope === 'organization'
      || (branchId !== null && candidate.source_branch_id === branchId))
  );

  return <Modal isOpen onClose={onClose} title={`Composición fija: ${product.name}`}>
    <div className="premium-form-layout admin-catalog-tool">
      <p className="premium-form-hint">La composición agrupa productos vendibles con precio propio del producto combo. No admite sustituciones, anidación ni cantidades fraccionarias.</p>
      <label className="premium-form-group">Alcance
        <select value={branchId || ''} onChange={(event) => {
          setBranchId(event.target.value || null);
          setIsDirty(false);
          setMessage('');
          setRequiresReview(false);
          setReviewedVersion(null);
          setReviewedComposition(null);
          idempotencyKey.current = '';
        }} disabled={save.isPending}>
          <option value="">Corporativo</option>
          {(branches.data || []).filter((branch) => branch.status !== 'inactive').map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
        </select>
      </label>
      {composition.isLoading && !composition.data && <p role="status">Cargando composición vigente…</p>}
      {composition.isError && !composition.data && <p role="alert">No fue posible cargar la composición. No se puede guardar sin su versión actual.</p>}
      {composition.isError && composition.data && <p role="alert">No fue posible actualizar la lectura. Se conserva la última composición autoritativa y tu borrador.</p>}
      {message && <p role={message.startsWith('La composición cambió') ? 'alert' : 'status'} className="admin-catalog-message">{message}</p>}
      {requiresReview && <div className="admin-catalog-message" role="alert"><p>Antes de guardar, revisa la versión vigente. Tu borrador no se modificará.</p><Button variant="secondary" onClick={() => void reviewCurrentVersion()}>Revisar versión vigente</Button></div>}
      {reviewedVersion !== null && <div className="premium-form-hint"><p>Versión revisada: v{reviewedVersion}.</p>{reviewedComposition && <ul>{reviewedComposition.components.map((component) => <li key={component.product_id}>{component.name || component.product_id}: {hydrateWholeQuantity(component.quantity)}</li>)}</ul>}</div>}
      {Boolean(composition.data) && <>
        <div className="admin-catalog-tool__header"><h2 style={{ fontSize: '1rem' }}>Productos componentes</h2><button type="button" className="premium-add-btn" onClick={() => changeDraft([...draft, blank()])}><Plus size={16} /> Agregar producto</button></div>
        <div style={{ overflowX: 'auto' }}><table className="premium-table"><thead><tr><th>Producto</th><th>Cantidad de unidades</th><th><span className="sr-only">Quitar</span></th></tr></thead><tbody>{draft.map((component, index) => <tr key={index}><td><select aria-label={`Producto componente ${index + 1}`} value={component.product_id} onChange={(event) => changeDraft(draft.map((row, rowIndex) => rowIndex === index ? { ...row, product_id: event.target.value } : row))}><option value="">Selecciona un producto</option>{candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name} ({candidate.sku})</option>)}</select></td><td><input aria-label={`Cantidad del componente ${index + 1}`} inputMode="numeric" value={component.quantity} onChange={(event) => changeDraft(draft.map((row, rowIndex) => rowIndex === index ? { ...row, quantity: event.target.value } : row))} /></td><td><button type="button" aria-label="Quitar producto componente" disabled={draft.length === 1} onClick={() => changeDraft(draft.filter((_, rowIndex) => rowIndex !== index))}><Trash2 size={16} /></button></td></tr>)}</tbody></table></div>
        {invalidQuantity && <p role="alert">Cada cantidad debe ser un entero positivo exacto.</p>}
        {duplicate && <p role="alert">Un producto sólo puede aparecer una vez en la composición.</p>}
        <div className="premium-footer-actions"><Button variant="secondary" onClick={onClose}>Cerrar</Button><Button variant="primary" disabled={save.isPending || requiresReview || incomplete || invalidQuantity || duplicate} onClick={() => save.mutate()}>{save.isPending ? 'Guardando…' : 'Guardar composición versionada'}</Button></div>
      </>}
    </div>
  </Modal>;
}
