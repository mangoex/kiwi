import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, Plus, RotateCcw, Trash2 } from 'lucide-react';
import '../../premium-catalogs.css';
import { resolveBranchId } from '../../lib/branchContext';

interface Item { id: string; name: string; sku: string; base_unit_id: string; unit_code: string; status: string; }
interface Reason { id: string; code: string; name: string; classification: string; status: string; }
interface Movement { id: string; movement_type: string; quantity_delta: number; total_cost: number; }
interface Waste { id: string; item_name: string; item_sku: string; unit_code: string; reason_name: string; stage: string; quantity: number; unit_cost: number; total_cost: number; effective_at: string; evidence: string[]; notes?: string; status: string; created_by: string; confirmed_by?: string; movements: Movement[]; }

const WasteList = () => {
  const branchId = resolveBranchId();
  const queryClient = useQueryClient();
  const [wasteOpen, setWasteOpen] = useState(false);
  const [reasonOpen, setReasonOpen] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ item_id: '', reason_id: '', quantity: '', stage: 'storage', effective_at: '', notes: '', evidence: '' });
  const [reasonForm, setReasonForm] = useState({ code: '', name: '', classification: 'operation' });
  const { data: items = [] } = useQuery<Item[]>({ queryKey: ['inventory', 'items'], queryFn: () => fetchApi('/inventory/items') });
  const { data: reasons = [] } = useQuery<Reason[]>({ queryKey: ['waste-reasons'], queryFn: () => fetchApi('/inventory/waste-reasons') });
  const { data: wastes = [] } = useQuery<Waste[]>({
    queryKey: ['wastes', branchId],
    queryFn: () => fetchApi(`/inventory/wastes?branch_id=${branchId}`),
    enabled: Boolean(branchId),
  });
  const selectedItem = items.find((item) => item.id === form.item_id);
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['wastes'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory-costs'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'stock'] }),
    ]);
  };
  const createMutation = useMutation({
    mutationFn: () => fetchApi('/inventory/wastes', { method: 'POST', body: JSON.stringify({
      branch_id: branchId, item_id: form.item_id, unit_id: selectedItem?.base_unit_id,
      reason_id: form.reason_id, quantity: form.quantity, stage: form.stage,
      effective_at: form.effective_at || undefined, notes: form.notes || undefined,
      evidence: form.evidence.split(',').map((value) => value.trim()).filter(Boolean),
    }) }),
    onSuccess: async () => { setWasteOpen(false); setForm({ item_id: '', reason_id: '', quantity: '', stage: 'storage', effective_at: '', notes: '', evidence: '' }); setError(''); await refresh(); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible registrar la merma.'),
  });
  const reasonMutation = useMutation({
    mutationFn: () => fetchApi('/inventory/waste-reasons', { method: 'POST', body: JSON.stringify(reasonForm) }),
    onSuccess: async (created: unknown) => { const reason = created as Reason; setForm({ ...form, reason_id: reason.id }); setReasonOpen(false); setReasonForm({ code: '', name: '', classification: 'operation' }); setError(''); await queryClient.invalidateQueries({ queryKey: ['waste-reasons'] }); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible crear el motivo.'),
  });
  const confirmWaste = async (wasteId: string) => {
    const storageKey = `waste_confirmation_${wasteId}`;
    const key = localStorage.getItem(storageKey) || `waste:${wasteId}:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, key);
    try {
      await fetchApi(`/inventory/wastes/${wasteId}/confirm`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: '{}' });
      localStorage.removeItem(storageKey); setError(''); await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No fue posible confirmar la merma.'); }
  };
  const reverseWaste = async (wasteId: string) => {
    const reason = window.prompt('Motivo obligatorio de la reversa');
    if (!reason) return;
    const storageKey = `waste_reversal_${wasteId}`;
    const key = localStorage.getItem(storageKey) || `waste-reversal:${wasteId}:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, key);
    try {
      await fetchApi(`/inventory/wastes/${wasteId}/reverse`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ reason }) });
      localStorage.removeItem(storageKey); setError(''); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No fue posible revertir la merma.'); }
  };

  return <>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
      <div><h1 className="premium-header-title">Mermas reales</h1><p className="premium-header-subtitle">Captura, autoriza y corrige pérdidas mediante movimientos auditables.</p></div>
      <div style={{ display: 'flex', gap: 8 }}><Button variant="secondary" onClick={() => setReasonOpen(true)}><Plus size={16} /> Motivo</Button><Button variant="primary" onClick={() => setWasteOpen(true)} disabled={!branchId}><Trash2 size={16} /> Registrar merma</Button></div>
    </div>
    {!branchId && <div role="alert" style={{ color: '#b91c1c', marginBottom: 16 }}>Selecciona o asigna una sucursal.</div>}
    {error && <div role="alert" style={{ color: '#b91c1c', marginBottom: 16 }}>{error}</div>}
    <div className="premium-card" style={{ overflowX: 'auto' }}><table className="premium-table"><thead><tr><th>Fecha</th><th>Artículo</th><th>Motivo / etapa</th><th>Cantidad</th><th>Costo</th><th>Evidencia</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{wastes.map((waste) => <tr key={waste.id}><td>{new Date(waste.effective_at).toLocaleString('es-MX')}</td><td><strong>{waste.item_name}</strong><br /><small>{waste.item_sku}</small></td><td>{waste.reason_name}<br /><small>{waste.stage}</small></td><td>{Number(waste.quantity)} {waste.unit_code}</td><td>${Number(waste.total_cost).toFixed(2)}<br /><small>${Number(waste.unit_cost).toFixed(4)} / {waste.unit_code}</small></td><td>{waste.evidence.length ? `${waste.evidence.length} referencia(s)` : 'Sin evidencia'}</td><td><Badge variant={waste.status === 'confirmed' ? 'success' : waste.status === 'draft' ? 'info' : 'default'}>{waste.status}</Badge></td><td><div style={{ display: 'flex', gap: 8 }}>{waste.status === 'draft' && <Button variant="primary" onClick={() => void confirmWaste(waste.id)}><CheckCircle2 size={15} /> Confirmar</Button>}{waste.status === 'confirmed' && <Button variant="secondary" onClick={() => void reverseWaste(waste.id)}><RotateCcw size={15} /> Revertir</Button>}</div></td></tr>)}</tbody></table></div>

    <Modal isOpen={wasteOpen} onClose={() => setWasteOpen(false)} title="Registrar merma real"><div style={{ display: 'grid', gap: 12 }}><label>Artículo<select value={form.item_id} onChange={(event) => setForm({ ...form, item_id: event.target.value })} style={{ width: '100%', padding: 10 }}><option value="">Selecciona</option>{items.filter((item) => item.status === 'active').map((item) => <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>)}</select></label><label>Motivo<select value={form.reason_id} onChange={(event) => setForm({ ...form, reason_id: event.target.value })} style={{ width: '100%', padding: 10 }}><option value="">Selecciona</option>{reasons.map((reason) => <option key={reason.id} value={reason.id}>{reason.name}</option>)}</select></label><Field label={`Cantidad ${selectedItem?.unit_code ? `(${selectedItem.unit_code})` : ''}`} value={form.quantity} setValue={(quantity) => setForm({ ...form, quantity })} /><label>Etapa<select value={form.stage} onChange={(event) => setForm({ ...form, stage: event.target.value })} style={{ width: '100%', padding: 10 }}><option value="storage">Almacenamiento</option><option value="preparation">Preparación</option><option value="service">Servicio</option><option value="receiving">Recepción</option></select></label><Field label="Fecha efectiva (opcional)" value={form.effective_at} setValue={(effective_at) => setForm({ ...form, effective_at })} type="datetime-local" /><Field label="Evidencia (referencias separadas por coma)" value={form.evidence} setValue={(evidence) => setForm({ ...form, evidence })} /><Field label="Observaciones" value={form.notes} setValue={(notes) => setForm({ ...form, notes })} /></div><div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}><Button variant="primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>Guardar borrador</Button></div></Modal>
    <Modal isOpen={reasonOpen} onClose={() => setReasonOpen(false)} title="Nuevo motivo de merma"><div style={{ display: 'grid', gap: 12 }}><Field label="Código" value={reasonForm.code} setValue={(code) => setReasonForm({ ...reasonForm, code })} /><Field label="Nombre" value={reasonForm.name} setValue={(name) => setReasonForm({ ...reasonForm, name })} /><label>Clasificación<select value={reasonForm.classification} onChange={(event) => setReasonForm({ ...reasonForm, classification: event.target.value })} style={{ width: '100%', padding: 10 }}><option value="quality">Calidad</option><option value="production">Producción</option><option value="operation">Operación</option><option value="security">Seguridad</option><option value="other">Otro</option></select></label></div><div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}><Button variant="primary" onClick={() => reasonMutation.mutate()} disabled={reasonMutation.isPending}>Crear motivo</Button></div></Modal>
  </>;
};

const Field = ({ label, value, setValue, type = 'text' }: { label: string; value: string; setValue: (value: string) => void; type?: string }) => <label style={{ display: 'grid', gap: 4 }}><span>{label}</span><Input type={type} value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValue(event.target.value)} /></label>;

export default WasteList;
