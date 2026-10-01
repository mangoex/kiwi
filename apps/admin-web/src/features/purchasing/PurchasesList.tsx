import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Badge, PurchaseDocumentReview, PurchaseDocumentEditor, ContextualPresentationForm, type PresentationItem, type PresentationUnit } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, CheckCircle2, XCircle, ReceiptText, AlertCircle, ShoppingCart, Sparkles } from 'lucide-react';
import '../../premium-catalogs.css';
import { resolveBranchId, getSessionUser } from '../../lib/branchContext';
import { SuggestedPurchasesModal } from './SuggestedPurchasesModal';

interface Supplier { id: string; commercial_name: string; }
interface Presentation { id: string; supplier_id: string; name: string; last_net_price: number; base_unit_yield: number; base_unit_code: string; }
interface PurchaseLine { id: string; presentation_snapshot: { name: string }; presentation_quantity: number; base_quantity: number; }
interface Purchase { id: string; folio: string; supplier_id: string; document_type: string; total: number; status: string; paid_from_cash: boolean; cash_movement_id?: string; lines: PurchaseLine[]; }
interface InventoryCost { item_id: string; item_name: string; item_sku: string; quantity_on_hand: number; average_unit_cost: number; unit_code: string; }

const PurchasesList = () => {
  const branchId = resolveBranchId();
  const queryClient = useQueryClient();
  const actorId = getSessionUser().id || "";
  const [open, setOpen] = useState(false);
  const [review, setReview] = useState<Purchase | null>(null);
  const [suggestedOpen, setSuggestedOpen] = useState(false);
  const [error, setError] = useState('');
  const [registerId, setRegisterId] = useState(() => localStorage.getItem('pos_register_id') || '');
  const [captureVersion, setCaptureVersion] = useState(0);
  const [initialSupplierId, setInitialSupplierId] = useState('');
  const query = branchId ? `?branch_id=${branchId}` : '';
  const { data: purchases = [] } = useQuery<Purchase[]>({ queryKey: ['purchases', branchId, actorId], queryFn: () => fetchApi(`/purchases${query}`) });
  const { data: suppliers = [] } = useQuery<Supplier[]>({ queryKey: ['suppliers', branchId, actorId], queryFn: () => fetchApi(`/suppliers${query}`) });
  const { data: presentations = [] } = useQuery<Presentation[]>({ queryKey: ['purchase-presentations', branchId, actorId], queryFn: () => fetchApi(`/purchase-presentations${query}`) });
  const { data: costs = [] } = useQuery<InventoryCost[]>({ queryKey: ['inventory-costs', branchId, actorId], queryFn: () => fetchApi(`/inventory/costs${query}`) });
  const { data: canonicalSession } = useQuery<{ user: { id: string }; permissions: string[] }>({ queryKey: ['purchase-session', branchId, actorId], queryFn: () => fetchApi('/auth/session' + query), enabled: Boolean(branchId) });
  const { data: items = [] } = useQuery<PresentationItem[]>({ queryKey: ['purchase-items', branchId, actorId], queryFn: () => fetchApi('/inventory/items' + query), enabled: Boolean(branchId) });
  const { data: units = [] } = useQuery<PresentationUnit[]>({ queryKey: ['inventory-units'], queryFn: () => fetchApi('/inventory/units') });
  const scope = (canonicalSession?.user.id || '') + ':' + branchId;

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['purchases', branchId, actorId] }),
      queryClient.invalidateQueries({ queryKey: ['inventory-costs', branchId, actorId] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'stock'] }),
    ]);
  };
  const confirmPurchase = async (purchase: Purchase) => {
    const configuredRegisterId = (localStorage.getItem('pos_register_id') || '').trim();
    if (purchase.paid_from_cash && !configuredRegisterId) {
      setError('Configura una caja antes de confirmar una compra en efectivo.');
      return;
    }
    const storageKey = `purchase_confirmation_${purchase.id}`;
    const idempotencyKey = localStorage.getItem(storageKey) || `purchase:${purchase.id}:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, idempotencyKey);
    try {
      await fetchApi(`/purchases/${purchase.id}/confirm`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey },
        body: JSON.stringify({ ...(purchase.paid_from_cash ? { register_id: configuredRegisterId } : {}) }),
      });
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
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            className="premium-add-btn"
            style={{ background: 'linear-gradient(135deg, #059669 0%, #0d9488 100%)' }}
            onClick={() => setSuggestedOpen(true)}
          >
            <Sparkles size={18} />
            Sugerencias IA & Mermas
          </button>
          <button className="premium-add-btn" onClick={() => setOpen(true)}>
            <Plus size={18} />
            Nueva compra
          </button>
        </div>
      </div>

      {error && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      <div className="premium-card" style={{ marginBottom: 20, padding: '16px 20px' }}>
        <label style={{ display: 'grid', gap: 6, maxWidth: 360, fontWeight: 600 }}>
          Caja para compras en efectivo
          <Input
            value={registerId}
            placeholder="Ej. CAJA-01"
            onChange={(event: React.ChangeEvent<HTMLInputElement>) => {
              const value = event.target.value;
              setRegisterId(value);
              localStorage.setItem('pos_register_id', value);
            }}
          />
          <small style={{ color: '#64748b', fontWeight: 400 }}>
            Debe tener un turno abierto en la sucursal seleccionada.
          </small>
        </label>
      </div>

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
                      <strong style={{ fontSize: '1rem', color: '#0f172a' }}>${purchase.total}</strong>
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
                          <Button variant="primary" onClick={() => { void fetchApi<Purchase[]>(`/purchases${query}`).then(rows => setReview(rows.find(row => row.id === purchase.id) || null)).catch(cause => setError(String(cause))); }}>
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
            <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '2px 0 0' }}>Sucursal y almacén seleccionados · se actualiza al confirmar recepciones</p>
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

      <PurchaseDocumentReview purchase={review} onClose={() => setReview(null)} onConfirm={async () => { if (review) await confirmPurchase(review); setReview(null); }} />
      {canonicalSession && <PurchaseDocumentEditor
        key={scope + ':' + captureVersion}
        scope={scope} branchId={branchId} isOpen={open} onClose={() => setOpen(false)}
        suppliers={suppliers} presentations={presentations} request={fetchApi}
        initialSupplierId={initialSupplierId}
        onCreated={async () => { await refresh(); setCaptureVersion(value => value + 1); }}
        catalogTools={(supplierId, done) => <ContextualPresentationForm
          key={supplierId} supplierId={supplierId} branchId={branchId} items={items} units={units} request={fetchApi}
          onCancel={done} onSaved={async () => { await queryClient.invalidateQueries({ queryKey: ['purchase-presentations', branchId, actorId] }); done(); }}
        />}
      />}

      <SuggestedPurchasesModal
        open={suggestedOpen}
        onClose={() => setSuggestedOpen(false)}
        branchId={branchId}
        onSelectSupplierForPurchase={(supId) => {
          setInitialSupplierId(supId);
          setOpen(true);
        }}
      />
    </>
  );
};

export default PurchasesList;
