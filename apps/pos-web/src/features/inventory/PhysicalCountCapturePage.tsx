import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Badge,
  Button,
  PhysicalCountCapture,
  type PhysicalCountCaptureSession,
  type PhysicalCountLine,
  type PhysicalCountLineCapture,
} from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { AlertTriangle, ClipboardCheck, LockKeyhole, PackageCheck, WifiOff } from 'lucide-react';
import { usePosSession } from '../../session';

interface CountSession extends PhysicalCountCaptureSession {
  snapshot_at: string;
  scope: string;
  scope_definition: { category_names: string[] };
  blind: boolean;
  lines: PhysicalCountLine[];
}

interface CountOptions {
  groups: Array<{ name: string; item_count: number }>;
}

const statusLabel = (status: string) => {
  if (status === 'counting') return <Badge variant="info">En captura</Badge>;
  if (status === 'submitted') return <Badge variant="warning">En revisión administrativa</Badge>;
  if (status === 'approved') return <Badge variant="success">Ajustes aprobados</Badge>;
  if (status === 'closed') return <Badge variant="default">Cerrado</Badge>;
  return <Badge variant="default">{status}</Badge>;
};

const PhysicalCountCapturePage: React.FC = () => {
  const { session } = usePosSession();
  const branchId = session?.active_branch?.id || '';
  const queryClient = useQueryClient();
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [online, setOnline] = useState(() => navigator.onLine);

  useEffect(() => {
    const connected = () => setOnline(true);
    const disconnected = () => setOnline(false);
    window.addEventListener('online', connected);
    window.addEventListener('offline', disconnected);
    return () => {
      window.removeEventListener('online', connected);
      window.removeEventListener('offline', disconnected);
    };
  }, []);

  const countsQuery = useQuery<CountSession[]>({
    queryKey: ['pos-physical-counts', branchId],
    queryFn: () => fetchApi(`/inventory/physical-counts?branch_id=${encodeURIComponent(branchId)}`),
    enabled: Boolean(branchId) && online,
  });
  const optionsQuery = useQuery<CountOptions>({
    queryKey: ['pos-physical-count-options', branchId],
    queryFn: () => fetchApi(`/inventory/physical-counts/options?branch_id=${encodeURIComponent(branchId)}`),
    enabled: Boolean(branchId) && online,
  });

  const counts = countsQuery.data || [];
  const active = counts.find((count) => ['counting', 'submitted', 'approved'].includes(count.status));
  const refresh = async () => queryClient.invalidateQueries({ queryKey: ['pos-physical-counts', branchId] });

  const createMutation = useMutation({
    mutationFn: () => {
      if (!online) throw new Error('Reconéctate para abrir un conteo.');
      return fetchApi<CountSession>('/inventory/physical-counts', {
        method: 'POST',
        body: JSON.stringify({ branch_id: branchId, category_names: selectedGroups }),
      });
    },
    onSuccess: async () => {
      setSelectedGroups([]);
      setError('');
      await refresh();
    },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible abrir el conteo.'),
  });

  const saveCapture = async (capture: PhysicalCountLineCapture): Promise<PhysicalCountCaptureSession> => {
    if (!active || !online) throw new Error('Reconéctate para confirmar esta captura.');
    setBusy(true);
    try {
      const updated = await fetchApi<CountSession>(
        `/inventory/physical-counts/${active.id}/lines/${capture.line_id}/entries`,
        {
          method: 'PUT',
          body: JSON.stringify({
            expected_version: capture.expected_version,
            entries: capture.entries,
          }),
        },
      );
      queryClient.setQueryData<CountSession[]>(['pos-physical-counts', branchId], (current = []) =>
        current.map((count) => count.id === updated.id ? updated : count),
      );
      setError('');
      return updated;
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'No fue posible guardar la captura.';
      setError(message);
      throw reason;
    } finally {
      setBusy(false);
    }
  };

  const submitCount = async () => {
    if (!active || !online) {
      setError('Reconéctate para enviar el conteo.');
      return;
    }
    setBusy(true);
    try {
      await fetchApi(`/inventory/physical-counts/${active.id}/submit`, { method: 'POST', body: '{}' });
      setError('');
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible enviar el conteo.');
      throw reason;
    } finally {
      setBusy(false);
    }
  };

  const toggleGroup = (group: string) => {
    setSelectedGroups((current) =>
      current.includes(group) ? current.filter((item) => item !== group) : [...current, group],
    );
  };

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '24px clamp(16px, 3vw, 36px)', background: '#f8fafc' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', marginBottom: 20, flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, color: '#16a34a', fontWeight: 800, fontSize: 13, textTransform: 'uppercase', letterSpacing: '.05em' }}>
            <ClipboardCheck size={18} /> Operación de almacén
          </div>
          <h1 style={{ margin: '6px 0', color: '#0f172a', fontSize: 28 }}>Conteo físico</h1>
          <p style={{ margin: 0, color: '#64748b' }}>
            Captura lo que encuentras físicamente. Las existencias y costos permanecen ocultos.
          </p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <strong style={{ color: '#0f172a' }}>{session?.active_branch?.name}</strong><br />
          <small style={{ color: '#64748b' }}>Almacén operativo de la sucursal</small>
        </div>
      </header>

      {!online && (
        <div role="alert" style={warningStyle}>
          <WifiOff size={19} /> Sin conexión. Puedes revisar la pantalla, pero necesitas reconectarte para abrir, guardar o enviar.
        </div>
      )}
      {(error || countsQuery.error) && (
        <div role="alert" style={errorStyle}>
          <AlertTriangle size={19} /> {error || 'No fue posible consultar los conteos.'}
        </div>
      )}

      {!active && (
        <section style={cardStyle}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16 }}>
            <PackageCheck size={22} color="#16a34a" />
            <div><strong style={{ color: '#0f172a' }}>Abrir un nuevo conteo</strong><br /><small style={{ color: '#64748b' }}>La hora del inventario será fijada por el servidor.</small></div>
          </div>
          <label style={groupStyle}>
            <input type="checkbox" checked={selectedGroups.length === 0} onChange={() => setSelectedGroups([])} />
            <span><strong>Todo el almacén</strong><br /><small>Incluye todos los insumos activos.</small></span>
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 9, marginTop: 9 }}>
            {optionsQuery.data?.groups.map((group) => (
              <label key={group.name} style={groupStyle}>
                <input type="checkbox" checked={selectedGroups.includes(group.name)} onChange={() => toggleGroup(group.name)} />
                <span><strong>{group.name}</strong><br /><small>{group.item_count} insumos</small></span>
              </label>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
            <Button variant="primary" disabled={!online || createMutation.isPending || !branchId} onClick={() => createMutation.mutate()}>
              {createMutation.isPending ? 'Preparando insumos…' : 'Comenzar conteo'}
            </Button>
          </div>
        </section>
      )}

      {active?.status === 'counting' && (
        <section style={cardStyle}>
          <PhysicalCountCapture session={active} busy={busy || !online} onSave={saveCapture} onSubmit={submitCount} />
        </section>
      )}

      {active && active.status !== 'counting' && (
        <section style={{ ...cardStyle, textAlign: 'center', padding: 36 }}>
          <LockKeyhole size={42} color="#16a34a" />
          <h2 style={{ color: '#0f172a' }}>Conteo {active.folio}</h2>
          <div>{statusLabel(active.status)}</div>
          <p style={{ color: '#64748b', maxWidth: 520, margin: '14px auto 0' }}>
            La captura terminó. Un responsable revisará las diferencias y autorizará cualquier ajuste.
          </p>
        </section>
      )}

      {counts.length > 0 && (
        <section style={{ ...cardStyle, marginTop: 16 }}>
          <h2 style={{ fontSize: 17, margin: '0 0 12px', color: '#0f172a' }}>Conteos recientes</h2>
          <div style={{ display: 'grid', gap: 8 }}>
            {counts.slice(0, 8).map((count) => (
              <div key={count.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: 11, border: '1px solid #e2e8f0', borderRadius: 9, flexWrap: 'wrap' }}>
                <span><strong>{count.folio}</strong><br /><small>{new Date(count.snapshot_at).toLocaleString('es-MX')}</small></span>
                <span>{count.lines.filter((line) => line.counted_quantity != null).length} / {count.lines.length} insumos</span>
                {statusLabel(count.status)}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: 20,
  boxShadow: '0 8px 24px rgba(15, 23, 42, .05)',
};
const groupStyle: React.CSSProperties = {
  display: 'flex', gap: 10, alignItems: 'flex-start', padding: 12, border: '1px solid #dbe3ec',
  borderRadius: 10, cursor: 'pointer', color: '#334155', minHeight: 58,
};
const warningStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, padding: 12, borderRadius: 10,
  background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a', marginBottom: 16,
};
const errorStyle: React.CSSProperties = {
  ...warningStyle, background: '#fef2f2', color: '#b91c1c', borderColor: '#fecaca',
};

export default PhysicalCountCapturePage;
