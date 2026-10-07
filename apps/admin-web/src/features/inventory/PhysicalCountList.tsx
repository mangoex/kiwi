import { useAdminPermission } from '../../lib/adminSession';
import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Badge,
  Button,
  Input,
  Modal,
  PhysicalCountCapture,
  type PhysicalCountCaptureSession,
  type PhysicalCountLine,
  type PhysicalCountLineCapture,
} from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import {
  AlertCircle,
  CheckCircle2,
  ClipboardCheck,
  Eye,
  LockKeyhole,
  Package,
  Plus,
  XCircle,
} from 'lucide-react';
import '../../premium-catalogs.css';
import { resolveBranchId } from '../../lib/branchContext';

interface CountLine extends PhysicalCountLine {
  theoretical_quantity?: number;
  snapshot_unit_cost?: number;
  snapshot_value?: number;
  snapshot_difference?: number;
  snapshot_difference_value?: number;
  approval_ledger_quantity?: number;
  adjustment_quantity?: number;
  adjustment_cost?: number;
}

interface CountSession extends PhysicalCountCaptureSession {
  branch_name: string;
  status: string;
  scope: string;
  scope_definition: {
    category_names: string[];
    requested_item_ids: string[];
    resolved_item_ids: string[];
  };
  blind: boolean;
  can_review: boolean;
  snapshot_at: string;
  notes?: string;
  lines: CountLine[];
  summary?: {
    theoretical_value: number;
    physical_value: number;
    difference_value: number;
  };
  movements: unknown[];
}

interface CountOptions {
  groups: Array<{ name: string; item_count: number }>;
  items: Array<{ id: string; name: string; sku: string; category_name: string }>;
}

