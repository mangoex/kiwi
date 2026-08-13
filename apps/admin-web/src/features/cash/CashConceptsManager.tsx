import React, { useEffect, useRef, useState } from 'react';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Button, Input } from '@restaurantos/ui';
import {
  commandKeyStore,
  createCashConceptPayload,
  formatLocalDateTime,
  versionCashConceptPayload,
} from './cashConceptState';

type MovementType = 'deposit' | 'withdrawal' | 'both';
type CashConceptVersion = {
  id: string;
  version: number;
  name: string;
  allowed_movement_type: MovementType;
  requires_reference: boolean;
  requires_evidence: boolean;
  valid_from: string;
};
type CashConcept = {
  id: string;
  code: string;
  status: 'active' | 'archived';
  archived_at: string | null;
  versions: CashConceptVersion[];
};

const emptyForm = () => ({
  code: '',
  name: '',
  allowed_movement_type: 'withdrawal' as MovementType,
  valid_from: formatLocalDateTime(new Date()),
});

const messageFor = (reason: unknown) => {
  if (!(reason instanceof ApiError)) return 'No se pudo completar la operación.';
  const messages: Record<string, string> = {
    cash_concept_code_conflict: 'Ya existe un concepto con ese código.',
    cash_concept_code_immutable: 'El código del concepto no puede cambiar.',
    cash_concept_invalid: 'Revisa nombre, tipo y vigencia del concepto.',
    idempotency_conflict: 'La operación ya fue usada con datos distintos. Recarga e intenta de nuevo.',
    idempotency_key_required: 'No se generó una clave de reintento. Intenta nuevamente.',
    cash_concept_not_found: 'El concepto ya no está disponible. Recarga e intenta nuevamente.',
    permission_denied: 'Tu cuenta no tiene permiso para administrar conceptos.',
  };
  return messages[reason.code] || reason.message;
};

