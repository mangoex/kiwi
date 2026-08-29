import React, { useState } from 'react';
import { Bot, Send, ShieldCheck, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';

export type ProposalChange = {
  kind: string;
  target_id: string | null;
  current: Record<string, unknown> | null;
  proposed: Record<string, unknown>;
  review_path: string;
  evidence_fields: string[];
};

export type AdminAiProposal = {
  id: string;
  status: 'DRAFT' | 'READY_FOR_REVIEW' | 'APPLIED' | 'REJECTED' | 'EXPIRED';
  payload: {
    answer: string;
    sources: string[];
    questions: string[];
    warnings: string[];
    change_set: ProposalChange[];
  };
  result?: Record<string, unknown> | null;
};

export default function AdminAssistantPanel({ open, onClose, branchId }: { open: boolean; onClose: () => void; branchId: string }) {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [proposal, setProposal] = useState<AdminAiProposal | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const ask = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError('');
    try {
      setProposal(await fetchApi<AdminAiProposal>('/admin-ai/proposals', {
        method: 'POST',
        body: JSON.stringify({ prompt, branch_id: branchId || null }),
      }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No fue posible consultar el asistente.');
    } finally {
      setLoading(false);
    }
  };

  const review = () => {
    if (!proposal?.payload.change_set[0]) return;
    const path = proposal.payload.change_set[0].review_path;
    const separator = path.includes('?') ? '&' : '?';
    navigate(`${path}${separator}admin_ai_proposal=${encodeURIComponent(proposal.id)}`);
    onClose();
  };

  return (
    <Modal isOpen={open} onClose={onClose} title="Asistente de configuración" maxWidth="680px">
      <div style={{ display: 'grid', gap: 14 }}>
        <p style={{ margin: 0, color: '#64748b' }}>
          Consulta flujos y reglas o prepara una propuesta para productos, modificadores, recetas e insumos. El asistente nunca aplica cambios por sí solo.
        </p>
        <label htmlFor="admin-ai-prompt" style={{ fontWeight: 600 }}>¿Qué necesitas configurar o entender?</label>
        <textarea
          id="admin-ai-prompt"
          aria-label="Consulta para asistente de configuración"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          maxLength={1600}
          rows={5}
          placeholder="Ej. Para el producto 1001 crea un grupo TAMAÑO opcional, mínimo 0 y máximo 1."
          style={{ resize: 'vertical', width: '100%', boxSizing: 'border-box', padding: 12, borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 12, color: '#64748b' }}><ShieldCheck size={14} style={{ verticalAlign: 'middle' }} /> Revisión y permisos canónicos obligatorios.</span>
          <Button onClick={ask} disabled={loading || !prompt.trim()}><Send size={16} /> {loading ? 'Consultando...' : 'Consultar'}</Button>
        </div>
        {error && <div role="alert" style={{ color: '#b91c1c' }}>{error}</div>}
        {proposal && (
          <section aria-label="Respuesta del asistente" aria-live="polite" style={{ borderTop: '1px solid #e2e8f0', paddingTop: 14 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 700 }}><Bot size={18} /> Respuesta</div>
            <p>{proposal.payload.answer}</p>
            {proposal.payload.questions.length > 0 && <><strong>Faltantes</strong><ul>{proposal.payload.questions.map((question) => <li key={question}>{question}</li>)}</ul></>}
            {proposal.payload.sources.length > 0 && <><strong>Fuentes y reglas usadas</strong><ul>{proposal.payload.sources.map((source) => <li key={source}>{source}</li>)}</ul></>}
            {proposal.payload.warnings.map((warning) => <p key={warning} style={{ color: '#92400e', fontSize: 13 }}>{warning}</p>)}
            {proposal.status === 'READY_FOR_REVIEW' && proposal.payload.change_set[0] && (
              <div style={{ padding: 12, borderRadius: 10, background: '#ecfdf5', border: '1px solid #a7f3d0', marginBottom: 12 }}>
                <strong>Propuesta lista para revisión</strong>
                <p style={{ margin: '5px 0 10px', fontSize: 13 }}>Acción: {proposal.payload.change_set[0].kind}. Aún no se modificó la configuración.</p>
                <Button onClick={review}><ExternalLink size={16} /> Revisar configuración</Button>
              </div>
            )}
            <Button variant="secondary" onClick={() => { setProposal(null); setPrompt(''); }}>Nueva consulta</Button>
          </section>
        )}
      </div>
    </Modal>
  );
}
