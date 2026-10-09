import { useAdminSession } from '../../lib/adminSession';
import { useAdminPermission } from '../../lib/adminSession';
import React, { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, PurchaseDocumentReview, PurchaseDocumentEditor, ContextualPresentationForm, type PresentationItem, type PresentationUnit } from '@restaurantos/ui';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Plus, CheckCircle2, XCircle, ReceiptText, AlertCircle, ShoppingCart, Sparkles } from 'lucide-react';
import '../../premium-catalogs.css';
import { SuggestedPurchasesModal } from './SuggestedPurchasesModal';
import type { PurchaseCashContextV1 } from '../../../../../packages/contracts/purchase-workspace-v1';
import { createPurchaseAttempt, isDefinitivePurchaseRejection, purchaseAttemptKey, purchaseMethodLabels, purchaseScopeKey, readPurchaseAttempt, selectedPurchaseRegister, type PurchaseAttempt } from './purchaseConfirmation';

interface Supplier { id: string; commercial_name: string; }
interface Presentation { id: string; supplier_id: string; supplier_name: string; item_id: string; item_name: string; item_sku: string; name: string; last_net_price: number; base_unit_yield: number; base_unit_code: string; }
interface PurchaseLine { id: string; presentation_snapshot: { name: string }; presentation_quantity: number; base_quantity: number; }
interface Purchase { id: string; organization_id: string; branch_id: string; payment_method: string; folio: string; supplier_id: string; document_type: string; total: number; status: string; paid_from_cash: boolean; cash_movement_id?: string; confirmation_idempotency_key?: string; confirmed_by?: string; confirmed_at?: string; lines: PurchaseLine[]; }
interface InventoryCost { item_id: string; item_name: string; item_sku: string; quantity_on_hand: number; average_unit_cost: number; unit_code: string; }

const PurchasesList = () => {
  const { session } = useAdminSession();
  return <PurchasesWorkspace key={`${session.organization_id}:${session.user.id}:${session.active_branch.id}`} />;
};