export default function CashConceptsManager() {
  const [concepts, setConcepts] = useState<CashConcept[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const commandKeys = useRef(commandKeyStore());

  const load = async () => {
    setLoading(true);
    try {
      setConcepts(await fetchApi<CashConcept[]>('/cash/concepts'));
    } catch (reason) {
      setMessage(messageFor(reason));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const save = async () => {
    if (!form.code.trim() || !form.name.trim() || !form.valid_from) return;
    const operation = editingId ? `version:${editingId}` : 'create';
    setSaving(true);
    setMessage('');
    try {
      await fetchApi(
        editingId ? `/cash/concepts/${editingId}/versions` : '/cash/concepts',
        {
          method: editingId ? 'PUT' : 'POST',
          headers: { 'Idempotency-Key': commandKeys.current.get(operation, () => crypto.randomUUID()) },
          body: JSON.stringify(editingId ? versionCashConceptPayload(form) : createCashConceptPayload(form)),
        },
      );
      commandKeys.current.clear(operation);
      setForm(emptyForm());
      setEditingId(null);
      setMessage(editingId ? 'Nueva versión publicada.' : 'Concepto publicado.');
      await load();
    } catch (reason) {
      setMessage(messageFor(reason));
    } finally {
      setSaving(false);
    }
  };

  const startVersion = (concept: CashConcept) => {
    const current = concept.versions[concept.versions.length - 1];
    setEditingId(concept.id);
    setForm({
      code: concept.code,
      name: current.name,
      allowed_movement_type: current.allowed_movement_type,
      valid_from: formatLocalDateTime(new Date()),
    });
    setMessage('');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const archive = async (concept: CashConcept) => {
    if (!window.confirm(`¿Archivar ${concept.code}? Dejará de aparecer en operaciones nuevas.`)) return;
    const operation = `archive:${concept.id}`;
    setSaving(true);
    setMessage('');
    try {
      await fetchApi(`/cash/concepts/${concept.id}/archive`, {
        method: 'POST',
        headers: { 'Idempotency-Key': commandKeys.current.get(operation, () => crypto.randomUUID()) },
      });
      commandKeys.current.clear(operation);
      setMessage('Concepto archivado; su historial permanece disponible.');
      await load();
    } catch (reason) {
      setMessage(messageFor(reason));
    } finally {
      setSaving(false);
    }
  };

  return (
    <main style={{ maxWidth: 1120, padding: 24 }}>
      <div className="admin-title-row">
        <div>
          <h1 className="admin-title">Conceptos de caja</h1>
          <p style={{ color: 'var(--admin-text-muted)' }}>
            Catálogo corporativo versionado. Referencia y evidencia son obligatorias en todo movimiento manual.
          </p>
        </div>
      </div>

      <section style={{ background: '#fff', padding: 20, borderRadius: 14, boxShadow: 'var(--admin-card-shadow)', marginBottom: 24 }}>
        <h2 style={{ marginTop: 0 }}>{editingId ? 'Publicar nueva versión' : 'Publicar concepto'}</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 16 }}>
          <label>
            Código estable
            <Input
              value={form.code}
              disabled={Boolean(editingId)}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, code: event.target.value.toUpperCase() })}
              placeholder="RETIRO_OPERATIVO"
            />
          </label>
          <label>
            Nombre visible
            <Input
              value={form.name}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, name: event.target.value })}
            />
          </label>
          <label>
            Tipo permitido
            <select
              value={form.allowed_movement_type}
              onChange={(event) => setForm({ ...form, allowed_movement_type: event.target.value as MovementType })}
              style={{ width: '100%', minHeight: 42, border: '1px solid #cbd5e1', borderRadius: 8, padding: '0 10px' }}
            >
              <option value="withdrawal">Retiro</option>
              <option value="deposit">Depósito</option>
              <option value="both">Depósito y retiro</option>
            </select>
          </label>
          <label>
            Vigente desde
            <Input
              type="datetime-local"
              value={form.valid_from}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, valid_from: event.target.value })}
            />
          </label>
        </div>
        <p style={{ color: 'var(--admin-text-muted)', fontSize: 14 }}>
          El backend determina la versión efectiva. El código no se puede cambiar y archivar nunca elimina historia.
        </p>
        <div style={{ display: 'flex', gap: 10 }}>
          <Button onClick={() => void save()} disabled={saving || !form.code.trim() || !form.name.trim() || !form.valid_from}>
            {saving ? 'Guardando…' : editingId ? 'Publicar versión' : 'Publicar concepto'}
          </Button>
          {editingId && (
            <Button onClick={() => { setEditingId(null); setForm(emptyForm()); setMessage(''); }} disabled={saving}>
              Cancelar
            </Button>
          )}
        </div>
      </section>

      {message && <p role="status" style={{ padding: 12, background: '#f1f5f9', borderRadius: 8 }}>{message}</p>}
      {loading ? <p>Cargando conceptos…</p> : concepts.length === 0 ? (
        <p>No hay conceptos publicados.</p>
      ) : (
        <div style={{ display: 'grid', gap: 16 }}>
          {concepts.map((concept) => {
            const current = concept.versions[concept.versions.length - 1];
            return (
              <article key={concept.id} style={{ background: '#fff', padding: 20, borderRadius: 14, boxShadow: 'var(--admin-card-shadow)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                  <div>
                    <h2 style={{ margin: 0 }}>{current.name}</h2>
                    <p style={{ margin: '6px 0' }}><code>{concept.code}</code> · versión {current.version} · {concept.status === 'active' ? 'Activo' : 'Archivado'}</p>
                    <p style={{ color: 'var(--admin-text-muted)', margin: 0 }}>
                      {current.allowed_movement_type === 'withdrawal' ? 'Retiro' : current.allowed_movement_type === 'deposit' ? 'Depósito' : 'Depósito y retiro'} · vigente desde {new Date(current.valid_from).toLocaleString('es-MX')}
                    </p>
                  </div>
                  {concept.status === 'active' && (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <Button onClick={() => startVersion(concept)} disabled={saving}>Nueva versión</Button>
                      <Button onClick={() => void archive(concept)} disabled={saving}>Archivar</Button>
                    </div>
                  )}
                </div>
                <details style={{ marginTop: 14 }}>
                  <summary>Historial ({concept.versions.length})</summary>
                  <ol>
                    {concept.versions.map((version) => (
                      <li key={version.id}>
                        v{version.version} · {version.name} · {new Date(version.valid_from).toLocaleString('es-MX')}
                      </li>
                    ))}
                  </ol>
                </details>
              </article>
            );
          })}
        </div>
      )}
    </main>
  );
}
