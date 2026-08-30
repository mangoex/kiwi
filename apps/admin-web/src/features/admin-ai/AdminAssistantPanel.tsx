import React, { useMemo, useState } from 'react';
import {
  ArrowRight,
  Check,
  ChevronDown,
  Filter,
  ListChecks,
  MapPin,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';

import './AdminAssistantPanel.css';

export type ProposalChange = {
  kind: string;
  target_id: string | null;
  current: Record<string, unknown> | null;
  proposed: Record<string, unknown>;
  review_path: string;
  evidence_fields: string[];
};

export type AdminAiDiagnosticItem = {
  id: string;
  name: string | null;
  sku: string | null;
  base_unit_code: string | null;
  label: string;
};

export type AdminAiDiagnostic = {
  kind: 'missing_purchase_price' | 'missing_average_cost' | string;
  scope: Record<string, string | null>;
  total: number;
  items: AdminAiDiagnosticItem[];
  truncated: boolean;
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
    diagnostic?: AdminAiDiagnostic | null;
  };
  result?: Record<string, unknown> | null;
};

type AdminAssistantPanelProps = {
  open: boolean;
  onClose: () => void;
  branchId: string;
  branchName: string;
};

const reasonFor = (kind: string) => {
  if (kind === 'missing_purchase_price') return 'Sin precio de compra';
  if (kind === 'missing_average_cost') return 'Sin costo promedio';
  return 'Requiere revisión';
};

const titleFor = (diagnostic: AdminAiDiagnostic) => {
  const noun = diagnostic.kind === 'missing_average_cost'
    ? 'insumos sin costo promedio'
    : 'insumos sin precio de compra';
  return `${diagnostic.total} ${noun}`;
};

