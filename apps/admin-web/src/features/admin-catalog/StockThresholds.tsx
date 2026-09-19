import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Button, Modal } from '@restaurantos/ui';
import { Edit, Trash2 } from 'lucide-react';
import { resolveBranchId } from '../../lib/branchContext';
import '../../premium-catalogs.css';

type Threshold = {
  item_id: string; item_name: string; branch_id: string; warehouse_id: string; unit_id: string; unit_code: string;
  quantity_on_hand: string; minimum_quantity: string | null; maximum_quantity: string | null; version: number | null;
  status: 'no_thresholds' | 'below_minimum' | 'in_range' | 'above_maximum'; as_of: string;
};
const labels: Record<Threshold['status'], string> = { no_thresholds: 'Sin umbrales', below_minimum: 'Bajo mínimo', in_range: 'En rango', above_maximum: 'Sobre máximo' };
const failure = (reason: unknown, fallback: string) => reason instanceof ApiError ? reason.message : fallback;

export default function StockThresholds() {
  const branchId = resolveBranchId();
  const client = useQueryClient();
  const [editing, setEditing] = useState<Threshold | null>(null);
  const [minimum, setMinimum] = useState('');
  const [maximum, setMaximum] = useState('');
  const [message, setMessage] = useState('');
  const thresholds = useQuery<Threshold[]>({
    queryKey: ['admin-catalog', 'stock-thresholds', branchId],
    queryFn: () => fetchApi(`/admin-catalog/stock-thresholds?branch_id=${encodeURIComponent(branchId)}`),
    enabled: Boolean(branchId),
  });
  const refresh = () => void client.invalidateQueries({ queryKey: ['admin-catalog', 'stock-thresholds', branchId] });
  const save = useMutation({
    mutationFn: () => fetchApi(`/admin-catalog/stock-thresholds/${editing?.item_id}?branch_id=${encodeURIComponent(branchId)}`, {
      method: 'PUT', body: JSON.stringify({ minimum_quantity: minimum, maximum_quantity: maximum, expected_version: editing?.version ?? null }),
    }),
    onSuccess: () => { setMessage('Umbrales guardados. La existencia se conserva sin cambios.'); setEditing(null); refresh(); },
    onError: (reason) => setMessage(failure(reason, 'No fue posible guardar los umbrales.')),
  });
  const remove = useMutation({
    mutationFn: (row: Threshold) => fetchApi(`/admin-catalog/stock-thresholds/${row.item_id}?branch_id=${encodeURIComponent(branchId)}&expected_version=${encodeURIComponent(String(row.version))}`, { method: 'DELETE' }),
    onSuccess: () => { setMessage('Umbrales retirados. La existencia se conserva sin cambios.'); refresh(); },
    onError: (reason) => setMessage(failure(reason, 'No fue posible retirar los umbrales.')),
  });
  const open = (row: Threshold) => { setEditing(row); setMinimum(row.minimum_quantity ?? ''); setMaximum(row.maximum_quantity ?? ''); setMessage(''); };

  if (!branchId) return <p role="alert">Selecciona una sucursal antes de configurar umbrales.</p>;
  if (thresholds.isLoading) return <p role="status">Comparando inventario teórico y umbrales…</p>;
  if (thresholds.isError) return <p role="alert">No fue posible consultar los umbrales. Reintenta la consulta.</p>;

  return (
    <main className="admin-catalog-tool">
      <header className="admin-catalog-tool__header"><div><h1 className="premium-header-title">Umbrales de existencias</h1><p className="premium-header-subtitle">Consulta por sucursal. Las cantidades provienen del stock teórico canónico; este formulario nunca ajusta inventario.</p></div></header>
      {message && <p className="admin-catalog-message" role="status">{message}</p>}
      <div className="premium-card" style={{ overflowX: 'auto' }}><table className="premium-table"><thead><tr><th>Insumo</th><th>Existencia teórica</th><th>Mínimo</th><th>Máximo</th><th>Estado</th><th>Consulta</th><th><span className="sr-only">Acciones</span></th></tr></thead><tbody>
        {(thresholds.data || []).map((row) => <tr key={row.item_id}><td><strong>{row.item_name}</strong></td><td>{row.quantity_on_hand} {row.unit_code}</td><td>{row.minimum_quantity ?? '—'}</td><td>{row.maximum_quantity ?? '—'}</td><td>{labels[row.status]}</td><td>{row.as_of}</td><td><span className="admin-catalog-order-actions"><button type="button" aria-label={`Editar umbrales de ${row.item_name}`} onClick={() => open(row)}><Edit size={16} /></button>{row.version !== null && <button type="button" aria-label={`Retirar umbrales de ${row.item_name}`} disabled={remove.isPending} onClick={() => remove.mutate(row)}><Trash2 size={16} /></button>}</span></td></tr>)}
      </tbody></table></div>
      {!thresholds.data?.length && <p className="premium-empty-state">No hay insumos activos en el almacén de la sucursal seleccionada.</p>}
      <Modal isOpen={Boolean(editing)} onClose={() => setEditing(null)} title={editing ? `Umbrales: ${editing.item_name}` : 'Umbrales'}>
        <div className="premium-form-layout"><p className="premium-form-hint">Unidad base: {editing?.unit_code}. El rango incluye los valores iguales al mínimo o máximo.</p><label className="premium-form-group">Mínimo<input value={minimum} inputMode="decimal" onChange={(event) => setMinimum(event.target.value)} /></label><label className="premium-form-group">Máximo<input value={maximum} inputMode="decimal" onChange={(event) => setMaximum(event.target.value)} /></label><div className="premium-footer-actions"><Button variant="secondary" onClick={() => setEditing(null)}>Cancelar</Button><Button variant="primary" disabled={save.isPending || !minimum || !maximum} onClick={() => save.mutate()}>{save.isPending ? 'Guardando…' : 'Guardar umbrales'}</Button></div></div>
      </Modal>
    </main>
  );
}
