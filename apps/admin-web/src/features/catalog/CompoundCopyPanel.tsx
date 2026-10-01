import React, { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Button, usePythonPreview, registerWorkspaceNavigationGuard, isWorkspaceRejection } from '@restaurantos/ui';
import { resolveBranchId } from '../../lib/branchContext';

type Group = { id?: string; name: string; minimum_selections: number; maximum_selections: number; included_selections: number; options: { id?: string; name: string; component_quantity?: string | number | null; price_delta_cents: number }[] };
export interface CopyResult { version: number; groups: unknown[]; result: 'applied' | 'replay' }
export function CompoundCopyPanel({ productId, expectedVersion, disabled, onCopied, onBusyChange }: {
  productId: string; expectedVersion: number; disabled: boolean; onCopied: (result: CopyResult) => void | Promise<void>; onBusyChange: (busy: boolean) => void;
}) {
  const [sourceId, setSourceId] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const intent = useRef<{ key: string; body: string } | null>(null);
  useEffect(() => {
    if (!pending && !uncertain) return;
    const unregister = registerWorkspaceNavigationGuard(() => { window.alert('Recupera el resultado de la copia antes de salir.'); return false; });
    const unload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', unload);
    return () => { unregister(); window.removeEventListener('beforeunload', unload); };
  }, [pending, uncertain]);
  const { data: products = [] } = useQuery<{ id: string; name: string }[]>({ queryKey: ['compound-copy-products'], queryFn: () => fetchApi('/products') });
  const source = useQuery<{ expected_version: number; groups: Group[] }>({ queryKey: ['compound-copy-source', sourceId], queryFn: () => fetchApi('/products/' + sourceId + '/modifier-configuration'), enabled: Boolean(sourceId), retry: false });
  const copy = async () => {
    if (pending || (!uncertain && (!accepted || !source.data))) return;
    intent.current ??= { key: 'compound-copy-' + crypto.randomUUID(), body: JSON.stringify({ source_product_id: sourceId, expected_source_version: source.data?.expected_version, expected_target_version: expectedVersion }) };
    setPending(true); onBusyChange(true); setMessage('');
    let applied = false;
    try {
      const result = await fetchApi<CopyResult>('/products/' + productId + '/modifier-configuration/copy', { method: 'POST', headers: { 'Idempotency-Key': intent.current.key }, body: intent.current.body });
      applied = true;
      await onCopied(result); intent.current = null; setUncertain(false); setAccepted(false); onBusyChange(false); setMessage('Copia registrada y destino releído. El origen y los pedidos históricos conservan sus datos.');
    } catch (error) {
      const rejected = !applied && error instanceof ApiError && isWorkspaceRejection(error.status, error.code, uncertain, 'copy');
      setUncertain(!rejected); setMessage(error instanceof Error ? error.message : 'No se confirmó la copia.');
      if (rejected) { intent.current = null; setAccepted(false); onBusyChange(false); }
    } finally { setPending(false); }
  };
  return <section className="modifier-group-card" aria-label="Copiar configuración completa">
    <h3>Copiar grupos y opciones de otro producto</h3>
    <label>Producto de origen<select className="modifier-control" disabled={disabled || pending || uncertain} value={sourceId} onChange={e => { setSourceId(e.target.value); setAccepted(false); }}><option value="">Selecciona producto</option>{products.filter(product => product.id !== productId).map(product => <option key={product.id} value={product.id}>{product.name}</option>)}</select></label>
    {source.isError && <p role="alert">No se pudo consultar el origen. Reintenta su lectura.</p>}
    {source.data && <><p>Origen v{source.data.expected_version} · destino v{expectedVersion}. Se reemplazarán todos los grupos y opciones del destino.</p><ul>{source.data.groups.map(group => <li key={group.id || group.name}>{group.name} · mínimo {group.minimum_selections}, máximo {group.maximum_selections}, incluidos {group.included_selections}<ul>{group.options.map(option => <li key={option.id || option.name}>{option.name} · cantidad {option.component_quantity ?? '—'} · recargo {option.price_delta_cents} centavos</li>)}</ul></li>)}</ul><p>Precio base, receta, combo fijo y disponibilidad conservan sus valores.</p><label><input type="checkbox" checked={accepted} disabled={disabled || pending || uncertain} onChange={e => setAccepted(e.target.checked)} /> Revisé el reemplazo de la configuración del destino y de cualquier edición local.</label></>}
    {message && <p role="alert">{message}</p>}
    {uncertain && <p>Recupera el resultado de esta copia antes de editar el destino.</p>}
    <Button disabled={disabled || pending || (!uncertain && (!accepted || !source.data))} onClick={() => void copy()}>{pending ? 'Copiando…' : uncertain ? 'Recuperar copia' : 'Confirmar copia completa'}</Button>
    <Button variant="secondary" disabled={pending || uncertain || !sourceId} onClick={() => { setAccepted(false); void source.refetch(); }}>Releer origen</Button>
  </section>;
}

export function CompoundSelectionPreview({ productId, groups, disabled }: { productId: string; groups: Group[]; disabled: boolean }) {
  const branchId = resolveBranchId();
  const [selected, setSelected] = useState<string[]>([]);
  const preview = usePythonPreview<{ line_total_cents: number; modifier_total_cents: number; consumption: { components: { item_id: string; gross_quantity: string; unit_code?: string }[] } }>(fetchApi, '/products/' + productId + '/modifier-configuration/selection-preview', { branch_id: branchId, quantity: 1, modifiers: selected.map(option_id => ({ option_id })) }, Boolean(branchId && !disabled));
  return <section aria-label="Probar selección guardada"><h3>Probar selección guardada</h3><p>Prueba una unidad con la configuración vigente en la sucursal seleccionada.</p>{groups.map(group => <fieldset key={group.id || group.name} disabled={disabled}><legend>{group.name}</legend>{group.options.map(option => <label key={option.id || option.name} style={{ display: 'block' }}><input type="checkbox" checked={Boolean(option.id && selected.includes(option.id))} onChange={e => { if (option.id) setSelected(rows => e.target.checked ? [...rows, option.id!] : rows.filter(id => id !== option.id)); }} /> {option.name}</label>)}</fieldset>)}{preview.error && <p role="alert">{preview.error}</p>}{preview.data && <div role="status"><p>Precio: {preview.data.line_total_cents} centavos · adicionales: {preview.data.modifier_total_cents} centavos</p><ul>{preview.data.consumption.components.map(row => <li key={row.item_id}>Insumo {row.item_id}: {row.gross_quantity} {row.unit_code}</li>)}</ul></div>}</section>;
}
