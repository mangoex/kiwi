import { useEffect, useRef, useState } from 'react';
import { Modal } from './Modal';
import { Button } from './Button';
export interface PurchaseDocumentView {
  id: string; folio: string; document_type: string; status: string; total: string | number;
  document_date?: string; subtotal?: string | number; discount_total?: string | number; tax_total?: string | number;
  lines?: { id: string; presentation_snapshot?: { name?: string; base_unit_code?: string }; presentation_quantity?: string | number; base_quantity?: string | number; unit_price?: string | number; discount?: string | number; tax?: string | number; line_total?: string | number }[];
}
export interface PurchasePaymentReview { branchName: string; method: string; registerId: string; cashShiftId: string; message: string; recovering: boolean; canConfirm: boolean; }
export function PurchaseDocumentReview({ purchase, paymentContext, onClose, onConfirm }: { purchase: PurchaseDocumentView | null; paymentContext?: PurchasePaymentReview; onClose: () => void; onConfirm: () => Promise<void> }) {
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState('');
  const content = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!purchase) return;
    const dialog = content.current?.closest<HTMLElement>('[role="dialog"]');
    if (!dialog) return;
    const previous = document.activeElement;
    dialog.tabIndex = -1;
    dialog.setAttribute('aria-label', 'Revisar nota registrada');
    dialog.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      const buttons = [...dialog.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), [tabindex="0"]')].filter(element => element.offsetParent !== null);
      const first = buttons[0];
      const last = buttons.at(-1);
      const active = document.activeElement;
      if (!first || !last) { event.preventDefault(); dialog.focus(); }
      else if (event.shiftKey && (active === first || active === dialog)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (active === last || active === dialog)) { event.preventDefault(); first.focus(); }
    };
    dialog.addEventListener('keydown', trap);
    return () => {
      dialog.removeEventListener('keydown', trap);
      if (previous instanceof HTMLElement && previous.isConnected && !previous.closest('[inert]')) previous.focus();
    };
  }, [purchase?.id]);
  return <Modal isOpen={Boolean(purchase)} onClose={() => { if (!pending && !paymentContext?.recovering) onClose(); }} title="Revisar nota registrada" maxWidth="1000px">
    {purchase && <div ref={content}><p>{purchase.document_type} · {purchase.folio} · fecha: {purchase.document_date?.slice(0, 10)} · {purchase.status}</p>
      {paymentContext && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}><span>Sucursal: {paymentContext.branchName}</span><span>Pago: {paymentContext.method}</span>{paymentContext.cashShiftId && <><span>Caja: {paymentContext.registerId}</span><span>Turno revisado: {paymentContext.cashShiftId.slice(-8)}</span></>}</div>}
      {(paymentContext?.message || failure) && <p role="alert">{paymentContext?.message || failure}</p>}
      {paymentContext?.recovering && <p role="status">Hay una confirmación pendiente de respuesta. Recupera el mismo intento antes de continuar.</p>}
      <div style={{ overflowX: 'auto' }}><table className="premium-table"><thead><tr><th>Presentación</th><th>Cantidad</th><th>Entrada base</th><th>Precio</th><th>Descuento</th><th>Impuesto</th><th>Importe</th></tr></thead><tbody>{purchase.lines?.map(line => <tr key={line.id}><td>{line.presentation_snapshot?.name ?? 'Sin referencia histórica'}</td><td>{line.presentation_quantity}</td><td>{line.base_quantity} {line.presentation_snapshot?.base_unit_code}</td><td>{line.unit_price}</td><td>{line.discount}</td><td>{line.tax}</td><td>{line.line_total}</td></tr>)}</tbody></table></div>
      <p>Subtotal: {purchase.subtotal} · descuentos: {purchase.discount_total} · impuestos: {purchase.tax_total} · total registrado: {purchase.total}</p>
      <p>Confirmar registra las entradas y, cuando corresponde, el retiro de caja de esta nota.</p>
      <Button variant="secondary" disabled={pending || paymentContext?.recovering} onClick={onClose}>Cerrar revisión</Button> {(purchase.status === 'draft' || paymentContext?.recovering) && <Button disabled={pending || paymentContext?.canConfirm === false} onClick={() => { setPending(true); setFailure(''); void onConfirm().catch(cause => setFailure(cause instanceof Error ? cause.message : 'No se pudo confirmar.')).finally(() => setPending(false)); }}>{pending ? 'Confirmando…' : paymentContext?.recovering ? 'Recuperar confirmación pendiente' : 'Confirmar recepción de esta nota'}</Button>}
    </div>}
  </Modal>;
}
