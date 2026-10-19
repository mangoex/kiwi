import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Button, Input, Modal, Badge } from '@restaurantos/ui';
import { Edit, Trash2 } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAdminSession } from '../../lib/adminSession';
import { formatRecipeDecimal } from '../catalog/recipeDecimal';
import InventoryScopeControl from '../inventory/InventoryScopeControl';
import { useInventoryOnline } from '../inventory/useInventoryOnline';
import { inventoryDate } from '../inventory/InventoryStock';
import { thresholdDraftError, thresholdPayload, type ThresholdDraft } from '../inventory/inventoryQueryState';
import '../inventory/InventoryVisibility.css';

interface Threshold {
  item_id: string; item_name: string; branch_id: string; warehouse_id: string; unit_id: string; unit_code: string;
  quantity_on_hand: string; minimum_quantity: string | null; maximum_quantity: string | null; version: number | null;
  status: 'no_thresholds' | 'below_minimum' | 'in_range' | 'above_maximum'; as_of: string;
}
interface Editing { row: Threshold; branchName: string; warehouseName: string }
const labels: Record<Threshold['status'], string> = { no_thresholds: 'Sin umbrales', below_minimum: 'Bajo mínimo', in_range: 'En rango', above_maximum: 'Sobre máximo' };
const failure = (reason: unknown, fallback: string) => reason instanceof ApiError ? reason.message : fallback;