export default function AdminAssistantPanel({
  open,
  onClose,
  branchId,
  branchName,
}: AdminAssistantPanelProps) {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [proposal, setProposal] = useState<AdminAiProposal | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [reasonFilter, setReasonFilter] = useState('all');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const diagnostic = proposal?.payload.diagnostic || null;
  const filteredItems = useMemo(() => {
    if (!diagnostic) return [];
    const normalized = search.trim().toLocaleLowerCase('es-MX');
    return diagnostic.items.filter((item) => {
      const matchesText = !normalized || [item.name, item.sku, item.label]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase('es-MX').includes(normalized));
      const matchesReason = reasonFilter === 'all' || reasonFilter === diagnostic.kind;
      return matchesText && matchesReason;
    });
  }, [diagnostic, reasonFilter, search]);

  const reset = () => {
    setProposal(null);
    setPrompt('');
    setSearch('');
    setReasonFilter('all');
    setSelectedIds(new Set());
    setError('');
  };

  const ask = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError('');
    try {
      const response = await fetchApi<AdminAiProposal>('/admin-ai/proposals', {
        method: 'POST',
        body: JSON.stringify({ prompt, branch_id: branchId || null }),
      });
      setProposal(response);
      setSelectedIds(new Set(response.payload.diagnostic?.items.map((item) => item.id) || []));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No fue posible consultar el asistente.');
    } finally {
      setLoading(false);
    }
  };

  const reviewProposal = () => {
    if (!proposal?.payload.change_set[0]) return;
    const path = proposal.payload.change_set[0].review_path;
    const separator = path.includes('?') ? '&' : '?';
    navigate(`${path}${separator}admin_ai_proposal=${encodeURIComponent(proposal.id)}`);
    onClose();
  };

  const openDiagnosticConfiguration = (ids: string[]) => {
    if (!proposal || !diagnostic || ids.length === 0) return;
    const selectionKey = `admin-ai-selection:${proposal.id}`;
    sessionStorage.setItem(selectionKey, JSON.stringify({
      proposal_id: proposal.id,
      kind: diagnostic.kind,
      item_ids: ids,
    }));
    const path = diagnostic.kind === 'missing_purchase_price'
      ? '/purchase-presentations'
      : '/inventory/items';
    navigate(`${path}?admin_ai_selection=${encodeURIComponent(proposal.id)}`);
    onClose();
  };

  const toggleItem = (itemId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  };

  const toggleVisible = () => {
    const visibleIds = filteredItems.map((item) => item.id);
    const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));
    setSelectedIds((current) => {
      const next = new Set(current);
      visibleIds.forEach((id) => {
        if (allVisibleSelected) next.delete(id);
        else next.add(id);
      });
      return next;
    });
  };

  const modalTitle = (
    <span className="admin-ai-title">
      <span className="admin-ai-title-icon" aria-hidden="true"><UserRound size={24} /><Sparkles size={12} /></span>
      <span>Asistente de configuración</span>
      <span className="admin-ai-branch"><MapPin size={15} /> {branchName}</span>
    </span>
  );

  return (
    <Modal isOpen={open} onClose={onClose} title={modalTitle} maxWidth="1040px" contentClassName="admin-ai-modal">
      <div className="admin-ai-assistant">
        <ol className="admin-ai-steps" aria-label="Progreso de configuración">
          <li className={proposal ? 'is-complete' : 'is-active'}>
            <span className="admin-ai-step-marker">{proposal ? <Check size={17} /> : '1'}</span>
            <span><strong>Consultar</strong><small>{proposal ? 'Completado' : 'En progreso'}</small></span>
          </li>
          <li className={proposal ? 'is-active' : ''}>
            <span className="admin-ai-step-marker">2</span>
            <span><strong>Revisar resultados</strong><small>{proposal ? 'En progreso' : 'Pendiente'}</small></span>
          </li>
          <li className={proposal?.status === 'READY_FOR_REVIEW' ? 'is-active' : ''}>
            <span className="admin-ai-step-marker">3</span>
            <span><strong>Validar cambios</strong><small>{proposal?.status === 'READY_FOR_REVIEW' ? 'Disponible' : 'Pendiente'}</small></span>
          </li>
        </ol>

        {!proposal && (
          <section className="admin-ai-query" aria-label="Nueva consulta">
            <div className="admin-ai-query-copy">
              <Sparkles size={22} />
              <div>
                <h4>¿Qué necesitas configurar o entender?</h4>
                <p>Consulta reglas, detecta faltantes o prepara una propuesta que siempre revisarás antes de aplicar.</p>
              </div>
            </div>
            <label htmlFor="admin-ai-prompt" className="admin-ai-visually-hidden">Consulta para asistente de configuración</label>
            <textarea
              id="admin-ai-prompt"
              aria-label="Consulta para asistente de configuración"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              maxLength={1600}
              rows={4}
              placeholder="Ej. ¿Qué insumos no tienen precio de compra?"
            />
            <div className="admin-ai-query-actions">
              <span><ShieldCheck size={15} /> Revisión y permisos canónicos obligatorios.</span>
              <Button onClick={() => void ask()} disabled={loading || !prompt.trim()}>
                <Send size={16} /> {loading ? 'Consultando…' : 'Consultar'}
              </Button>
            </div>
          </section>
        )}

        {error && <div className="admin-ai-error" role="alert">{error}</div>}

        {proposal && diagnostic && (
          <section className="admin-ai-result" aria-label="Resultados del diagnóstico" aria-live="polite">
            <div className="admin-ai-result-main">
              <header className="admin-ai-result-heading">
                <h4>{titleFor(diagnostic)}</h4>
                <p>Diagnóstico listo <span aria-hidden="true">·</span> No se realizaron cambios</p>
              </header>

              <div className="admin-ai-toolbar">
                <label className="admin-ai-search">
                  <Search size={17} />
                  <span className="admin-ai-visually-hidden">Buscar insumo o SKU</span>
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Buscar insumo o SKU"
                  />
                </label>
                <label className="admin-ai-filter">
                  <Filter size={16} />
                  <span className="admin-ai-visually-hidden">Filtrar motivo</span>
                  <select value={reasonFilter} onChange={(event) => setReasonFilter(event.target.value)}>
                    <option value="all">Todos los motivos</option>
                    <option value={diagnostic.kind}>{reasonFor(diagnostic.kind)}</option>
                  </select>
                  <ChevronDown size={15} aria-hidden="true" />
                </label>
              </div>

              <div className="admin-ai-table-wrap">
                <table className="admin-ai-table">
                  <thead>
                    <tr>
                      <th className="admin-ai-check-cell">
                        <input
                          type="checkbox"
                          aria-label="Seleccionar resultados visibles"
                          checked={filteredItems.length > 0 && filteredItems.every((item) => selectedIds.has(item.id))}
                          onChange={toggleVisible}
                        />
                      </th>
                      <th>Insumo</th>
                      <th>SKU</th>
                      <th>Unidad</th>
                      <th>Motivo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item) => (
                      <tr key={item.id}>
                        <td className="admin-ai-check-cell">
                          <input
                            type="checkbox"
                            aria-label={`Seleccionar ${item.label}`}
                            checked={selectedIds.has(item.id)}
                            onChange={() => toggleItem(item.id)}
                          />
                        </td>
                        <td><strong>{item.name || item.label}</strong></td>
                        <td>{item.sku || '—'}</td>
                        <td>{item.base_unit_code || '—'}</td>
                        <td>{reasonFor(diagnostic.kind)}</td>
                      </tr>
                    ))}
                    {filteredItems.length === 0 && (
                      <tr><td colSpan={5} className="admin-ai-empty">No hay resultados para esta búsqueda.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              <p className="admin-ai-selection-count">
                {selectedIds.size} seleccionados de {diagnostic.total}
                {diagnostic.truncated && ' · El detalle está acotado a 100 registros'}
              </p>
            </div>

            <aside className="admin-ai-next-step" aria-label="Siguiente paso">
              <h4>Siguiente paso</h4>
              <div className="admin-ai-selected-summary">
                <span><ListChecks size={22} /></span>
                <p><strong>{selectedIds.size} seleccionados</strong><small>de {diagnostic.total} insumos</small></p>
              </div>
              <p>Puedes abrir estos registros para completar su configuración.</p>
              <p>El asistente sólo prepara la navegación.</p>
              <button
                type="button"
                className="admin-ai-primary-action"
                disabled={selectedIds.size === 0}
                onClick={() => openDiagnosticConfiguration([...selectedIds])}
              >
                Revisar {selectedIds.size} {selectedIds.size === 1 ? 'insumo' : 'insumos'} <ArrowRight size={17} />
              </button>
              <button
                type="button"
                className="admin-ai-secondary-action"
                onClick={() => openDiagnosticConfiguration(diagnostic.items.map((item) => item.id))}
              >
                Revisar todos
              </button>
              <button type="button" className="admin-ai-link-action" onClick={reset}>Volver a consultar</button>
            </aside>
          </section>
        )}

        {proposal && !diagnostic && (
          <section className="admin-ai-guidance" aria-label="Respuesta del asistente" aria-live="polite">
            <div className="admin-ai-guidance-icon"><Sparkles size={22} /></div>
            <div>
              <h4>{proposal.status === 'READY_FOR_REVIEW' ? 'Propuesta lista para revisión' : 'Respuesta del asistente'}</h4>
              <p>{proposal.payload.answer}</p>
              {proposal.payload.questions.length > 0 && (
                <div><strong>Información necesaria</strong><ul>{proposal.payload.questions.map((question) => <li key={question}>{question}</li>)}</ul></div>
              )}
              {proposal.payload.warnings.map((warning) => <p key={warning} className="admin-ai-warning">{warning}</p>)}
              <div className="admin-ai-guidance-actions">
                {proposal.status === 'READY_FOR_REVIEW' && proposal.payload.change_set[0] && (
                  <Button onClick={reviewProposal}>Revisar configuración <ArrowRight size={16} /></Button>
                )}
                <Button variant="secondary" onClick={reset}>Nueva consulta</Button>
              </div>
            </div>
          </section>
        )}

        {proposal && (
          <details className="admin-ai-rules">
            <summary><ShieldCheck size={19} /><span>Reglas y permisos utilizados ({proposal.payload.sources.length})</span><ChevronDown className="admin-ai-rules-chevron" size={16} /></summary>
            <ul>{proposal.payload.sources.map((source) => <li key={source}>{source}</li>)}</ul>
          </details>
        )}

        <footer className="admin-ai-safety"><ShieldCheck size={16} /> Siempre validarás antes de aceptar cualquier cambio.</footer>
      </div>
    </Modal>
  );
}
