import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, ClipboardCheck, LockKeyhole, Plus, Send, XCircle, Eye, AlertCircle, Package } from 'lucide-react';
import '../../premium-catalogs.css';
import { resolveBranchId } from '../../lib/branchContext';

interface CountLine {
  id: string;
  item_name: string;
  item_sku: string;
  unit_code: string;
  counted_quantity?: number;
  theoretical_quantity?: number;
  snapshot_difference?: number;
  approval_ledger_quantity?: number;
  adjustment_quantity?: number;
  adjustment_cost?: number;
  captured_at?: string;
}

interface CountSession {
  id: string;
  folio: string;
  branch_name: string;
  status: string;
  scope: string;
  blind: boolean;
  snapshot_at: string;
  notes?: string;
  lines: CountLine[];
  movements: unknown[];
}

const statusBadge = (status: string) => {
  switch (status) {
    case 'counting':
      return <Badge variant="info">En captura física</Badge>;
    case 'submitted':
      return <Badge variant="warning">En revisión</Badge>;
    case 'approved':
      return <Badge variant="success">Ajustes aprobados</Badge>;
    case 'closed':
      return <Badge variant="default">Cerrado</Badge>;
    case 'cancelled':
      return <Badge variant="default">Cancelado</Badge>;
    default:
      return <Badge variant="default">{status}</Badge>;
  }
};

