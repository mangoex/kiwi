import React, { useRef, useState } from 'react';
import { Modal, Button } from '@restaurantos/ui';
import { CashTenderFields } from './CashTenderFields';
import { formatMxnCents } from './cartMoney';
import { useCashTenderPreview, type CashTender, type OrderRequest } from './useCashTenderPreview';
import { clearPaymentAttempt, paymentWasDefinitelyRejected, readPaymentAttempt, storePaymentAttempt, submitCashierPayment,
  type PaymentAttempt } from './cashierPayment';

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
  const compatible = !stored.error && (!attempt || (attempt.authority === authority && attempt.orderId === orderId));
  const preview = useCashTenderPreview(request, authority, `/orders/${orderId}/payment-preview`,
    attempt || paid ? null : { method, ...(method === 'cash' && received.trim() ? { received_cash: received } : {}) });
  const totalRef = useRef<number | null>(null);
  if (preview?.data) totalRef.current = preview.data.total_cents;
  const canConfirm = compatible && !busy && (Boolean(attempt) || Boolean(preview?.data
    && preview.data.total_cents > 0 && (method !== 'cash' || preview.data.cash_tender?.can_confirm)));

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
      {error && <p role="alert">{error}</p>}
      <Button onClick={onClose}>Volver a pedidos</Button>
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
  </Modal>;
}