const PurchasesWorkspace = () => {
  const {session:canonicalSession} = useAdminSession();
  const authority = { organization_id: canonicalSession.organization_id || '', actor_id: canonicalSession.user.id, branch_id: canonicalSession.active_branch.id };
  const scope = purchaseScopeKey(authority);
  const canWrite = useAdminPermission('purchases.manage');
  const canWithdraw = useAdminPermission('cash.movement.withdraw');
  const canReadInventory = useAdminPermission('inventory.read');
  const branchId = authority.branch_id;
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [review, setReview] = useState<Purchase | null>(null);
  const [suggestedOpen, setSuggestedOpen] = useState(false);
  const [error, setError] = useState('');
  const [registerId, setRegisterId] = useState('');
  const [uncertain, setUncertain] = useState(false);
  const attempt = useRef<PurchaseAttempt | null>(null);
  const sending = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [captureVersion, setCaptureVersion] = useState(0);
  const [initialSupplierId, setInitialSupplierId] = useState('');
  const query = branchId ? `?branch_id=${branchId}` : '';
  const { data: purchases = [], error: readError, isPending, refetch } = useQuery<Purchase[]>({ queryKey: ['purchases', scope], queryFn: () => fetchApi(`/purchases${query}`) });
  const { data: suppliers = [] } = useQuery<Supplier[]>({ queryKey: ['suppliers', scope], queryFn: () => fetchApi(`/suppliers${query}`) });
  const { data: presentations = [] } = useQuery<Presentation[]>({ queryKey: ['purchase-presentations', scope], queryFn: () => fetchApi(`/purchase-presentations${query}`) });
  const { data: costs = [] } = useQuery<InventoryCost[]>({ queryKey: ['inventory-costs', scope], queryFn: () => fetchApi(`/inventory/costs${query}`), enabled: canReadInventory });
  const { data: items = [] } = useQuery<PresentationItem[]>({ queryKey: ['purchase-items', scope], queryFn: () => fetchApi('/inventory/items' + query), enabled: Boolean(branchId) && canReadInventory && canWrite });
  const { data: units = [] } = useQuery<PresentationUnit[]>({ queryKey: ['inventory-units', scope], queryFn: () => fetchApi('/inventory/units'), enabled: canReadInventory && canWrite });
  const cash = useQuery<PurchaseCashContextV1>({ queryKey: ['purchase-cash', scope], queryFn: () => fetchApi(`/purchases/cash-context${query}`), enabled: canWrite && canWithdraw && Boolean(authority.organization_id), staleTime: 0 });
  useEffect(() => {
    const hint = localStorage.getItem(`purchase-register:${scope}`) || localStorage.getItem('pos_register_id');
    setRegisterId(selectedPurchaseRegister(cash.data, branchId, hint));
  }, [cash.data, branchId, scope]);
  useEffect(() => {
    if (attempt.current || !authority.organization_id) return;
    for (const row of purchases) {
      try {
        const saved = readPurchaseAttempt(sessionStorage, authority, row.id);
        if (saved) { attempt.current = saved; setReview(row); setUncertain(true); break; }
        const legacyKey = `purchase_confirmation_${row.id}`;
        const legacy = localStorage.getItem(legacyKey);
        if (legacy) {
          if (row.confirmed_at && row.confirmation_idempotency_key === legacy && row.confirmed_by === authority.actor_id) { localStorage.removeItem(legacyKey); continue; }
          setReview(row); setUncertain(true); setError('Hay un intento anterior sin contexto recuperable. Revisa el resultado de esta nota antes de confirmar otra vez.'); break;
        }
      } catch (cause) { setError(String(cause)); setUncertain(true); setReview(row); break; }
    }
  }, [purchases, scope]);
  useEffect(() => { setReview(current => current ? purchases.find(row => row.id === current.id) || current : null); }, [purchases]);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['purchases', scope] }),
      queryClient.invalidateQueries({ queryKey: ['inventory-costs', scope] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'stock'] }),
      ...['cash-shifts', 'cash-movements', 'cash-ledger', 'cash-shift', 'current-shift', 'purchase-cash', 'expense-cash'].map(key => queryClient.invalidateQueries({ queryKey: [key] })),
    ]);
  };
  const confirmPurchase = async (purchase: Purchase) => {
    if (!canWrite || sending.current) return false;
    let next: PurchaseAttempt;
    let recovering = uncertain;
    try {
      const saved = readPurchaseAttempt(sessionStorage, authority, purchase.id);
      if (purchase.organization_id !== authority.organization_id || purchase.branch_id !== authority.branch_id) throw new Error('Vuelve a la cuenta y sucursal de esta compra antes de recuperar.');
      recovering = Boolean(saved) || uncertain;
      if (uncertain && !saved) throw new Error('Revisa el resultado pendiente antes de generar otro intento.');
      next = saved || createPurchaseAttempt(authority, purchase, cash.data, registerId, `purchase:${purchase.id}:${crypto.randomUUID()}`);
      if (next.purchase_id !== purchase.id) throw new Error('Hay otra compra pendiente de recuperar.');
      sessionStorage.setItem(purchaseAttemptKey(authority, purchase.id), JSON.stringify(next));
      attempt.current = next;
      sending.current = true;
      await fetchApi(`/purchases/${purchase.id}/confirm`, {
        method: 'POST',
        headers: { 'Idempotency-Key': next.key },
        body: JSON.stringify(next.body),
      });
      sessionStorage.removeItem(purchaseAttemptKey(authority, purchase.id));
      attempt.current = null;
      if (!alive.current) return true;
      setError(''); setUncertain(false);
      await refresh().catch(() => setError('La compra se confirmó. Actualiza las vistas para consultar el resultado.'));
      return true;
    } catch (reason) {
      if (!alive.current) return false;
      const rejected = reason instanceof ApiError && isDefinitivePurchaseRejection(reason.status, reason.code, recovering);
      if (rejected) { sessionStorage.removeItem(purchaseAttemptKey(authority, purchase.id)); attempt.current = null; setUncertain(false); void cash.refetch(); void refetch(); }
      else if (attempt.current) setUncertain(true);
      setError(reason instanceof Error ? reason.message : 'No fue posible confirmar.');
      return false;
    } finally { sending.current = false; }
  };
  const cancelPurchase = async (purchaseId: string) => {
    if (!canWrite || uncertain || sending.current) return;
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
          {canWrite && canReadInventory && <button
            className="premium-add-btn"
            style={{ background: 'linear-gradient(135deg, #059669 0%, #0d9488 100%)' }}
            onClick={() => setSuggestedOpen(true)}
          >
            <Sparkles size={18} />
            Sugerencias IA & Mermas
          </button>}
          {canWrite && <button className="premium-add-btn" onClick={() => setOpen(true)}>
            <Plus size={18} />
            Nueva compra
          </button>}
        </div>
      </div>

      {isPending && <p role="status">Cargando compras…</p>}
      {readError && <p role="alert">{readError.message} <button onClick={() => void refetch()}>Reintentar</button></p>}
      {error && (
        <div role="alert" style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '12px 16px', borderRadius: 12, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {canWrite && <div className="premium-card" style={{ marginBottom: 20, padding: '16px 20px' }}>
        <label style={{ display: 'grid', gap: 6, maxWidth: 360, fontWeight: 600 }}>
          Caja para compras en efectivo
          <select
            value={registerId}
            disabled={!canWithdraw || cash.isPending || uncertain}
            onChange={(event: React.ChangeEvent<HTMLSelectElement>) => {
              const value = event.target.value;
              setRegisterId(value);
              localStorage.setItem(`purchase-register:${scope}`, value);
            }}
          ><option value="">Selecciona caja</option>{cash.data?.open_registers.map(box => <option key={box.cash_shift_id} value={box.register_id}>{box.register_id}</option>)}</select>
          <small style={{ color: '#64748b', fontWeight: 400 }}>
            {!canWithdraw ? 'Tu cuenta no tiene permiso de retiro.' : cash.error ? cash.error.message : cash.isPending ? 'Consultando turnos abiertos…' : cash.data?.open_registers.length === 0 ? 'No hay turnos abiertos. Puedes guardar una nota y confirmarla después.' : `Sucursal: ${canonicalSession.active_branch.name}.`}
          </small>
        </label>
      </div>}

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
                        {purchaseMethodLabels[purchase.payment_method] || purchase.payment_method}
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
                          (canWrite ? <Button variant="primary" disabled={uncertain} onClick={() => { void fetchApi<Purchase[]>(`/purchases${query}`).then(rows => { if (alive.current) setReview(rows.find(row => row.id === purchase.id) || null); }).catch(cause => { if (alive.current) setError(String(cause)); }); }}>
                            <CheckCircle2 size={15} /> Confirmar
                          </Button> : null)
                        )}
                        {purchase.status !== 'cancelled' && (
                          (canWrite ? <Button variant="secondary" disabled={uncertain} onClick={() => void cancelPurchase(purchase.id)}>
                            <XCircle size={15} /> Cancelar
                          </Button> : null)
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

      {canReadInventory && <div className="premium-card">
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
      </div>}

      <PurchaseDocumentReview purchase={review} paymentContext={{ branchName: canonicalSession.active_branch.name, method: purchaseMethodLabels[review?.payment_method || ''] || review?.payment_method || '', registerId: uncertain ? attempt.current?.body.register_id || '' : registerId, cashShiftId: uncertain ? attempt.current?.body.expected_cash_shift_id || '' : cash.data?.open_registers.find(box => box.register_id === registerId)?.cash_shift_id || '', message: error, recovering: uncertain, canConfirm: Boolean(authority.organization_id) && canWrite && (!uncertain || Boolean(attempt.current)) && (!review?.paid_from_cash || (canWithdraw && (uncertain || Boolean(cash.data?.open_registers.some(box => box.register_id === registerId))))) }} onClose={() => { if (!uncertain) setReview(null); }} onConfirm={async () => { if (review && await confirmPurchase(review)) setReview(null); }} />
      {canWrite && canonicalSession && <PurchaseDocumentEditor
        key={scope + ':' + captureVersion}
        scope={scope} branchId={branchId} isOpen={open} onClose={() => setOpen(false)}
        suppliers={suppliers} presentations={presentations} request={fetchApi}
        initialSupplierId={initialSupplierId}
        onCreated={async () => { await refresh(); setCaptureVersion(value => value + 1); }}
        catalogTools={canReadInventory ? (supplierId, done) => <ContextualPresentationForm
          key={supplierId} supplierId={supplierId} branchId={branchId} items={items} units={units} request={fetchApi}
          onCancel={done} onSaved={async () => { await queryClient.invalidateQueries({ queryKey: ['purchase-presentations', scope] }); done(); }}
        /> : undefined}
      />}

      {canWrite && canReadInventory && <SuggestedPurchasesModal
        open={suggestedOpen}
        onClose={() => setSuggestedOpen(false)}
        branchId={branchId}
        onSelectSupplierForPurchase={(supId) => {
          setInitialSupplierId(supId);
          setOpen(true);
        }}
      />}
    </>
  );
};

export default PurchasesList;
