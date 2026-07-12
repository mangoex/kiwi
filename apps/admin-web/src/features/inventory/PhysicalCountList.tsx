import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, ClipboardCheck, LockKeyhole, Plus, Send, XCircle } from 'lucide-react';
import '../../premium-catalogs.css';
import { resolveBranchId } from '../../lib/branchContext';

interface CountLine { id: string; item_name: string; item_sku: string; unit_code: string; counted_quantity?: number; theoretical_quantity?: number; snapshot_difference?: number; approval_ledger_quantity?: number; adjustment_quantity?: number; adjustment_cost?: number; captured_at?: string; }
interface CountSession { id: string; folio: string; branch_name: string; status: string; scope: string; blind: boolean; snapshot_at: string; notes?: string; lines: CountLine[]; movements: unknown[]; }

const PhysicalCountList = () => {
  const branchId = resolveBranchId();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [captureSession, setCaptureSession] = useState<CountSession | null>(null);
  const [captureValues, setCaptureValues] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const { data: sessions = [] } = useQuery<CountSession[]>({
    queryKey: ['physical-counts', branchId],
    queryFn: () => fetchApi(`/inventory/physical-counts?branch_id=${branchId}`),
    enabled: Boolean(branchId),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['physical-counts'] });
  const createMutation = useMutation({
    mutationFn: () => fetchApi('/inventory/physical-counts', { method: 'POST', body: JSON.stringify({ branch_id: branchId, notes }) }),
    onSuccess: async (created: unknown) => { setCreateOpen(false); setNotes(''); setError(''); await refresh(); openCapture(created as CountSession); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible abrir el conteo.'),
  });
  const openCapture = (session: CountSession) => {
    setCaptureSession(session);
    setCaptureValues(Object.fromEntries(session.lines.map((line) => [line.id, line.counted_quantity === undefined || line.counted_quantity === null ? '' : String(line.counted_quantity)])));
  };
  const saveCaptures = async () => {
    if (!captureSession) return;
    if (captureSession.lines.some((line) => captureValues[line.id] === '' || captureValues[line.id] === undefined)) {
      setError('Captura una cantidad para cada artículo. Usa cero cuando no exista físicamente.'); return false;
    }
    try {
      for (const line of captureSession.lines) {
        await fetchApi(`/inventory/physical-counts/${captureSession.id}/lines/${line.id}`, { method: 'PUT', body: JSON.stringify({ counted_quantity: captureValues[line.id] }) });
      }
      setError(''); await refresh(); return true;
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No fue posible guardar las capturas.'); return false; }
  };
  const submitCount = async (sessionId: string) => {
    try { await fetchApi(`/inventory/physical-counts/${sessionId}/submit`, { method: 'POST', body: '{}' }); setCaptureSession(null); setError(''); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'El conteo está incompleto.'); }
  };
  const approveCount = async (sessionId: string) => {
    const storageKey = `physical_count_approval_${sessionId}`;
    const key = localStorage.getItem(storageKey) || `physical-count:${sessionId}:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, key);
    try { await fetchApi(`/inventory/physical-counts/${sessionId}/approve`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: '{}' }); localStorage.removeItem(storageKey); setError(''); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No fue posible aprobar el conteo.'); }
  };
  const closeCount = async (sessionId: string) => {
    try { await fetchApi(`/inventory/physical-counts/${sessionId}/close`, { method: 'POST', body: '{}' }); setError(''); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No fue posible cerrar el conteo.'); }
  };
  const cancelCount = async (sessionId: string) => {
    const reason = window.prompt('Motivo obligatorio de cancelación');
    if (!reason) return;
    try { await fetchApi(`/inventory/physical-counts/${sessionId}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) }); setError(''); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'No fue posible cancelar el conteo.'); }
  };

  return <>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}><div><h1 className="premium-header-title">Conteo físico</h1><p className="premium-header-subtitle">Fotografía teórica, captura ciega y ajustes conciliados contra el ledger vigente.</p></div><Button variant="primary" onClick={() => setCreateOpen(true)} disabled={!branchId || sessions.some((session) => ['counting', 'submitted', 'approved'].includes(session.status))}><Plus size={16} /> Nuevo conteo</Button></div>
    {!branchId && <div role="alert" style={{ color: '#b91c1c', marginBottom: 16 }}>Selecciona o asigna una sucursal.</div>}
    {error && <div role="alert" style={{ color: '#b91c1c', marginBottom: 16 }}>{error}</div>}
    <div className="premium-card" style={{ overflowX: 'auto' }}><table className="premium-table"><thead><tr><th>Folio</th><th>Fotografía</th><th>Artículos</th><th>Diferencia foto</th><th>Ajuste real</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{sessions.map((session) => <tr key={session.id}><td><strong>{session.folio}</strong><br /><small>{session.branch_name}</small></td><td>{new Date(session.snapshot_at).toLocaleString('es-MX')}</td><td>{session.lines.length}</td><td>{session.blind ? <span><LockKeyhole size={14} /> Oculta</span> : session.lines.reduce((sum, line) => sum + Number(line.snapshot_difference || 0), 0)}</td><td>{session.lines.reduce((sum, line) => sum + Number(line.adjustment_quantity || 0), 0)}</td><td><Badge variant={session.status === 'closed' ? 'success' : session.status === 'submitted' || session.status === 'approved' ? 'info' : 'default'}>{session.status}</Badge></td><td><div style={{ display: 'flex', gap: 8 }}>{session.status === 'counting' && <><Button variant="primary" onClick={() => openCapture(session)}><ClipboardCheck size={15} /> Capturar</Button><Button variant="secondary" onClick={() => void cancelCount(session.id)}><XCircle size={15} /></Button></>}{session.status === 'submitted' && <Button variant="primary" onClick={() => void approveCount(session.id)}><CheckCircle2 size={15} /> Aprobar ajustes</Button>}{session.status === 'approved' && <Button variant="primary" onClick={() => void closeCount(session.id)}><CheckCircle2 size={15} /> Cerrar</Button>}</div></td></tr>)}</tbody></table></div>

    <Modal isOpen={createOpen} onClose={() => setCreateOpen(false)} title="Abrir conteo físico"><p>Se congelará la existencia teórica y costo de todos los artículos activos. Durante la captura no se mostrarán esas cantidades.</p><Field label="Observaciones" value={notes} setValue={setNotes} /><div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}><Button variant="primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>Crear fotografía</Button></div></Modal>
    <Modal isOpen={Boolean(captureSession)} onClose={() => setCaptureSession(null)} title={`Captura ciega ${captureSession?.folio || ''}`}><div style={{ display: 'grid', gap: 10, maxHeight: '60vh', overflowY: 'auto' }}>{captureSession?.lines.map((line) => <label key={line.id} style={{ display: 'grid', gridTemplateColumns: '1fr 140px', gap: 10, alignItems: 'center' }}><span><strong>{line.item_name}</strong><br /><small>{line.item_sku} · {line.unit_code}</small></span><Input type="number" min={0} step="any" value={captureValues[line.id] || ''} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setCaptureValues({ ...captureValues, [line.id]: event.target.value })} placeholder="Cantidad física" /></label>)}</div><div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}><Button variant="secondary" onClick={() => void saveCaptures()}><ClipboardCheck size={15} /> Guardar</Button><Button variant="primary" onClick={async () => { if (await saveCaptures() && captureSession) await submitCount(captureSession.id); }}><Send size={15} /> Enviar a revisión</Button></div></Modal>
  </>;
};

const Field = ({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) => <label style={{ display: 'grid', gap: 4 }}><span>{label}</span><Input value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValue(event.target.value)} /></label>;

export default PhysicalCountList;
