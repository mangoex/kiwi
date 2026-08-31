import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Input, Modal, Select } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, Plus, RotateCcw, Trash2, AlertCircle, FileText, Tag } from 'lucide-react';
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
  const { data: reasons = [] } = useQuery<Reason[]>({ queryKey: ['waste-reasons', branchId], queryFn: () => fetchApi(`/inventory/waste-reasons?branch_id=${encodeURIComponent(branchId)}`), enabled: Boolean(branchId) });
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

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Mermas reales</h1>
          <p className="premium-header-subtitle">Captura, autoriza y corrige pérdidas mediante movimientos auditables.</p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <Button variant="secondary" onClick={() => setReasonOpen(true)}>
            <Plus size={16} /> Motivo
          </Button>
          <button className="premium-add-btn" onClick={() => setWasteOpen(true)} disabled={!branchId}>
            <Trash2 size={18} />
            Registrar merma
          </button>
        </div>
      </div>

      {!branchId && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>Selecciona o asigna una sucursal para registrar mermas.</span>
        </div>
      )}

      {error && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      <div className="premium-card">
        {wastes.length === 0 ? (
          <div className="premium-empty-state">
            <Trash2 size={56} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay mermas registradas</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Registra pérdidas de inventario para mantener el costo y existencias al día.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Artículo</th>
                  <th>Motivo / etapa</th>
                  <th>Cantidad</th>
                  <th>Costo</th>
                  <th>Evidencia</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {wastes.map((waste) => (
                  <tr key={waste.id}>
                    <td style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
                      {new Date(waste.effective_at).toLocaleString('es-MX')}
                    </td>
                    <td>
                      <strong style={{ color: '#1e293b' }}>{waste.item_name}</strong>
                      <br />
                      <small style={{ color: '#64748b' }}>{waste.item_sku}</small>
                    </td>
                    <td>
                      <span style={{ fontWeight: 600 }}>{waste.reason_name}</span>
                      <br />
                      <small style={{ color: '#64748b', textTransform: 'capitalize' }}>{waste.stage}</small>
                    </td>
                    <td style={{ fontWeight: 600 }}>
                      {Number(waste.quantity)} {waste.unit_code}
                    </td>
                    <td>
                      <span style={{ fontWeight: 700, color: '#b91c1c' }}>${Number(waste.total_cost).toFixed(2)}</span>
                      <br />
                      <small style={{ color: '#64748b' }}>${Number(waste.unit_cost).toFixed(4)} / {waste.unit_code}</small>
                    </td>
                    <td>
                      {waste.evidence.length ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.82rem', color: '#475467' }}>
                          <FileText size={14} /> {waste.evidence.length} ref.
                        </span>
                      ) : (
                        <span style={{ color: '#94a3b8', fontSize: '0.82rem' }}>Sin evidencia</span>
                      )}
                    </td>
                    <td>
                      <Badge variant={waste.status === 'confirmed' ? 'success' : waste.status === 'draft' ? 'info' : 'default'}>
                        {waste.status === 'confirmed' ? 'Confirmado' : waste.status === 'draft' ? 'Borrador' : waste.status}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        {waste.status === 'draft' && (
                          <Button variant="primary" onClick={() => void confirmWaste(waste.id)}>
                            <CheckCircle2 size={15} /> Confirmar
                          </Button>
                        )}
                        {waste.status === 'confirmed' && (
                          <Button variant="secondary" onClick={() => void reverseWaste(waste.id)}>
                            <RotateCcw size={15} /> Revertir
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={wasteOpen} onClose={() => setWasteOpen(false)} title="Registrar merma real" maxWidth="620px">
        <div className="premium-form-layout">
          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Artículo</label>
              <Select
                value={form.item_id}
                onChange={(event) => setForm({ ...form, item_id: event.target.value })}
              >
                <option value="">Selecciona un artículo</option>
                {items.filter((item) => item.status === 'active').map((item) => (
                  <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>
                ))}
              </Select>
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Motivo de merma</label>
              <Select
                value={form.reason_id}
                onChange={(event) => setForm({ ...form, reason_id: event.target.value })}
              >
                <option value="">Selecciona un motivo</option>
                {reasons.map((reason) => (
                  <option key={reason.id} value={reason.id}>{reason.name}</option>
                ))}
              </Select>
            </div>
          </div>

          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">
                Cantidad {selectedItem?.unit_code ? `(${selectedItem.unit_code})` : ''}
              </label>
              <Input
                type="number"
                step="any"
                placeholder="0.00"
                value={form.quantity}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, quantity: event.target.value })}
              />
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Etapa operativa</label>
              <Select
                value={form.stage}
                onChange={(event) => setForm({ ...form, stage: event.target.value })}
              >
                <option value="storage">Almacenamiento</option>
                <option value="preparation">Preparación</option>
                <option value="service">Servicio</option>
                <option value="receiving">Recepción</option>
              </Select>
            </div>
          </div>

          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Fecha efectiva (opcional)</label>
              <Input
                type="datetime-local"
                value={form.effective_at}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, effective_at: event.target.value })}
              />
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Evidencia</label>
              <Input
                placeholder="Fotos, folios o ticket (separados por coma)"
                value={form.evidence}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, evidence: event.target.value })}
              />
            </div>
          </div>

          <div className="premium-form-group">
            <label className="premium-form-label">Observaciones y notas</label>
            <Input
              placeholder="Detalle o causa de la pérdida..."
              value={form.notes}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, notes: event.target.value })}
            />
          </div>

          <div className="premium-footer-actions">
            <Button variant="secondary" onClick={() => setWasteOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !form.item_id || !form.reason_id || !form.quantity}
            >
              {createMutation.isPending ? 'Guardando...' : 'Guardar borrador'}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={reasonOpen} onClose={() => setReasonOpen(false)} title="Nuevo motivo de merma" maxWidth="500px">
        <div className="premium-form-layout">
          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Código</label>
              <Input
                placeholder="Ej. EXP-01"
                value={reasonForm.code}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setReasonForm({ ...reasonForm, code: event.target.value })}
              />
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Clasificación</label>
              <Select
                value={reasonForm.classification}
                onChange={(event) => setReasonForm({ ...reasonForm, classification: event.target.value })}
              >
                <option value="operation">Operación</option>
                <option value="quality">Calidad</option>
                <option value="production">Producción</option>
                <option value="security">Seguridad</option>
                <option value="other">Otro</option>
              </Select>
            </div>
          </div>

          <div className="premium-form-group">
            <label className="premium-form-label">Nombre del motivo</label>
            <Input
              placeholder="Ej. Caducidad en almacén"
              value={reasonForm.name}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => setReasonForm({ ...reasonForm, name: event.target.value })}
            />
          </div>

          <div className="premium-footer-actions">
            <Button variant="secondary" onClick={() => setReasonOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => reasonMutation.mutate()}
              disabled={reasonMutation.isPending || !reasonForm.code || !reasonForm.name}
            >
              {reasonMutation.isPending ? 'Creando...' : 'Crear motivo'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default WasteList;
