import React, { useState } from 'react';
import { Button } from './Button';
import { usePythonPreview, type WorkspaceRequest } from './usePythonPreview';
export interface PresentationItem { id: string; name: string; base_unit_id: string; base_unit_code?: string; unit_code?: string }
export interface PresentationUnit { id: string; code: string; name?: string }
export function ContextualPresentationForm({ supplierId, branchId, items, units, request, onSaved, onCancel }: {
  supplierId: string; branchId: string; items: PresentationItem[]; units: PresentationUnit[];
  request: WorkspaceRequest; onSaved: () => void | Promise<void>; onCancel: () => void;
}) {
  const [form, setForm] = useState({ item_id: '', commercial_unit_id: '', name: '', code: '', base_unit_yield: '', usable_content: '', last_net_price: '0', tax_rate: '0' });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const item = items.find(row => row.id === form.item_id);
  const payload = { ...form, supplier_id: supplierId, branch_id: branchId, base_unit_id: item?.base_unit_id || '', commercial_quantity: '1', yield_percent: '1' };
  const preview = usePythonPreview<{ cost_per_base_unit: string }>(request, '/purchase-presentations/preview', payload);
  const save = async () => {
    if (pending || !preview.data) return;
    setPending(true); setError('');
    try {
      await request('/purchase-presentations', { method: 'POST', body: JSON.stringify(payload) });
      await onSaved();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo registrar la presentación.'); }
    finally { setPending(false); }
  };
  return <section aria-label="Alta contextual de presentación" style={{ border: '1px solid #94a3b8', padding: 16, borderRadius: 8 }}>
    <h4>Nueva presentación del proveedor seleccionado</h4>
    <fieldset disabled={pending} className="purchase-fields">
      <label>Insumo base<select value={form.item_id} onChange={e => setForm({ ...form, item_id: e.target.value, base_unit_yield: '', usable_content: '' })}><option value="">Selecciona insumo</option>{items.map(row => <option key={row.id} value={row.id}>{row.name} · {row.base_unit_code || row.unit_code}</option>)}</select></label>
      <label>Unidad comercial<select value={form.commercial_unit_id} onChange={e => setForm({ ...form, commercial_unit_id: e.target.value })}><option value="">Selecciona unidad</option>{units.map(row => <option key={row.id} value={row.id}>{row.name || row.code}</option>)}</select></label>
      {(['name', 'code', 'base_unit_yield', 'usable_content', 'last_net_price', 'tax_rate'] as const).map((key, index) => <label key={key}>{['Nombre', 'Código (opcional)', 'Entrada por presentación en unidad base', 'Contenido útil en unidad base', 'Precio informativo ($)', 'Tasa de impuesto (fracción; 0 permitido)'][index]}<input value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} /></label>)}
    </fieldset>
    <p>Unidad base: {item?.base_unit_code || item?.unit_code || 'Selecciona insumo'} · costo informativo por unidad útil: {preview.data?.cost_per_base_unit ?? 'Pendiente'}</p>
    <p>Esta alta permanece en el catálogo aunque cierres la compra. El inventario cambia al confirmar la recepción.</p>
    {(error || preview.error) && <p role="alert">{error || preview.error}</p>}
    <Button disabled={pending || !preview.data} onClick={() => void save()}>{pending ? 'Registrando…' : 'Registrar presentación'}</Button> <Button variant="secondary" disabled={pending} onClick={onCancel}>Volver a la nota</Button>
  </section>;
}
