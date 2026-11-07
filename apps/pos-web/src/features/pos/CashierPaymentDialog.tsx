import React, { useRef, useState } from 'react';
import { Modal, Button } from '@restaurantos/ui';
import { CashTenderFields } from './CashTenderFields';
import { formatMxnCents } from './cartMoney';
import { useCashTenderPreview, type CashTender, type OrderRequest } from './useCashTenderPreview';
import { clearPaymentAttempt, paymentWasDefinitelyRejected, readPaymentAttempt, storePaymentAttempt, submitCashierPayment,
  type PaymentAttempt } from './cashierPayment';
import { Printer } from 'lucide-react';
import {
  ThermalReceiptModal,
  buildTicketPrintData,
  buildKitchenPrintData,
  dispatchPosPrintJob,
  loadPrinterConfig,
  type OrderLike,
} from '../printing';

export function CashierPaymentDialog({ orderId, folio, authority, registerId, request, initialMethod,
  onClose, onPaid }: {
  orderId: string; folio: string; authority: string; registerId: string; request: OrderRequest;
  initialMethod: string; onClose: () => void; onPaid: () => Promise<void>;
}) {
  const [method, setMethod] = useState(initialMethod);
  const [received, setReceived] = useState('');
  const [stored] = useState(() => { try { return { attempt: readPaymentAttempt(sessionStorage), error: '' }; }
    catch (failure) { return { attempt: null, error: failure instanceof Error ? failure.message : 'No se puede leer el cobro pendiente.' }; } });
  const [attempt, setAttempt] = useState<PaymentAttempt | null>(stored.attempt);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [paid, setPaid] = useState<{ cash_tender?: CashTender; order_status: string } | null>(null);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [orderDetail, setOrderDetail] = useState<OrderLike | null>(null);
  const [loadingReceipt, setLoadingReceipt] = useState(false);
  const [autoPrintNotice, setAutoPrintNotice] = useState('');
  const compatible = !stored.error && (!attempt || (attempt.authority === authority && attempt.orderId === orderId));
  const preview = useCashTenderPreview(request, authority, `/orders/${orderId}/payment-preview`,
    attempt || paid ? null : { method, ...(method === 'cash' && received.trim() ? { received_cash: received } : {}) });
  const totalRef = useRef<number | null>(null);
  if (preview?.data) totalRef.current = preview.data.total_cents;
  const canConfirm = compatible && !busy && (Boolean(attempt) || Boolean(preview?.data
    && preview.data.total_cents > 0 && (method !== 'cash' || preview.data.cash_tender?.can_confirm)));

  const loadOrderForPrint = async (): Promise<OrderLike> => {
    if (orderDetail) return orderDetail;
    try {
      const detail = await request<OrderLike>(`/orders/${encodeURIComponent(orderId)}`);
      setOrderDetail(detail);
      return detail;
    } catch {
      const fallback: OrderLike = {
        folio,
        total_cents: preview?.data?.total_cents || 0,
        created_at: new Date().toISOString(),
      };
      setOrderDetail(fallback);
      return fallback;
    }
  };

  const openReceipt = async () => {
    if (!orderDetail) {
      setLoadingReceipt(true);
      try {
        await loadOrderForPrint();
        setReceiptOpen(true);
      } finally {
        setLoadingReceipt(false);
      }
    } else {
      setReceiptOpen(true);
    }
  };

  const confirm = async () => {
    if (busyRef.current || !canConfirm) return;
    busyRef.current = true; setBusy(true); setError('');
    let commandKey = attempt?.key;
    try {
      let command = attempt;
      if (!command) {
        if (!preview?.data) return;
        command = { schema: 1, authority, orderId, key: crypto.randomUUID(), body: {
          amount_cents: preview.data.total_cents, method, register_id: registerId,
          ...(method === 'cash' ? { received_cash: received } : {}),
        } };
        storePaymentAttempt(sessionStorage, command);
        setAttempt(command);
      }
      commandKey = command.key;
      const response = await submitCashierPayment(request, command.orderId, { method: 'POST',
          headers: { 'Idempotency-Key': command.key }, body: JSON.stringify(command.body) });
      clearPaymentAttempt(sessionStorage, command.key);
      setAttempt(null); setPaid(response);

      const printerConfig = loadPrinterConfig();
      if (printerConfig.autoPrintOnConfirm) {
        void (async () => {
          const detail = await loadOrderForPrint();
          const tData = buildTicketPrintData(detail, {
            cashTender: response.cash_tender
              ? { receivedCents: response.cash_tender.received_cents, changeCents: response.cash_tender.change_cents }
              : null,
          });
          const kData = buildKitchenPrintData(detail);
          const printRes = await dispatchPosPrintJob({
            ticketData: tData,
            kitchenData: kData,
            copies: printerConfig.autoPrintCopies,
            kickDrawer: command.body.method === 'cash',
            config: printerConfig,
          });
          if (printRes.ok) {
            setAutoPrintNotice(`✓ ${printRes.message}`);
          }
        })();
      }

      try { await onPaid(); } catch { setError('Pago confirmado. Actualiza la lista para ver el estado.'); }
    } catch (reason) {
      if (paymentWasDefinitelyRejected(reason)) {
        if (commandKey) clearPaymentAttempt(sessionStorage, commandKey); setAttempt(null);
      }
      setError(reason instanceof Error ? reason.message : 'No se recibió confirmación del pago.');
    } finally { busyRef.current = false; setBusy(false); }
  };
  return <Modal isOpen onClose={() => { if (!busyRef.current) onClose(); }} title={`Cobrar · ${folio}`}>
    {paid ? <section className="pos-cashier-payment-result" role="status">
      <strong>Pago confirmado</strong>
      {paid.cash_tender && <p>Cambio: <strong>{formatMxnCents(paid.cash_tender.change_cents)}</strong></p>}
      <p>El cobro no cambia el estado de preparación ni confirma la entrega.</p>
      <p>Las impresiones quedan en cola; consulta su estado antes de reimprimir.</p>
      {autoPrintNotice && <p style={{ color: '#059669', fontWeight: 600 }}>{autoPrintNotice}</p>}
      {error && <p role="alert">{error}</p>}
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <Button variant="primary" disabled={loadingReceipt} onClick={() => void openReceipt()} title="Ver e imprimir ticket o comanda térmica">
          <Printer size={16} /> {loadingReceipt ? 'Cargando ticket…' : 'Imprimir Ticket / Comanda'}
        </Button>
        <Button variant="secondary" onClick={onClose}>Volver a pedidos</Button>
      </div>
    </section> : <>
      {!compatible ? <p role="alert">Este cobro pendiente pertenece a otra sesión, caja o transporte. Restablece su contexto para recuperarlo.</p> : null}
      {attempt ? <section className="pos-cashier-payment-result">
        <strong>Cobro pendiente de confirmación</strong>
        <p>Reintenta la misma intención sin volver a recibir dinero ni crear otra venta.</p>
        <p>Total: {formatMxnCents(attempt.body.amount_cents)} · {attempt.body.method}</p>
        {attempt.body.received_cash && <p>Recibido: {attempt.body.received_cash}</p>}
      </section> : <>
        <p className="pos-cashier-payment-total">Total <strong>{totalRef.current !== null ? formatMxnCents(totalRef.current) : '—'}</strong></p>
        {stored.error && <p role="alert">{stored.error}</p>}
        <div className="pos-payment-grid">{[
          ['cash', 'Efectivo'], ['debit_card', 'Débito'], ['credit_card', 'Crédito'], ['transfer', 'Transferencia'],
        ].map(([value, label]) => <button key={value} type="button" aria-pressed={method === value}
          className={method === value ? 'active' : ''} disabled={busy} onClick={() => setMethod(value)}>{label}</button>)}</div>
        {method === 'cash' ? <CashTenderFields received={received} onChange={setReceived}
          tender={preview?.data?.cash_tender} error={preview?.error} disabled={busy} />
          : preview?.error ? <p role="alert">{preview.error}</p> : null}
        <p>Confirma sólo después de recibir el pago. Cocina y entrega conservan su estado.</p>
      </>}
      {error && <p role="alert">{error}</p>}
      <Button disabled={!canConfirm || !registerId} onClick={() => void confirm()}>
        {busy ? 'Confirmando…' : attempt ? 'Recuperar confirmación' : 'Confirmar pago recibido'}
      </Button>
    </>}
      {receiptOpen && orderDetail && (
      <ThermalReceiptModal
        isOpen={receiptOpen}
        onClose={() => setReceiptOpen(false)}
        ticketData={buildTicketPrintData(orderDetail, {
          cashTender: paid?.cash_tender
            ? { receivedCents: paid.cash_tender.received_cents, changeCents: paid.cash_tender.change_cents }
            : null,
        })}
        kitchenData={buildKitchenPrintData(orderDetail)}
      />
    )}
  </Modal>;
}
