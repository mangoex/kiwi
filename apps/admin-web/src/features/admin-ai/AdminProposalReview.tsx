import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ShieldCheck, XCircle } from 'lucide-react';
import { Button, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import type { AdminAiProposal } from './AdminAssistantPanel';

const displayValue = (value: unknown) => {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
};

function ValueTable({ title, value }: { title: string; value: Record<string, unknown> | null }) {
  return (
    <section style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden' }}>
      <h3 style={{ margin: 0, padding: '10px 12px', fontSize: 14, background: '#f8fafc' }}>{title}</h3>
      {value ? Object.entries(value).map(([key, fieldValue]) => (
        <div key={key} style={{ display: 'grid', gridTemplateColumns: 'minmax(130px, 0.4fr) 1fr', gap: 10, padding: '9px 12px', borderTop: '1px solid #f1f5f9', fontSize: 13 }}>
          <strong>{key}</strong><pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{displayValue(fieldValue)}</pre>
        </div>
      )) : <p style={{ padding: 12, margin: 0, color: '#64748b' }}>Registro nuevo; no existe configuración actual.</p>}
    </section>
  );
}

export default function AdminProposalReview({ proposalId, onClose }: { proposalId: string; onClose: () => void }) {
  const [proposal, setProposal] = useState<AdminAiProposal | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const idempotencyKey = useMemo(() => `admin-ai-review-${proposalId}-${crypto.randomUUID()}`, [proposalId]);
  const change = proposal?.payload.change_set[0];

  useEffect(() => {
    setError('');
    fetchApi<AdminAiProposal>(`/admin-ai/proposals/${encodeURIComponent(proposalId)}`)
      .then(setProposal)
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'No fue posible cargar la propuesta.'));
  }, [proposalId]);

  const decide = async (accept: boolean) => {
    setBusy(true);
    setError('');
    try {
      const updated = await fetchApi<AdminAiProposal>(`/admin-ai/proposals/${encodeURIComponent(proposalId)}/review`, {
        method: 'POST',
        headers: accept ? { 'Idempotency-Key': idempotencyKey } : undefined,
        body: JSON.stringify({ accept }),
      });
      setProposal(updated);
      if (updated.status === 'APPLIED' || updated.status === 'REJECTED') window.setTimeout(() => window.location.reload(), 500);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No fue posible registrar la decisión.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal isOpen onClose={onClose} title="Revisar configuración propuesta" maxWidth="860px">
      <div style={{ display: 'grid', gap: 14, maxHeight: '75vh', overflowY: 'auto' }}>
        {error && <div role="alert" style={{ color: '#b91c1c' }}>{error}</div>}
        {!proposal && !error && <p>Cargando propuesta…</p>}
        {proposal && <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#475569' }}><ShieldCheck size={18} /> Estado: <strong>{proposal.status}</strong></div>
          <p style={{ margin: 0 }}>{proposal.payload.answer}</p>
          {proposal.payload.warnings.map((warning) => <p key={warning} style={{ margin: 0, color: '#92400e' }}>{warning}</p>)}
          {change && <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
              <ValueTable title="Configuración actual" value={change.current} />
              <ValueTable title="Configuración propuesta" value={change.proposed} />
            </div>
            <div><strong>Fuentes</strong><ul>{proposal.payload.sources.map((source) => <li key={source}>{source}</li>)}</ul></div>
          </>}
          {proposal.status === 'READY_FOR_REVIEW' && change && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, borderTop: '1px solid #e2e8f0', paddingTop: 12 }}>
              <Button variant="secondary" disabled={busy} onClick={() => void decide(false)}><XCircle size={16} /> Rechazar</Button>
              <Button disabled={busy} onClick={() => void decide(true)}><CheckCircle2 size={16} /> {busy ? 'Validando…' : 'Aceptar configuración'}</Button>
            </div>
          )}
        </>}
      </div>
    </Modal>
  );
}
