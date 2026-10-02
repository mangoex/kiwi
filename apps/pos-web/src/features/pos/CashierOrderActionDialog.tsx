import React, { useRef, useState } from 'react';
import { Button, Modal } from '@restaurantos/ui';
import type { OrderRequest } from './useCashTenderPreview';

export const ORDER_ACTION_STORAGE_KEY = 'pos_cashier_order_action_v1';
interface PendingAction { authority: string; orderId: string; key: string; path: string;
  body: Record<string, never>; label: string }

function clearPendingOrderAction(expectedKey: string): void {
  if (readPendingOrderAction()?.key === expectedKey) sessionStorage.removeItem(ORDER_ACTION_STORAGE_KEY);
}

export function readPendingOrderAction(): PendingAction | null {
  const raw = sessionStorage.getItem(ORDER_ACTION_STORAGE_KEY);
  if (raw === null) return null;
  if (raw.length > 5000) throw new Error('La acción pendiente guardada es inválida.');
  const value = JSON.parse(raw) as PendingAction;
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  if (!value || typeof value.authority !== 'string' || !value.authority || !uuid.test(value.orderId)
    || !uuid.test(value.key) || typeof value.label !== 'string' || value.label.length > 100 || !value.body
    || typeof value.body !== 'object' || Array.isArray(value.body)
    || Object.keys(value.body).length !== 0
    || !['start_delivery', 'deliver', 'close'].map((command) =>
      `/orders/${value.orderId}/fulfillment/${command}`).includes(value.path)) {
    throw new Error('La acción pendiente guardada es inválida. Revisa el estado del pedido.');
  }
  return value;
}

export function CashierOrderActionDialog({ orderId, folio, authority, request, command,
  label, paid, onClose, onApplied }: {
  orderId: string; folio: string; authority: string; request: OrderRequest; command: string;
  label: string; paid: boolean; onClose: () => void; onApplied: () => Promise<void>;
}) {
  const [stored] = useState(() => { try { return { pending: readPendingOrderAction(), error: '' }; }
    catch (failure) { return { pending: null, error: failure instanceof Error ? failure.message : 'No se puede leer la acción pendiente.' }; } });
  const [pending, setPending] = useState<PendingAction | null>(stored.pending);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const compatible = !stored.error && (!pending || (pending.authority === authority && pending.orderId === orderId));
  const confirm = async () => {
    if (busyRef.current || !compatible) return;
    busyRef.current = true; setBusy(true); setError('');
    let commandKey = pending?.key;
    try {
      const action: PendingAction = pending || { authority, orderId, key: crypto.randomUUID(), label,
        path: `/orders/${orderId}/fulfillment/${command}`, body: {},
      };
      commandKey = action.key;
      if (!pending) {
        if (readPendingOrderAction()) throw new Error('Resuelve la acción pendiente antes de confirmar otra.');
        sessionStorage.setItem(ORDER_ACTION_STORAGE_KEY, JSON.stringify(action)); setPending(action);
      }
      await request(action.path, { method: 'POST', headers: { 'Idempotency-Key': action.key }, body: JSON.stringify(action.body) });
      clearPendingOrderAction(action.key); setPending(null); setDone(true);
      try { await onApplied(); } catch { setError('Acción confirmada. Actualiza la lista de pedidos.'); }
    } catch (failure) {
      if (failure && typeof failure === 'object' && 'code' in failure
        && ['order_fulfillment_transition_invalid'].includes(String(failure.code))) {
        if (commandKey) clearPendingOrderAction(commandKey); setPending(null);
      }
      setError(failure instanceof Error ? failure.message : 'No se recibió confirmación.');
    } finally { busyRef.current = false; setBusy(false); }
  };
  return <Modal isOpen onClose={() => { if (!busyRef.current) onClose(); }} title={`${label} · ${folio}`}>
    {done ? <p role="status">Acción confirmada. El estado del pago se conserva.</p> : <>
      {!compatible && <p role="alert">Restablece el contexto de la acción pendiente antes de reintentar.</p>}
      {pending ? <p>Respuesta pendiente. Recupera la misma acción sin volver a enviarla como una intención nueva.</p> : <>
        <p>Confirma esta acción sólo cuando haya ocurrido físicamente. No confirma pago.</p>
        {command === 'close' && !paid && <p role="alert">El pedido todavía tiene pago pendiente.</p>}
      </>}
    </>}
    {(error || stored.error) && <p role="alert">{error || stored.error}</p>}
    {done ? <Button onClick={onClose}>Volver a pedidos</Button> : <Button disabled={busy || !compatible}
      onClick={() => void confirm()}>{busy ? 'Confirmando…' : pending ? 'Recuperar confirmación' : label}</Button>}
  </Modal>;
}