const PhysicalCountList = () => {
  const branchId = resolveBranchId();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [captureSession, setCaptureSession] = useState<CountSession | null>(null);
  const [detailSession, setDetailSession] = useState<CountSession | null>(null);
  const [captureValues, setCaptureValues] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');

  const { data: sessions = [], isLoading } = useQuery<CountSession[]>({
    queryKey: ['physical-counts', branchId],
    queryFn: () => fetchApi(`/inventory/physical-counts?branch_id=${branchId}`),
    enabled: Boolean(branchId),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['physical-counts'] });

  const createMutation = useMutation({
    mutationFn: () =>
      fetchApi('/inventory/physical-counts', {
        method: 'POST',
        body: JSON.stringify({ branch_id: branchId, notes }),
      }),
    onSuccess: async (created: unknown) => {
      setCreateOpen(false);
      setNotes('');
      setError('');
      await refresh();
      openCapture(created as CountSession);
    },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible abrir el conteo.'),
  });

  const openCapture = (session: CountSession) => {
    if (session.status !== 'counting') {
      setError('Solo los conteos en fase de captura pueden ser editados.');
      return;
    }
    setCaptureSession(session);
    setCaptureValues(
      Object.fromEntries(
        session.lines.map((line) => [
          line.id,
          line.counted_quantity === undefined || line.counted_quantity === null ? '' : String(line.counted_quantity),
        ])
      )
    );
  };

  const saveCaptures = async () => {
    if (!captureSession) return false;
    if (captureSession.lines.some((line) => captureValues[line.id] === '' || captureValues[line.id] === undefined)) {
      setError('Captura una cantidad para cada artículo. Usa cero (0) cuando no exista físicamente en almacén.');
      return false;
    }
    try {
      for (const line of captureSession.lines) {
        await fetchApi(`/inventory/physical-counts/${captureSession.id}/lines/${line.id}`, {
          method: 'PUT',
          body: JSON.stringify({ counted_quantity: captureValues[line.id] }),
        });
      }
      setError('');
      await refresh();
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible guardar las capturas.');
      return false;
    }
  };

  const submitCount = async (sessionId: string) => {
    try {
      await fetchApi(`/inventory/physical-counts/${sessionId}/submit`, { method: 'POST', body: '{}' });
      setCaptureSession(null);
      setError('');
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'El conteo está incompleto o no pudo enviarse.');
    }
  };

  const approveCount = async (sessionId: string) => {
    const storageKey = `physical_count_approval_${sessionId}`;
    const key = localStorage.getItem(storageKey) || `physical-count:${sessionId}:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, key);
    try {
      await fetchApi(`/inventory/physical-counts/${sessionId}/approve`, {
        method: 'POST',
        headers: { 'Idempotency-Key': key },
        body: '{}',
      });
      localStorage.removeItem(storageKey);
      setError('');
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible aprobar el conteo.');
    }
  };

  const closeCount = async (sessionId: string) => {
    try {
      await fetchApi(`/inventory/physical-counts/${sessionId}/close`, { method: 'POST', body: '{}' });
      setError('');
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible cerrar el conteo.');
    }
  };

  const cancelCount = async (sessionId: string) => {
    const reason = window.prompt('Motivo obligatorio de cancelación');
    if (!reason) return;
    try {
      await fetchApi(`/inventory/physical-counts/${sessionId}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) });
      setError('');
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible cancelar el conteo.');
    }
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Conteo físico</h1>
          <p className="premium-header-subtitle">
            Fotografía teórica, captura ciega y ajustes conciliados contra el ledger vigente.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => setCreateOpen(true)}
          disabled={!branchId || sessions.some((session) => ['counting', 'submitted', 'approved'].includes(session.status))}
        >
          <Plus size={16} /> Nuevo conteo
        </Button>
      </div>

      {!branchId && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>Selecciona o asigna una sucursal para auditar conteos físicos.</span>
        </div>
      )}

      {error && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      <div className="premium-card">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando conteos físicos...</div>
        ) : sessions.length === 0 ? (
          <div className="premium-empty-state">
            <Package size={56} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay conteos físicos registrados</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>
              Inicia un nuevo conteo para congelar la fotografía teórica y auditar las existencias de este almacén.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Folio</th>
                  <th>Fecha de Fotografía</th>
                  <th>Artículos</th>
                  <th>Estado de Captura</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => {
                  const withDiff = session.lines.filter((l) => Number(l.snapshot_difference || 0) !== 0).length;
                  return (
                    <tr key={session.id}>
                      <td>
                        <strong style={{ color: '#1e293b' }}>{session.folio}</strong>
                        <br />
                        <small style={{ color: '#64748b' }}>{session.branch_name}</small>
                      </td>
                      <td>{new Date(session.snapshot_at).toLocaleString('es-MX')}</td>
                      <td>
                        <strong style={{ color: '#0f172a' }}>{session.lines.length}</strong> insumos
                      </td>
                      <td>
                        {session.blind ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#64748b', fontSize: '0.85rem' }}>
                            <LockKeyhole size={14} /> Captura ciega (oculta)
                          </span>
                        ) : withDiff > 0 ? (
                          <span style={{ color: '#b91c1c', fontWeight: 600, fontSize: '0.85rem' }}>
                            ⚠️ {withDiff} {withDiff === 1 ? 'insumo con diferencia' : 'insumos con diferencia'}
                          </span>
                        ) : (
                          <span style={{ color: '#047857', fontWeight: 600, fontSize: '0.85rem' }}>
                            ✓ Sin diferencias
                          </span>
                        )}
                      </td>
                      <td>{statusBadge(session.status)}</td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
                          <Button variant="secondary" onClick={() => setDetailSession(session)} title="Ver detalle">
                            <Eye size={15} /> Detalle
                          </Button>
                          {session.status === 'counting' && (
                            <>
                              <Button variant="primary" onClick={() => openCapture(session)}>
                                <ClipboardCheck size={15} /> Capturar
                              </Button>
                              <Button variant="secondary" onClick={() => void cancelCount(session.id)} title="Cancelar conteo">
                                <XCircle size={15} />
                              </Button>
                            </>
                          )}
                          {session.status === 'submitted' && (
                            <Button variant="primary" onClick={() => void approveCount(session.id)}>
                              <CheckCircle2 size={15} /> Aprobar ajustes
                            </Button>
                          )}
                          {session.status === 'approved' && (
                            <Button variant="primary" onClick={() => void closeCount(session.id)}>
                              <CheckCircle2 size={15} /> Cerrar
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Abrir nuevo conteo */}
      <Modal isOpen={createOpen} onClose={() => setCreateOpen(false)} title="Abrir conteo físico" maxWidth="540px">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <p style={{ color: '#475569', fontSize: '0.9rem', lineHeight: 1.5, margin: 0 }}>
            Se congelará la <strong>existencia teórica</strong> de todos los insumos activos en esta sucursal. Durante la captura física no se mostrarán las cantidades del sistema (captura ciega) para garantizar una auditoría honesta.
          </p>
          <Field label="Observaciones o motivo" value={notes} setValue={setNotes} />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Congelando...' : 'Crear fotografía y abrir'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal: Captura Ciega */}
      <Modal
        isOpen={Boolean(captureSession)}
        onClose={() => setCaptureSession(null)}
        title={`Captura física ciega · ${captureSession?.folio || ''}`}
        maxWidth="680px"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <p style={{ color: '#64748b', fontSize: '0.85rem', margin: 0 }}>
            Ingresa la cantidad física encontrada en almacén para cada insumo. Si un insumo no existe físicamente, coloca <strong>0</strong>.
          </p>
          <div style={{ display: 'grid', gap: 10, maxHeight: '55vh', overflowY: 'auto', paddingRight: 6 }}>
            {captureSession?.lines.map((line) => (
              <label
                key={line.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 150px',
                  gap: 12,
                  alignItems: 'center',
                  padding: '10px 14px',
                  background: '#f8fafc',
                  borderRadius: 10,
                  border: '1px solid #e2e8f0',
                }}
              >
                <span>
                  <strong style={{ color: '#0f172a', fontSize: '0.9rem' }}>{line.item_name}</strong>
                  <br />
                  <small style={{ color: '#64748b' }}>{line.item_sku} · Unidad: {line.unit_code}</small>
                </span>
                <Input
                  type="number"
                  min={0}
                  step="any"
                  value={captureValues[line.id] || ''}
                  onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
                    setCaptureValues({ ...captureValues, [line.id]: event.target.value })
                  }
                  placeholder="Cantidad física"
                />
              </label>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
            <Button variant="secondary" onClick={() => void saveCaptures()}>
              <ClipboardCheck size={15} /> Guardar borrador
            </Button>
            <Button
              variant="primary"
              onClick={async () => {
                if ((await saveCaptures()) && captureSession) {
                  await submitCount(captureSession.id);
                }
              }}
            >
              <Send size={15} /> Enviar a revisión
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal: Detalle del Conteo Físico */}
      <Modal
        isOpen={Boolean(detailSession)}
        onClose={() => setDetailSession(null)}
        title={`Detalle de Conteo · ${detailSession?.folio || ''}`}
        maxWidth="820px"
      >
        {detailSession && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8fafc', padding: '12px 16px', borderRadius: 12, border: '1px solid #e2e8f0' }}>
              <div>
                <span style={{ fontSize: '0.8rem', color: '#64748b', display: 'block' }}>Sucursal</span>
                <strong style={{ color: '#0f172a' }}>{detailSession.branch_name}</strong>
              </div>
              <div>
                <span style={{ fontSize: '0.8rem', color: '#64748b', display: 'block' }}>Fotografía congelada</span>
                <span style={{ fontSize: '0.88rem', color: '#334155' }}>{new Date(detailSession.snapshot_at).toLocaleString('es-MX')}</span>
              </div>
              <div>
                <span style={{ fontSize: '0.8rem', color: '#64748b', display: 'block' }}>Estado</span>
                {statusBadge(detailSession.status)}
              </div>
            </div>

            <div style={{ maxHeight: '55vh', overflowY: 'auto' }}>
              <table className="premium-table" style={{ fontSize: '0.85rem' }}>
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Insumo</th>
                    <th style={{ textAlign: 'right' }}>Teórico (Foto)</th>
                    <th style={{ textAlign: 'right' }}>Físico (Contado)</th>
                    <th style={{ textAlign: 'right' }}>Diferencia</th>
                    <th style={{ textAlign: 'right' }}>Ajuste Ledger</th>
                  </tr>
                </thead>
                <tbody>
                  {detailSession.lines.map((line) => {
                    const diff = Number(line.snapshot_difference || 0);
                    const isBlind = detailSession.blind && detailSession.status === 'counting';
                    return (
                      <tr key={line.id}>
                        <td style={{ color: '#64748b', fontWeight: 600 }}>{line.item_sku}</td>
                        <td><strong style={{ color: '#1e293b' }}>{line.item_name}</strong></td>
                        <td style={{ textAlign: 'right' }}>
                          {isBlind ? '🔒 Oculto' : `${Number(line.theoretical_quantity || 0)} ${line.unit_code}`}
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 600 }}>
                          {line.counted_quantity !== null && line.counted_quantity !== undefined
                            ? `${Number(line.counted_quantity)} ${line.unit_code}`
                            : 'Pendiente'}
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 700, color: diff > 0 ? '#047857' : diff < 0 ? '#b91c1c' : '#64748b' }}>
                          {isBlind ? '🔒' : `${diff > 0 ? `+${diff}` : diff} ${line.unit_code}`}
                        </td>
                        <td style={{ textAlign: 'right', color: '#334155' }}>
                          {isBlind ? '🔒' : `${Number(line.adjustment_quantity || 0)} ${line.unit_code}`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
              <Button variant="secondary" onClick={() => setDetailSession(null)}>
                Cerrar
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
};

const Field = ({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) => (
  <label style={{ display: 'grid', gap: 6, fontWeight: 500, fontSize: '0.875rem' }}>
    <span>{label}</span>
    <Input value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValue(event.target.value)} placeholder="Ej. Conteo quincenal de cierre de mes..." />
  </label>
);

export default PhysicalCountList;
