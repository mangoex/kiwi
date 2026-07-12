import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { CheckCircle2, Plus, Send, Trash2, Truck } from 'lucide-react';
import '../../premium-catalogs.css';

interface Branch { id: string; name: string; code: string; status: string; }
interface Item { id: string; name: string; sku: string; base_unit_id: string; unit_code: string; status: string; }
interface DraftLine { item_id: string; quantity: string; notes: string; }
interface TransferLine { id: string; item_name: string; item_sku: string; unit_code: string; requested_quantity: number; sent_quantity: number; received_quantity: number; difference_quantity: number; unit_cost: number; difference_cost: number; }
interface Transfer { id: string; folio: string; source_branch_id: string; source_branch_name: string; destination_branch_id: string; destination_branch_name: string; status: string; created_at: string; notes?: string; lines: TransferLine[]; }
interface ReceiptLine { line_id: string; received_quantity: string; condition: string; difference_reason: string; notes: string; }

const currentBranchId = () => {
  const user = JSON.parse(localStorage.getItem('user') || '{}') as { assigned_branch_id?: string };
  return localStorage.getItem('admin_branch_id') || localStorage.getItem('pos_branch_id') || user.assigned_branch_id || '';
};

const TransferList = () => {
  const branchId = currentBranchId();
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

  return <>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}><div><h1 className="premium-header-title">Traspasos entre sucursales</h1><p className="premium-header-subtitle">Controla salida, tránsito, recepción y diferencias sin entradas automáticas.</p></div><Button variant="primary" onClick={() => setCreateOpen(true)} disabled={!branchId}><Plus size={16} /> Nuevo traspaso</Button></div>
    {!branchId && <div role="alert" style={{ color: '#b91c1c', marginBottom: 16 }}>Selecciona o asigna una sucursal.</div>}
    {error && <div role="alert" style={{ color: '#b91c1c', marginBottom: 16 }}>{error}</div>}
    <div className="premium-card" style={{ overflowX: 'auto' }}><table className="premium-table"><thead><tr><th>Folio</th><th>Ruta</th><th>Artículos</th><th>Enviado</th><th>Diferencia</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{transfers.map((transfer) => <tr key={transfer.id}><td><strong>{transfer.folio}</strong><br /><small>{new Date(transfer.created_at).toLocaleString('es-MX')}</small></td><td>{transfer.source_branch_name}<br /><Truck size={14} /> {transfer.destination_branch_name}</td><td>{transfer.lines.map((line) => <div key={line.id}>{line.item_name} · {Number(line.requested_quantity)} {line.unit_code}</div>)}</td><td>{transfer.lines.reduce((sum, line) => sum + Number(line.sent_quantity), 0)}</td><td>{transfer.lines.reduce((sum, line) => sum + Number(line.difference_quantity), 0)}</td><td><Badge variant={transfer.status === 'received' ? 'success' : transfer.status === 'sent' ? 'info' : 'default'}>{transfer.status}</Badge></td><td><div style={{ display: 'flex', gap: 8 }}>{transfer.status === 'draft' && transfer.source_branch_id === branchId && <><Button variant="primary" onClick={() => void sendTransfer(transfer.id)}><Send size={15} /> Enviar</Button><Button variant="secondary" onClick={() => void cancelTransfer(transfer.id)}><Trash2 size={15} /></Button></>}{transfer.status === 'sent' && transfer.destination_branch_id === branchId && <Button variant="primary" onClick={() => openReceipt(transfer)}><CheckCircle2 size={15} /> Recibir</Button>}</div></td></tr>)}</tbody></table></div>

    <Modal isOpen={createOpen} onClose={() => setCreateOpen(false)} title="Nuevo traspaso"><div style={{ display: 'grid', gap: 12 }}><label>Destino<select value={destinationBranchId} onChange={(event) => setDestinationBranchId(event.target.value)} style={{ width: '100%', padding: 10 }}><option value="">Selecciona</option>{branches.filter((branch) => branch.id !== branchId && branch.status === 'active').map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label><Field label="Observaciones" value={notes} setValue={setNotes} /><strong>Artículos</strong>{lines.map((line, index) => <div key={index} style={{ display: 'grid', gridTemplateColumns: '1fr 110px 36px', gap: 8 }}><select value={line.item_id} onChange={(event) => setLines(lines.map((row, rowIndex) => rowIndex === index ? { ...row, item_id: event.target.value } : row))} style={{ padding: 9 }}><option value="">Selecciona</option>{items.filter((item) => item.status === 'active').map((item) => <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>)}</select><Input value={line.quantity} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setLines(lines.map((row, rowIndex) => rowIndex === index ? { ...row, quantity: event.target.value } : row))} placeholder="Cantidad" /><button type="button" onClick={() => setLines(lines.filter((_, rowIndex) => rowIndex !== index))} style={{ border: 0, background: 'none' }}><Trash2 size={16} /></button></div>)}<Button variant="secondary" onClick={() => setLines([...lines, { item_id: '', quantity: '', notes: '' }])}><Plus size={15} /> Agregar artículo</Button></div><div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}><Button variant="primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>Guardar borrador</Button></div></Modal>
    <Modal isOpen={Boolean(receiveTransfer)} onClose={() => setReceiveTransfer(null)} title={`Recibir ${receiveTransfer?.folio || ''}`}><div style={{ display: 'grid', gap: 14 }}>{receiveTransfer?.lines.map((line, index) => { const receipt = receiptLines[index]; return <div key={line.id} style={{ display: 'grid', gap: 6, padding: 10, border: '1px solid var(--color-border)', borderRadius: 8 }}><strong>{line.item_name} · enviados {Number(line.sent_quantity)} {line.unit_code}</strong><Field label="Cantidad recibida" value={receipt?.received_quantity || ''} setValue={(received_quantity) => setReceiptLines(receiptLines.map((row, rowIndex) => rowIndex === index ? { ...row, received_quantity } : row))} /><label>Condición<select value={receipt?.condition || 'good'} onChange={(event) => setReceiptLines(receiptLines.map((row, rowIndex) => rowIndex === index ? { ...row, condition: event.target.value } : row))} style={{ width: '100%', padding: 9 }}><option value="good">Buena</option><option value="damaged">Dañada</option><option value="missing">Faltante</option></select></label><Field label="Motivo de diferencia" value={receipt?.difference_reason || ''} setValue={(difference_reason) => setReceiptLines(receiptLines.map((row, rowIndex) => rowIndex === index ? { ...row, difference_reason } : row))} /></div>; })}</div><div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}><Button variant="primary" onClick={() => void confirmReceipt()}>Confirmar recepción</Button></div></Modal>
  </>;
};

const Field = ({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) => <label style={{ display: 'grid', gap: 4 }}><span>{label}</span><Input value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValue(event.target.value)} /></label>;

export default TransferList;