export default function StockThresholds() {
  const { session, inventoryQueryScope: scope, selectInventoryQueryScope, assertCurrentAuthority } = useAdminSession();
  const [params] = useSearchParams();
  const requestedBranch = params.get('inventory_branch_id');
  const [handledBranch, setHandledBranch] = useState<string | null>(null);
  const capability = session.inventory_query_capabilities;
  const online = useInventoryOnline();
  const authorizedRequest = Boolean(requestedBranch && capability?.branches.some(branch => branch.id === requestedBranch));
  useEffect(() => {
    if (requestedBranch && requestedBranch !== handledBranch && authorizedRequest) {
      selectInventoryQueryScope({ kind: 'branch', branch_id: requestedBranch });
      setHandledBranch(requestedBranch);
    }
  }, [requestedBranch, handledBranch, authorizedRequest, selectInventoryQueryScope]);
  const branchId = scope?.kind === 'branch' ? scope.branch_id : '';
  const branch = capability?.branches.find(row => row.id === branchId);
  const client = useQueryClient();
  const [editing, setEditing] = useState<Editing | null>(null);
  const modalBody = useRef<HTMLDivElement>(null);
  const restoreFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!editing) { restoreFocus.current?.focus(); return; }
    const dialog = modalBody.current?.closest<HTMLElement>('[role="dialog"]');
    modalBody.current?.querySelector<HTMLInputElement>('input')?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !dialog) return;
      const elements = Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), [tabindex="0"]'));
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    dialog?.addEventListener('keydown', trap);
    return () => dialog?.removeEventListener('keydown', trap);
  }, [editing]);
  const [draft, setDraft] = useState<ThresholdDraft>({});
  const [message, setMessage] = useState('');
  const [conflict, setConflict] = useState(false);
  const thresholds = useQuery<Threshold[]>({
    queryKey: ['admin-catalog', 'stock-thresholds', session.user.id, session.organization_id,
      session.scope.authorization_version, branchId],
    queryFn: ({ signal }) => fetchApi(`/admin-catalog/stock-thresholds?branch_id=${encodeURIComponent(branchId)}`, { signal }),
    enabled: Boolean(branchId && online && capability && (!requestedBranch || handledBranch === requestedBranch)), retry: false,
  });
  const refresh = () => void client.invalidateQueries({ queryKey: ['admin-catalog', 'stock-thresholds'] });
  const mutationFailure = (reason: unknown) => {
    setMessage(failure(reason, 'No fue posible guardar los umbrales.'));
    if (reason instanceof ApiError && reason.status === 409) {
      setConflict(true); setMessage('Los umbrales cambiaron. Cierra este formulario, actualiza y revisa los valores antes de guardar.');
    }
  };
  const save = useMutation({ retry: false,
    mutationFn: async () => {
      assertCurrentAuthority();
      if (!navigator.onLine) throw new Error('Sin conexión. No se enviaron cambios.');
      if (!editing || thresholdDraftError(editing.row, draft)) throw new Error('Revisa los valores del formulario.');
      return fetchApi(`/admin-catalog/stock-thresholds/${editing.row.item_id}?branch_id=${encodeURIComponent(editing.row.branch_id)}`, {
        method: 'PUT', body: JSON.stringify(thresholdPayload(editing.row, draft, editing.row.version)),
      });
    },
    onSuccess: () => { setMessage('Umbrales guardados. La existencia se conserva sin cambios.'); setEditing(null); refresh(); },
    onError: mutationFailure,
  });
  const remove = useMutation({ retry: false,
    mutationFn: (row: Threshold) => {
      assertCurrentAuthority();
      if (!navigator.onLine) throw new Error('Sin conexión. No se enviaron cambios.');
      return fetchApi(`/admin-catalog/stock-thresholds/${row.item_id}?branch_id=${encodeURIComponent(row.branch_id)}&expected_version=${encodeURIComponent(String(row.version))}`, { method: 'DELETE' });
    },
    onSuccess: () => { setMessage('Umbrales retirados. La existencia se conserva sin cambios.'); refresh(); },
    onError: mutationFailure,
  });
  const open = (row: Threshold, trigger: HTMLElement) => {
    if (!branch) return;
    restoreFocus.current = trigger;
    setEditing({ row: { ...row }, branchName: branch.name, warehouseName: branch.warehouse_name || 'Almacén de la sucursal' });
    setDraft({}); setMessage(''); setConflict(false);
  };
  const error = editing ? thresholdDraftError(editing.row, draft) : '';
  const visibleRows = params.get('item_id') ? thresholds.data?.filter(row => row.item_id === params.get('item_id')) : thresholds.data;
  return <main className="inventory-visibility">
    <header><h1>Umbrales de existencias</h1><p>Mínimos y máximos por sucursal. Se comparan con la existencia teórica antes de reservas; guardar no ajusta inventario.</p></header>
    <InventoryScopeControl />
    {!online && <p className="inventory-state" role="alert">Sin conexión. Vuelve a conectarte para consultar o editar umbrales.</p>}
    {requestedBranch && !authorizedRequest && <p className="inventory-state" role="alert">La sucursal del enlace no está autorizada para esta consulta.</p>}
    {message && !editing && <p role="status" className="inventory-state">{message}</p>}
    {scope?.kind === 'organization' && <div className="inventory-state"><p>Selecciona una sucursal para consultar y configurar sus umbrales. La edición global no está disponible.</p><Link to="/inventory/stock">Consultar existencias de todas las sucursales</Link></div>}
    {branchId && online && <>
      <div className="inventory-toolbar"><Button variant="secondary" disabled={thresholds.isFetching} onClick={() => void thresholds.refetch()}>Actualizar</Button><Link to="/inventory/stock">Volver a Existencias</Link></div>
      {thresholds.isPending && <p role="status">Consultando umbrales…</p>}
      {thresholds.isError && <p role="alert" className="inventory-state">{failure(thresholds.error, 'No fue posible consultar los umbrales. Revisa tu conexión y actualiza.')}</p>}
      {!thresholds.isError && visibleRows && <>
        {visibleRows[0] && <p className="inventory-caption">Consulta: {inventoryDate(visibleRows[0].as_of, branch?.timezone || 'UTC')}</p>}
        <div className="inventory-table-wrap" tabIndex={0} role="region" aria-label="Umbrales por insumo"><table className="inventory-table"><thead><tr><th>Insumo</th><th>Existencia teórica</th><th>Mínimo</th><th>Máximo</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
          {visibleRows.map(row => <tr key={row.item_id}><td><strong>{row.item_name}</strong></td><td className="inventory-quantity">{formatRecipeDecimal(row.quantity_on_hand)} {row.unit_code}</td><td className="inventory-quantity">{formatRecipeDecimal(row.minimum_quantity)}</td><td className="inventory-quantity">{formatRecipeDecimal(row.maximum_quantity)}</td><td><Badge variant={row.status === 'below_minimum' ? 'warning' : row.status === 'in_range' ? 'success' : 'default'}>{labels[row.status]}</Badge></td><td><div className="inventory-modal-actions"><Button variant="ghost" size="sm" aria-label={`Editar umbrales de ${row.item_name}`} onClick={event => open(row, event.currentTarget)}><Edit size={16} /></Button>{row.version !== null && <Button variant="ghost" size="sm" aria-label={`Retirar umbrales de ${row.item_name}`} disabled={remove.isPending} onClick={() => remove.mutate(row)}><Trash2 size={16} /></Button>}</div></td></tr>)}
        </tbody></table></div>
        {!visibleRows.length && <p className="inventory-state">No hay insumos activos que coincidan con esta consulta.</p>}
      </>}
    </>}
    <Modal isOpen={Boolean(editing)} onClose={() => { if (!save.isPending) setEditing(null); }} title={editing ? `Umbrales: ${editing.row.item_name}` : 'Umbrales'}>
      {editing && <div ref={modalBody} className="inventory-modal-fields">
        <p><strong>{editing.branchName}</strong> · {editing.warehouseName}<br />Unidad base: {editing.row.unit_code}. Los límites incluyen los valores iguales al mínimo o máximo.</p>
        <label htmlFor="threshold-minimum">Mínimo<Input id="threshold-minimum" inputMode="decimal" value={draft.minimum ?? (editing.row.minimum_quantity === null ? '' : formatRecipeDecimal(editing.row.minimum_quantity))}
          aria-describedby="threshold-validation" aria-invalid={Boolean(error)} disabled={save.isPending || conflict}
          onChange={event => setDraft(current => ({ ...current, minimum: event.target.value }))} /></label>
        <label htmlFor="threshold-maximum">Máximo<Input id="threshold-maximum" inputMode="decimal" value={draft.maximum ?? (editing.row.maximum_quantity === null ? '' : formatRecipeDecimal(editing.row.maximum_quantity))}
          aria-describedby="threshold-validation" aria-invalid={Boolean(error)} disabled={save.isPending || conflict}
          onChange={event => setDraft(current => ({ ...current, maximum: event.target.value }))} /></label>
        <p id="threshold-validation" role={error ? 'alert' : undefined}>{error || 'Puedes capturar hasta dos decimales. Los valores sin cambios conservan su precisión original.'}</p>
        {message && <p role="alert">{message}</p>}
        <div className="inventory-modal-actions"><Button variant="secondary" disabled={save.isPending} onClick={() => setEditing(null)}>Cancelar</Button><Button disabled={!online || save.isPending || Boolean(error) || conflict} onClick={() => save.mutate()}>{save.isPending ? 'Guardando…' : 'Guardar umbrales'}</Button></div>
      </div>}
    </Modal>
  </main>;
}