const money = (value?: number) =>
  new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(Number(value || 0));

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
  const canCapture = useAdminPermission('inventory.count.capture');
  const canApprove = useAdminPermission('inventory.count.approve');
  const branchId = resolveBranchId();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [captureSession, setCaptureSession] = useState<CountSession | null>(null);
  const [detailSession, setDetailSession] = useState<CountSession | null>(null);
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [captureBusy, setCaptureBusy] = useState(false);

  const { data: sessions = [], isLoading } = useQuery<CountSession[]>({
    queryKey: ['physical-counts', branchId],
    queryFn: () => fetchApi(`/inventory/physical-counts?branch_id=${encodeURIComponent(branchId || '')}`),
    enabled: Boolean(branchId),
  });
  const { data: options } = useQuery<CountOptions>({
    queryKey: ['physical-count-options', branchId],
    queryFn: () => fetchApi(`/inventory/physical-counts/options?branch_id=${encodeURIComponent(branchId || '')}`),
    enabled: Boolean(branchId) && createOpen,
  });

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['physical-counts'] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      fetchApi('/inventory/physical-counts', {
        method: 'POST',
        body: JSON.stringify({ branch_id: branchId, notes, category_names: selectedGroups }),
      }),
    onSuccess: async (created: unknown) => {
      setCreateOpen(false);
      setNotes('');
      setSelectedGroups([]);
      setError('');
      setCaptureSession(created as CountSession);
      await refresh();
    },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible abrir el conteo.'),
  });

  const saveCapture = async (capture: PhysicalCountLineCapture): Promise<PhysicalCountCaptureSession> => {
    if (!captureSession) throw new Error('No hay un conteo activo.');
    setCaptureBusy(true);
    try {
      const updated = await fetchApi<CountSession>(
        `/inventory/physical-counts/${captureSession.id}/lines/${capture.line_id}/entries`,
        {
          method: 'PUT',
          body: JSON.stringify({
            expected_version: capture.expected_version,
            entries: capture.entries,
          }),
        },
      );
      setCaptureSession(updated);
      setError('');
      await refresh();
      return updated;
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'No fue posible guardar la captura.';
      setError(message);
      throw reason;
    } finally {
      setCaptureBusy(false);
    }
  };

  const submitCount = async () => {
    if (!captureSession) return;
    setCaptureBusy(true);
    try {
      await fetchApi(`/inventory/physical-counts/${captureSession.id}/submit`, { method: 'POST', body: '{}' });
      setCaptureSession(null);
      setError('');
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'El conteo está incompleto o no pudo enviarse.');
      throw reason;
    } finally {
      setCaptureBusy(false);
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
      await fetchApi(`/inventory/physical-counts/${sessionId}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      setError('');
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible cancelar el conteo.');
    }
  };

  const toggleGroup = (group: string) => {
    setSelectedGroups((current) =>
      current.includes(group) ? current.filter((item) => item !== group) : [...current, group],
    );
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Conteo físico</h1>
          <p className="premium-header-subtitle">
            Configura el alcance, supervisa la captura ciega y autoriza diferencias contra el ledger vigente.
          </p>
        </div>
        {canCapture && <Button
          variant="primary"
          onClick={() => setCreateOpen(true)}
          disabled={!branchId || sessions.some((session) => ['counting', 'submitted', 'approved'].includes(session.status))}
        >
          <Plus size={16} /> Nuevo conteo
        </Button>}
      </div>

      {!branchId && (
        <div role="alert" style={alertStyle}>
          <AlertCircle size={18} /> Selecciona o asigna una sucursal para auditar conteos físicos.
        </div>
      )}
      {error && (
        <div role="alert" style={alertStyle}>
          <AlertCircle size={18} /> {error}
        </div>
      )}

      <div className="premium-card">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando conteos físicos…</div>
        ) : sessions.length === 0 ? (
          <div className="premium-empty-state">
            <Package size={56} className="premium-empty-icon" />
            <h3>No hay conteos físicos registrados</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Abre un conteo por grupos o para todo el almacén.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Folio</th>
                  <th>Fotografía</th>
                  <th>Alcance</th>
                  <th>Avance</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => {
                  const completed = session.lines.filter((line) => line.counted_quantity !== null && line.counted_quantity !== undefined).length;
                  return (
                    <tr key={session.id}>
                      <td><strong>{session.folio}</strong><br /><small>{session.branch_name}</small></td>
                      <td>{new Date(session.snapshot_at).toLocaleString('es-MX')}</td>
                      <td>{session.scope === 'groups' ? session.scope_definition.category_names.join(', ') : session.scope === 'all_active' ? 'Todo el almacén' : 'Selección'}</td>
                      <td>{completed} / {session.lines.length}</td>
                      <td>{statusBadge(session.status)}</td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                          <Button variant="secondary" onClick={() => setDetailSession(session)}><Eye size={15} /> Detalle</Button>
                          {session.status === 'counting' && (
                            <>
                              {canCapture && <Button variant="primary" onClick={() => setCaptureSession(session)}><ClipboardCheck size={15} /> Capturar</Button>}
                              {canApprove && <Button variant="secondary" onClick={() => void cancelCount(session.id)} title="Cancelar conteo"><XCircle size={15} /> Cancelar</Button>}
                            </>
                          )}
                          {session.status === 'submitted' && (
                            (canApprove ? <Button variant="primary" onClick={() => void approveCount(session.id)}><CheckCircle2 size={15} /> Aprobar ajustes</Button> : null)
                          )}
                          {session.status === 'approved' && (
                            (canApprove ? <Button variant="primary" onClick={() => void closeCount(session.id)}><CheckCircle2 size={15} /> Cerrar</Button> : null)
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

      <Modal isOpen={createOpen} onClose={() => setCreateOpen(false)} title="Abrir conteo físico" maxWidth="620px">
        <div style={{ display: 'grid', gap: 16 }}>
          <div style={{ padding: 12, borderRadius: 10, background: '#eff6ff', color: '#1e40af', fontSize: 14 }}>
            <LockKeyhole size={15} style={{ verticalAlign: 'text-bottom', marginRight: 6 }} />
            La fecha y la fotografía las fija el servidor. Durante la captura no se muestran existencias ni costos.
          </div>
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend style={{ fontWeight: 700, marginBottom: 10 }}>Grupos a contar</legend>
            <label style={groupStyle}>
              <input type="checkbox" checked={selectedGroups.length === 0} onChange={() => setSelectedGroups([])} />
              <span><strong>Todos los grupos</strong><br /><small>Incluye todos los insumos activos del almacén.</small></span>
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 8, marginTop: 8 }}>
              {options?.groups.map((group) => (
                <label key={group.name} style={groupStyle}>
                  <input type="checkbox" checked={selectedGroups.includes(group.name)} onChange={() => toggleGroup(group.name)} />
                  <span><strong>{group.name}</strong><br /><small>{group.item_count} insumos</small></span>
                </label>
              ))}
            </div>
          </fieldset>
          <label style={{ display: 'grid', gap: 6, fontWeight: 600, fontSize: 14 }}>
            Observaciones
            <Input value={notes} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setNotes(event.target.value)} placeholder="Ej. Conteo quincenal" />
          </label>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancelar</Button>
            <Button variant="primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Preparando insumos…' : 'Abrir conteo'}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={Boolean(captureSession)}
        onClose={() => setCaptureSession(null)}
        title="Captura física ciega"
        maxWidth="1040px"
      >
        {captureSession && (
          <PhysicalCountCapture
            session={captureSession}
            busy={captureBusy}
            onSave={saveCapture}
            onSubmit={submitCount}
          />
        )}
      </Modal>

      <Modal
        isOpen={Boolean(detailSession)}
        onClose={() => setDetailSession(null)}
        title={`Detalle de conteo · ${detailSession?.folio || ''}`}
        maxWidth="1080px"
      >
        {detailSession && <CountDetail session={detailSession} />}
      </Modal>
    </>
  );
};

const CountDetail = ({ session }: { session: CountSession }) => (
  <div style={{ display: 'grid', gap: 16 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', padding: 12, borderRadius: 10, background: '#f8fafc' }}>
      <span><small>Sucursal</small><br /><strong>{session.branch_name}</strong></span>
      <span><small>Fotografía</small><br />{new Date(session.snapshot_at).toLocaleString('es-MX')}</span>
      <span><small>Estado</small><br />{statusBadge(session.status)}</span>
    </div>
    {session.summary && (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10 }}>
        <Summary label="Inventario teórico" value={money(session.summary.theoretical_value)} />
        <Summary label="Inventario físico" value={money(session.summary.physical_value)} />
        <Summary label="Diferencia" value={money(session.summary.difference_value)} emphasis={Number(session.summary.difference_value) !== 0} />
      </div>
    )}
    <div style={{ overflowX: 'auto', maxHeight: '58vh' }}>
      <table className="premium-table" style={{ fontSize: 13 }}>
        <thead><tr><th>Insumo</th><th>Presentaciones capturadas</th><th style={{ textAlign: 'right' }}>Teórico</th><th style={{ textAlign: 'right' }}>Físico</th><th style={{ textAlign: 'right' }}>Diferencia</th><th style={{ textAlign: 'right' }}>Importe</th></tr></thead>
        <tbody>
          {session.lines.map((line) => (
            <tr key={line.id}>
              <td><strong>{line.item_name}</strong><br /><small>{line.item_sku} · {line.category_name || 'Sin grupo'}</small></td>
              <td>
                {line.entries.length === 0 ? 'Sin captura' : line.entries.map((entry, index) => (
                  <span key={`${entry.presentation_id || 'base'}-${index}`} style={{ display: 'block' }}>
                    {entry.quantity} {entry.presentation_name_snapshot || line.unit_code}
                    {entry.presentation_id ? ` = ${entry.converted_quantity} ${line.unit_code}` : ''}
                  </span>
                ))}
              </td>
              <td style={{ textAlign: 'right' }}>{session.blind ? 'Oculto' : `${Number(line.theoretical_quantity || 0)} ${line.unit_code}`}</td>
              <td style={{ textAlign: 'right', fontWeight: 700 }}>{line.counted_quantity == null ? 'Pendiente' : `${Number(line.counted_quantity)} ${line.unit_code}`}</td>
              <td style={{ textAlign: 'right' }}>{session.blind ? 'Oculta' : `${Number(line.snapshot_difference || 0)} ${line.unit_code}`}</td>
              <td style={{ textAlign: 'right' }}>{session.blind ? 'Oculto' : money(line.snapshot_difference_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

const Summary = ({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) => (
  <div style={{ padding: 14, border: `1px solid ${emphasis ? '#fca5a5' : '#e2e8f0'}`, borderRadius: 10, background: emphasis ? '#fef2f2' : '#fff' }}>
    <small style={{ color: '#64748b' }}>{label}</small><br />
    <strong style={{ fontSize: 20, color: emphasis ? '#b91c1c' : '#0f172a' }}>{value}</strong>
  </div>
);

const alertStyle: React.CSSProperties = {
  background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px',
  borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8,
};

const groupStyle: React.CSSProperties = {
  display: 'flex', gap: 9, alignItems: 'flex-start', border: '1px solid #e2e8f0',
  borderRadius: 10, padding: 10, cursor: 'pointer', color: '#334155',
};

export default PhysicalCountList;
