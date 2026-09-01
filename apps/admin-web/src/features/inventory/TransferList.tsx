import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Input, Modal, Select } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, Plus, Send, Trash2, Truck, AlertCircle, ArrowRight, Package } from 'lucide-react';
import '../../premium-catalogs.css';
import { resolveBranchId } from '../../lib/branchContext';

interface Branch { id: string; name: string; code: string; status: string; }
interface Item { id: string; name: string; sku: string; base_unit_id: string; unit_code: string; status: string; }
interface DraftLine { item_id: string; quantity: string; notes: string; }
interface TransferLine { id: string; item_name: string; item_sku: string; unit_code: string; requested_quantity: number; sent_quantity: number; received_quantity: number; difference_quantity: number; unit_cost: number; difference_cost: number; }
interface Transfer { id: string; folio: string; source_branch_id: string; source_branch_name: string; destination_branch_id: string; destination_branch_name: string; status: string; created_at: string; notes?: string; lines: TransferLine[]; }
interface ReceiptLine { line_id: string; received_quantity: string; condition: string; difference_reason: string; notes: string; }

const TransferList = () => {
  const branchId = resolveBranchId();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [receiveTransfer, setReceiveTransfer] = useState<Transfer | null>(null);
  const [error, setError] = useState('');
  const [destinationBranchId, setDestinationBranchId] = useState('');
  const [notes, setNotes] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([{ item_id: '', quantity: '', notes: '' }]);
  const [receiptLines, setReceiptLines] = useState<ReceiptLine[]>([]);
  const { data: branches = [] } = useQuery<Branch[]>({ queryKey: ['branches'], queryFn: () => fetchApi('/branches') });
  const { data: items = [] } = useQuery<Item[]>({ queryKey: ['inventory', 'items'], queryFn: () => fetchApi('/inventory/items') });
  const { data: transfers = [] } = useQuery<Transfer[]>({
    queryKey: ['inventory-transfers', branchId],
    queryFn: () => fetchApi(`/inventory/transfers?branch_id=${branchId}`),
    enabled: Boolean(branchId),
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['inventory-transfers'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory-costs'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'stock'] }),
    ]);
  };
  const createMutation = useMutation({
    mutationFn: () => fetchApi('/inventory/transfers', { method: 'POST', body: JSON.stringify({
      source_branch_id: branchId, destination_branch_id: destinationBranchId, notes,
      lines: lines.map((line) => ({ ...line, unit_id: items.find((item) => item.id === line.item_id)?.base_unit_id })),
    }) }),
    onSuccess: async () => { setCreateOpen(false); setDestinationBranchId(''); setNotes(''); setLines([{ item_id: '', quantity: '', notes: '' }]); setError(''); await refresh(); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible crear el traspaso.'),
  });
  const sendTransfer = async (transferId: string) => {
    const storageKey = `transfer_send_${transferId}`;
    const key = localStorage.getItem(storageKey) || `transfer-send:${transferId}:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, key);
    try { await fetchApi(`/inventory/transfers/${transferId}/send`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: '{}' }); localStorage.removeItem(storageKey); setError(''); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No fue posible enviar el traspaso.'); }
  };
  const openReceipt = (transfer: Transfer) => {
    setReceiveTransfer(transfer);
    setReceiptLines(transfer.lines.map((line) => ({ line_id: line.id, received_quantity: String(line.sent_quantity), condition: 'good', difference_reason: '', notes: '' })));
  };
  const confirmReceipt = async () => {
    if (!receiveTransfer) return;
    const storageKey = `transfer_receive_${receiveTransfer.id}`;
    const key = localStorage.getItem(storageKey) || `transfer-receive:${receiveTransfer.id}:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, key);
    try { await fetchApi(`/inventory/transfers/${receiveTransfer.id}/receive`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ lines: receiptLines }) }); localStorage.removeItem(storageKey); setReceiveTransfer(null); setError(''); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No fue posible recibir el traspaso.'); }
  };
  const cancelTransfer = async (transferId: string) => {
    const reason = window.prompt('Motivo obligatorio de cancelación');
    if (!reason) return;
    try { await fetchApi(`/inventory/transfers/${transferId}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) }); setError(''); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'No fue posible cancelar.'); }
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Traspasos entre sucursales</h1>
          <p className="premium-header-subtitle">Controla salida, tránsito, recepción y diferencias sin entradas automáticas.</p>
        </div>
        <button className="premium-add-btn" onClick={() => setCreateOpen(true)} disabled={!branchId}>
          <Plus size={18} />
          Nuevo traspaso
        </button>
      </div>

      {!branchId && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>Selecciona o asigna una sucursal para gestionar traspasos.</span>
        </div>
      )}

      {error && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      <div className="premium-card">
        {transfers.length === 0 ? (
          <div className="premium-empty-state">
            <Truck size={56} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay traspasos registrados</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Crea traspasos para mover insumos entre almacenes de diferentes sucursales.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Folio</th>
                  <th>Ruta</th>
                  <th>Artículos solicitados</th>
                  <th>Enviado</th>
                  <th>Diferencia</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {transfers.map((transfer) => (
                  <tr key={transfer.id}>
                    <td>
                      <strong style={{ color: '#1e293b' }}>{transfer.folio}</strong>
                      <br />
                      <small style={{ color: '#64748b' }}>{new Date(transfer.created_at).toLocaleString('es-MX')}</small>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.9rem', color: '#334155' }}>
                        <span>{transfer.source_branch_name}</span>
                        <ArrowRight size={14} color="#64748b" />
                        <strong style={{ color: '#0f172a' }}>{transfer.destination_branch_name}</strong>
                      </div>
                    </td>
                    <td>
                      {transfer.lines.map((line) => (
                        <div key={line.id} style={{ fontSize: '0.85rem', marginBottom: 2 }}>
                          {line.item_name} · <strong>{Number(line.requested_quantity)} {line.unit_code}</strong>
                        </div>
                      ))}
                    </td>
                    <td>
                      {transfer.lines.map((line) => (
                        <div key={line.id} style={{ fontSize: '0.85rem', color: '#047857', fontWeight: 600, marginBottom: 2 }}>
                          {Number(line.sent_quantity)} {line.unit_code}
                        </div>
                      ))}
                    </td>
                    <td>
                      {transfer.lines.map((line) => (
                        <div key={line.id} style={{ fontSize: '0.85rem', color: Number(line.difference_quantity) !== 0 ? '#b91c1c' : '#64748b', fontWeight: 600, marginBottom: 2 }}>
                          {Number(line.difference_quantity)} {line.unit_code}
                        </div>
                      ))}
                    </td>
                    <td>
                      <Badge variant={transfer.status === 'received' ? 'success' : transfer.status === 'sent' ? 'info' : 'default'}>
                        {transfer.status === 'received' ? 'Recibido' : transfer.status === 'sent' ? 'Enviado' : transfer.status === 'draft' ? 'Borrador' : transfer.status}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
                        {transfer.status === 'draft' && (
                          transfer.source_branch_id === branchId ? (
                            <>
                              <Button variant="primary" onClick={() => void sendTransfer(transfer.id)}>
                                <Send size={15} /> Enviar
                              </Button>
                              <button
                                className="premium-action-btn delete"
                                title="Cancelar traspaso"
                                onClick={() => void cancelTransfer(transfer.id)}
                              >
                                <Trash2 size={16} />
                              </button>
                            </>
                          ) : (
                            <span style={{ color: '#64748b', fontSize: '0.82rem', fontStyle: 'italic' }}>
                              Pendiente de envío en {transfer.source_branch_name}
                            </span>
                          )
                        )}
                        {transfer.status === 'sent' && (
                          transfer.destination_branch_id === branchId ? (
                            <Button variant="primary" onClick={() => openReceipt(transfer)}>
                              <CheckCircle2 size={15} /> Recibir
                            </Button>
                          ) : (
                            <span style={{ color: '#0284c7', fontSize: '0.82rem', fontWeight: 600 }}>
                              🚚 En tránsito a {transfer.destination_branch_name}
                            </span>
                          )
                        )}
                        {transfer.status === 'received' && (
                          <span style={{ color: '#047857', fontSize: '0.82rem', fontWeight: 700 }}>
                            ✓ Concluido
                          </span>
                        )}
                        {transfer.status === 'cancelled' && (
                          <span style={{ color: '#94a3b8', fontSize: '0.82rem', fontStyle: 'italic' }}>
                            Cancelado
                          </span>
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

      <Modal isOpen={createOpen} onClose={() => setCreateOpen(false)} title="Nuevo traspaso de inventario" maxWidth="680px">
        <div className="premium-form-layout">
          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Sucursal destino</label>
              <Select
                value={destinationBranchId}
                onChange={(event) => setDestinationBranchId(event.target.value)}
              >
                <option value="">Selecciona sucursal de destino</option>
                {branches.filter((branch) => branch.id !== branchId && branch.status === 'active').map((branch) => (
                  <option key={branch.id} value={branch.id}>{branch.name}</option>
                ))}
              </Select>
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Observaciones</label>
              <Input
                placeholder="Motivo del traslado o notas..."
                value={notes}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setNotes(event.target.value)}
              />
            </div>
          </div>

          <div className="premium-section-box">
            <div className="premium-section-title">
              <span>Artículos a transferir ({lines.length})</span>
              <Button
                variant="secondary"
                onClick={() => setLines([...lines, { item_id: '', quantity: '', notes: '' }])}
              >
                <Plus size={15} /> Agregar artículo
              </Button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {lines.map((line, index) => (
                <div key={index} className="premium-line-item">
                  <div style={{ flex: 1 }}>
                    <Select
                      value={line.item_id}
                      onChange={(event) => setLines(lines.map((row, rowIndex) => rowIndex === index ? { ...row, item_id: event.target.value } : row))}
                    >
                      <option value="">Selecciona insumo o artículo</option>
                      {items.filter((item) => item.status === 'active').map((item) => (
                        <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>
                      ))}
                    </Select>
                  </div>

                  <div style={{ width: '130px' }}>
                    <Input
                      type="number"
                      step="any"
                      placeholder="Cantidad"
                      value={line.quantity}
                      onChange={(event: React.ChangeEvent<HTMLInputElement>) => setLines(lines.map((row, rowIndex) => rowIndex === index ? { ...row, quantity: event.target.value } : row))}
                    />
                  </div>

                  {lines.length > 1 && (
                    <button
                      type="button"
                      className="premium-action-btn delete"
                      title="Eliminar artículo"
                      onClick={() => setLines(lines.filter((_, rowIndex) => rowIndex !== index))}
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="premium-footer-actions">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !destinationBranchId || lines.some((l) => !l.item_id || !l.quantity)}
            >
              {createMutation.isPending ? 'Guardando...' : 'Guardar borrador'}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={Boolean(receiveTransfer)} onClose={() => setReceiveTransfer(null)} title={`Recepción: ${receiveTransfer?.folio || ''}`} maxWidth="720px">
        <div className="premium-form-layout">
          <p style={{ color: '#64748b', fontSize: '0.9rem', margin: 0 }}>
            Verifica la mercancía recibida contra lo enviado desde <strong>{receiveTransfer?.source_branch_name}</strong>.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {receiveTransfer?.lines.map((line, index) => {
              const receipt = receiptLines[index];
              return (
                <div key={line.id} className="premium-section-box">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong style={{ color: '#0f172a', fontSize: '0.95rem' }}>{line.item_name}</strong>
                    <span style={{ fontSize: '0.84rem', background: '#dbeafe', color: '#1e40af', padding: '3px 8px', borderRadius: 6, fontWeight: 600 }}>
                      Enviados: {Number(line.sent_quantity)} {line.unit_code}
                    </span>
                  </div>

                  <div className="premium-form-grid">
                    <div className="premium-form-group">
                      <label className="premium-form-label">Cantidad recibida</label>
                      <Input
                        type="number"
                        step="any"
                        value={receipt?.received_quantity || ''}
                        onChange={(event: React.ChangeEvent<HTMLInputElement>) => setReceiptLines(receiptLines.map((row, rowIndex) => rowIndex === index ? { ...row, received_quantity: event.target.value } : row))}
                      />
                    </div>

                    <div className="premium-form-group">
                      <label className="premium-form-label">Condición</label>
                      <Select
                        value={receipt?.condition || 'good'}
                        onChange={(event) => setReceiptLines(receiptLines.map((row, rowIndex) => rowIndex === index ? { ...row, condition: event.target.value } : row))}
                      >
                        <option value="good">Buena (completo)</option>
                        <option value="damaged">Dañada / Merma</option>
                        <option value="missing">Faltante</option>
                      </Select>
                    </div>
                  </div>

                  <div className="premium-form-group">
                    <label className="premium-form-label">Motivo o detalle de diferencia</label>
                    <Input
                      placeholder="Ej. Paquete roto durante el transporte..."
                      value={receipt?.difference_reason || ''}
                      onChange={(event: React.ChangeEvent<HTMLInputElement>) => setReceiptLines(receiptLines.map((row, rowIndex) => rowIndex === index ? { ...row, difference_reason: event.target.value } : row))}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="premium-footer-actions">
            <Button variant="secondary" onClick={() => setReceiveTransfer(null)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={() => void confirmReceipt()}>
              <CheckCircle2 size={16} /> Confirmar recepción
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default TransferList;
