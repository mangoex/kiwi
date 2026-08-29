import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Modal, Badge, Select } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, CheckCircle2, XCircle, ReceiptText, AlertCircle, DollarSign, Building2, ShoppingCart } from 'lucide-react';
import '../../premium-catalogs.css';
import { resolveBranchId } from '../../lib/branchContext';

interface Supplier { id: string; commercial_name: string; }
interface Presentation { id: string; supplier_id: string; name: string; last_net_price: number; base_unit_yield: number; base_unit_code: string; }
interface PurchaseLine { id: string; presentation_snapshot: { name: string }; presentation_quantity: number; base_quantity: number; }
interface Purchase { id: string; folio: string; supplier_id: string; document_type: string; total: number; status: string; paid_from_cash: boolean; cash_movement_id?: string; lines: PurchaseLine[]; }
interface InventoryCost { item_id: string; item_name: string; item_sku: string; quantity_on_hand: number; average_unit_cost: number; unit_code: string; }

const PurchasesList = () => {
  const branchId = resolveBranchId();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ supplier_id: '', folio: '', document_type: 'invoice', presentation_id: '', quantity: '1', unit_price: '', discount: '0', tax: '0', paid_from_cash: true });
  const query = branchId ? `?branch_id=${branchId}` : '';
  const { data: purchases = [] } = useQuery<Purchase[]>({ queryKey: ['purchases'], queryFn: () => fetchApi(`/purchases${query}`) });
  const { data: suppliers = [] } = useQuery<Supplier[]>({ queryKey: ['suppliers'], queryFn: () => fetchApi(`/suppliers${query}`) });
  const { data: presentations = [] } = useQuery<Presentation[]>({ queryKey: ['purchase-presentations'], queryFn: () => fetchApi(`/purchase-presentations${query}`) });
  const { data: costs = [] } = useQuery<InventoryCost[]>({ queryKey: ['inventory-costs'], queryFn: () => fetchApi(`/inventory/costs${query}`) });
  const availablePresentations = useMemo(() => {
    if (!form.supplier_id) return presentations;
    const filtered = presentations.filter((item) => item.supplier_id === form.supplier_id);
    return filtered.length > 0 ? filtered : presentations;
  }, [presentations, form.supplier_id]);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['purchases'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory-costs'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'stock'] }),
    ]);
  };
  const createMutation = useMutation({
    mutationFn: () => fetchApi('/purchases', { method: 'POST', body: JSON.stringify({
      branch_id: branchId, supplier_id: form.supplier_id, folio: form.folio,
      document_type: form.document_type, payment_method: form.paid_from_cash ? 'cash' : 'other',
      paid_from_cash: form.paid_from_cash,
      lines: [{ presentation_id: form.presentation_id, quantity: form.quantity, unit_price: form.unit_price, discount: form.discount, tax: form.tax }],
    }) }),
    onSuccess: async () => {
      setOpen(false);
      setForm({ supplier_id: '', folio: '', document_type: 'invoice', presentation_id: '', quantity: '1', unit_price: '', discount: '0', tax: '0', paid_from_cash: true });
      setError('');
      await refresh();
    },
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

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Compras directas</h1>
          <p className="premium-header-subtitle">Recepciones, retiro de caja y costo promedio conciliados.</p>
        </div>
        <button className="premium-add-btn" onClick={() => setOpen(true)}>
          <Plus size={18} />
          Nueva compra
        </button>
      </div>

      {error && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      <div className="premium-card" style={{ marginBottom: 32 }}>
        {purchases.length === 0 ? (
          <div className="premium-empty-state">
            <ShoppingCart size={56} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay compras registradas</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Registra facturas y notas de compra para abastecer el almacén.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Folio / Documento</th>
                  <th>Proveedor</th>
                  <th>Total</th>
                  <th>Forma de pago</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {purchases.map((purchase) => (
                  <tr key={purchase.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ padding: 6, background: '#eff6ff', color: '#2563eb', borderRadius: 8 }}>
                          <ReceiptText size={16} />
                        </div>
                        <div>
                          <strong style={{ color: '#1e293b' }}>{purchase.folio}</strong>
                          <br />
                          <small style={{ color: '#64748b', textTransform: 'capitalize' }}>{purchase.document_type}</small>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span style={{ fontWeight: 600, color: '#334155' }}>
                        {suppliers.find((supplier) => supplier.id === purchase.supplier_id)?.commercial_name || purchase.supplier_id}
                      </span>
                    </td>
                    <td>
                      <strong style={{ fontSize: '1rem', color: '#0f172a' }}>${Number(purchase.total).toFixed(2)}</strong>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.85rem', color: '#475467', fontWeight: 500 }}>
                        {purchase.paid_from_cash ? '💵 Caja operativa' : '🏦 Crédito / Transferencia'}
                      </span>
                    </td>
                    <td>
                      <Badge variant={purchase.status === 'confirmed' ? 'success' : purchase.status === 'cancelled' ? 'default' : 'info'}>
                        {purchase.status === 'confirmed' ? 'Confirmado' : purchase.status === 'cancelled' ? 'Cancelado' : 'Borrador'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        {purchase.status === 'draft' && (
                          <Button variant="primary" onClick={() => void confirmPurchase(purchase.id)}>
                            <CheckCircle2 size={15} /> Confirmar
                          </Button>
                        )}
                        {purchase.status !== 'cancelled' && (
                          <Button variant="secondary" onClick={() => void cancelPurchase(purchase.id)}>
                            <XCircle size={15} /> Cancelar
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

      <div className="premium-card">
        <div style={{ padding: '20px 24px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
          <div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#1e293b', margin: 0 }}>Costo promedio por sucursal</h2>
            <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '2px 0 0' }}>Valuación ponderada de insumos en tiempo real</p>
          </div>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="premium-table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Insumo</th>
                <th>Existencia</th>
                <th>Costo promedio</th>
                <th>Último costo</th>
              </tr>
            </thead>
            <tbody>
              {costs.map((cost) => (
                <tr key={cost.item_id}>
                  <td style={{ color: '#64748b', fontWeight: 600 }}>{cost.item_sku}</td>
                  <td><strong style={{ color: '#1e293b' }}>{cost.item_name}</strong></td>
                  <td style={{ fontWeight: 600 }}>{Number(cost.quantity_on_hand)} {cost.unit_code}</td>
                  <td><strong style={{ color: '#047857' }}>${Number(cost.average_unit_cost).toFixed(4)}</strong></td>
                  <td style={{ color: '#475467' }}>${Number((cost as InventoryCost & { last_unit_cost?: number }).last_unit_cost || 0).toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal isOpen={open} onClose={() => setOpen(false)} title="Registrar compra directa" maxWidth="680px">
        <div className="premium-form-layout">
          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Proveedor</label>
              <Select
                value={form.supplier_id}
                onChange={(event) => setForm({ ...form, supplier_id: event.target.value, presentation_id: '' })}
              >
                <option value="">Selecciona proveedor</option>
                {suppliers.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>{supplier.commercial_name}</option>
                ))}
              </Select>
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Tipo de documento</label>
              <Select
                value={form.document_type}
                onChange={(event) => setForm({ ...form, document_type: event.target.value })}
              >
                <option value="invoice">Factura</option>
                <option value="ticket">Ticket</option>
                <option value="note">Nota de remisión</option>
                <option value="receipt">Recibo</option>
              </Select>
            </div>
          </div>

          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Folio del comprobante</label>
              <Input
                placeholder="Ej. F-98210"
                value={form.folio}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, folio: event.target.value })}
              />
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Presentación comercial</label>
              <Select
                value={form.presentation_id}
                onChange={(event) => {
                  const selected = presentations.find((item) => item.id === event.target.value);
                  setForm({
                    ...form,
                    presentation_id: event.target.value,
                    unit_price: String(selected?.last_net_price || ''),
                  });
                }}
              >
                <option value="">Selecciona presentación</option>
                {availablePresentations.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.base_unit_yield} {item.base_unit_code}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Cantidad de presentaciones</label>
              <Input
                type="number"
                step="any"
                placeholder="1"
                value={form.quantity}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, quantity: event.target.value })}
              />
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Precio unitario neto ($)</label>
              <Input
                type="number"
                step="0.01"
                placeholder="0.00"
                value={form.unit_price}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, unit_price: event.target.value })}
              />
            </div>
          </div>

          <div className="premium-form-grid">
            <div className="premium-form-group">
              <label className="premium-form-label">Descuento ($)</label>
              <Input
                type="number"
                step="0.01"
                placeholder="0.00"
                value={form.discount}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, discount: event.target.value })}
              />
            </div>

            <div className="premium-form-group">
              <label className="premium-form-label">Impuestos ($)</label>
              <Input
                type="number"
                step="0.01"
                placeholder="0.00"
                value={form.tax}
                onChange={(event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, tax: event.target.value })}
              />
            </div>
          </div>

          <label className="premium-checkbox-card">
            <input
              type="checkbox"
              checked={form.paid_from_cash}
              onChange={(event) => setForm({ ...form, paid_from_cash: event.target.checked })}
            />
            <span>Pagada con dinero en efectivo de la caja del turno</span>
          </label>

          <div className="premium-footer-actions">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !form.supplier_id || !form.folio || !form.presentation_id || !form.unit_price}
            >
              {createMutation.isPending ? 'Guardando...' : 'Guardar borrador'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default PurchasesList;
