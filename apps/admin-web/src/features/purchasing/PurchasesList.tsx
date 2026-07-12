import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Modal, Badge } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, CheckCircle2, XCircle, ReceiptText } from 'lucide-react';
import '../../premium-catalogs.css';

interface Supplier { id: string; commercial_name: string; }
interface Presentation { id: string; supplier_id: string; name: string; last_net_price: number; base_unit_yield: number; base_unit_code: string; }
interface PurchaseLine { id: string; presentation_snapshot: { name: string }; presentation_quantity: number; base_quantity: number; }
interface Purchase { id: string; folio: string; supplier_id: string; document_type: string; total: number; status: string; paid_from_cash: boolean; cash_movement_id?: string; lines: PurchaseLine[]; }
interface InventoryCost { item_id: string; item_name: string; item_sku: string; quantity_on_hand: number; average_unit_cost: number; unit_code: string; }

const PurchasesList = () => {
  const branchId = localStorage.getItem('admin_branch_id') || localStorage.getItem('pos_branch_id') || '';
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ supplier_id: '', folio: '', document_type: 'invoice', presentation_id: '', quantity: '1', unit_price: '', discount: '0', tax: '0', paid_from_cash: true });
  const query = branchId ? `?branch_id=${branchId}` : '';
  const { data: purchases = [] } = useQuery<Purchase[]>({ queryKey: ['purchases'], queryFn: () => fetchApi(`/purchases${query}`) });
  const { data: suppliers = [] } = useQuery<Supplier[]>({ queryKey: ['suppliers'], queryFn: () => fetchApi(`/suppliers${query}`) });
  const { data: presentations = [] } = useQuery<Presentation[]>({ queryKey: ['purchase-presentations'], queryFn: () => fetchApi(`/purchase-presentations${query}`) });
  const { data: costs = [] } = useQuery<InventoryCost[]>({ queryKey: ['inventory-costs'], queryFn: () => fetchApi(`/inventory/costs${query}`) });
  const availablePresentations = useMemo(() => presentations.filter((item) => !form.supplier_id || item.supplier_id === form.supplier_id), [presentations, form.supplier_id]);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['purchases'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory-costs'] }),
    ]);
  };
  const createMutation = useMutation({
    mutationFn: () => fetchApi('/purchases', { method: 'POST', body: JSON.stringify({
      branch_id: branchId, supplier_id: form.supplier_id, folio: form.folio,
      document_type: form.document_type, payment_method: form.paid_from_cash ? 'cash' : 'other',
      paid_from_cash: form.paid_from_cash,
      lines: [{ presentation_id: form.presentation_id, quantity: form.quantity, unit_price: form.unit_price, discount: form.discount, tax: form.tax }],
    }) }),
    onSuccess: async () => { setOpen(false); setError(''); await refresh(); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible crear la compra.'),
  });
  const confirmPurchase = async (purchaseId: string) => {
    const storageKey = `purchase_confirmation_${purchaseId}`;
    const idempotencyKey = localStorage.getItem(storageKey) || `purchase:${purchaseId}:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, idempotencyKey);
    try {
      await fetchApi(`/purchases/${purchaseId}/confirm`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: '{}' });
      localStorage.removeItem(storageKey);
      setError('');
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No fue posible confirmar.'); }
  };
  const cancelPurchase = async (purchaseId: string) => {
    const reason = window.prompt('Motivo obligatorio de cancelación');
    if (!reason) return;
    try {
      await fetchApi(`/purchases/${purchaseId}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) });
      setError(''); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No fue posible cancelar.'); }
  };

  return <>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
      <div><h1 className="premium-header-title">Compras directas</h1><p className="premium-header-subtitle">Recepciones, retiro de caja y costo promedio conciliados.</p></div>
      <Button variant="primary" onClick={() => setOpen(true)}><Plus size={17} /> Nueva compra</Button>
    </div>
    {error && <div role="alert" style={{ color: '#b91c1c', marginBottom: 16 }}>{error}</div>}
    <div className="premium-card" style={{ overflowX: 'auto', marginBottom: 24 }}>
      <table className="premium-table"><thead><tr><th>Folio</th><th>Proveedor</th><th>Total</th><th>Pago</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
        {purchases.map((purchase) => <tr key={purchase.id}>
          <td><span style={{ display: 'flex', gap: 8 }}><ReceiptText size={17} />{purchase.folio}</span></td>
          <td>{suppliers.find((supplier) => supplier.id === purchase.supplier_id)?.commercial_name || purchase.supplier_id}</td>
          <td>${Number(purchase.total).toFixed(2)}</td><td>{purchase.paid_from_cash ? 'Caja' : 'Otro medio'}</td>
          <td><Badge variant={purchase.status === 'confirmed' ? 'success' : purchase.status === 'cancelled' ? 'default' : 'info'}>{purchase.status}</Badge></td>
          <td><div style={{ display: 'flex', gap: 8 }}>
            {purchase.status === 'draft' && <Button variant="primary" onClick={() => void confirmPurchase(purchase.id)}><CheckCircle2 size={15} /> Confirmar</Button>}
            {purchase.status !== 'cancelled' && <Button variant="secondary" onClick={() => void cancelPurchase(purchase.id)}><XCircle size={15} /> Cancelar</Button>}
          </div></td>
        </tr>)}
      </tbody></table>
    </div>
    <div className="premium-card" style={{ overflowX: 'auto' }}>
      <h2 style={{ padding: '16px 20px 0' }}>Costo promedio por sucursal</h2>
      <table className="premium-table"><thead><tr><th>SKU</th><th>Insumo</th><th>Existencia</th><th>Costo promedio</th><th>Último costo</th></tr></thead><tbody>
        {costs.map((cost) => <tr key={cost.item_id}><td>{cost.item_sku}</td><td>{cost.item_name}</td><td>{Number(cost.quantity_on_hand)} {cost.unit_code}</td><td>${Number(cost.average_unit_cost).toFixed(4)}</td><td>${Number((cost as InventoryCost & { last_unit_cost?: number }).last_unit_cost || 0).toFixed(4)}</td></tr>)}
      </tbody></table>
    </div>

    <Modal isOpen={open} onClose={() => setOpen(false)} title="Registrar compra directa">
      <div style={{ display: 'grid', gap: 12 }}>
        <label>Proveedor<select value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: event.target.value, presentation_id: '' })} style={{ width: '100%', padding: 10 }}><option value="">Selecciona</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.commercial_name}</option>)}</select></label>
        <label>Tipo de documento<select value={form.document_type} onChange={(event) => setForm({ ...form, document_type: event.target.value })} style={{ width: '100%', padding: 10 }}><option value="invoice">Factura</option><option value="ticket">Ticket</option><option value="note">Nota</option><option value="receipt">Recibo</option></select></label>
        <Field label="Folio" value={form.folio} setValue={(folio) => setForm({ ...form, folio })} />
        <label>Presentación<select value={form.presentation_id} onChange={(event) => { const selected = presentations.find((item) => item.id === event.target.value); setForm({ ...form, presentation_id: event.target.value, unit_price: String(selected?.last_net_price || '') }); }} style={{ width: '100%', padding: 10 }}><option value="">Selecciona</option>{availablePresentations.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.base_unit_yield} {item.base_unit_code}</option>)}</select></label>
        <Field label="Cantidad de presentaciones" value={form.quantity} setValue={(quantity) => setForm({ ...form, quantity })} />
        <Field label="Precio unitario neto" value={form.unit_price} setValue={(unit_price) => setForm({ ...form, unit_price })} />
        <Field label="Descuento" value={form.discount} setValue={(discount) => setForm({ ...form, discount })} />
        <Field label="Impuestos" value={form.tax} setValue={(tax) => setForm({ ...form, tax })} />
        <label style={{ display: 'flex', gap: 8 }}><input type="checkbox" checked={form.paid_from_cash} onChange={(event) => setForm({ ...form, paid_from_cash: event.target.checked })} /> Pagada desde caja</label>
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}><Button variant="secondary" onClick={() => setOpen(false)}>Cancelar</Button><Button variant="primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>Guardar borrador</Button></div>
    </Modal>
  </>;
};

const Field = ({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) => <label style={{ display: 'grid', gap: 4 }}><span>{label}</span><Input value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValue(event.target.value)} /></label>;
export default PurchasesList;
