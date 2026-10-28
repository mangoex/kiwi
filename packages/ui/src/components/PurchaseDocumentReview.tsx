import { useEffect, useRef, useState } from 'react';
import { Modal } from './Modal';
import { Button } from './Button';
import { formatPurchaseDecimal } from './purchaseDraft';
import { PurchaseSummary } from './PurchaseSummary';
import './PurchaseDocumentEditor.css';
export interface PurchaseDocumentView {
  id: string; folio: string; document_type: string; status: string; total: string | number;
  delivered_by_name?: string | null;
  document_date?: string; subtotal?: string | number; discount_total?: string | number; tax_total?: string | number;
  lines?: { id: string; presentation_snapshot?: { name?: string; base_unit_code?: string }; presentation_quantity?: string | number; base_quantity?: string | number; unit_price?: string | number; discount?: string | number; tax?: string | number; line_total?: string | number }[];
}
export interface PurchasePaymentReview { branchName: string; method: string; registerId: string; cashShiftId: string; message: string; recovering: boolean; canManage: boolean; canConfirm: boolean; }
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
  const documentTypes: Record<string, string> = { note: 'Nota', invoice: 'Factura', ticket: 'Ticket', receipt: 'Recibo' };
  const statuses: Record<string, string> = { draft: 'Pendiente de recepción', confirmed: 'Confirmada', cancelled: 'Cancelada' };
  return <Modal isOpen={Boolean(purchase)} onClose={() => { if (!pending && !paymentContext?.recovering) onClose(); }} title="Revisar nota registrada" maxWidth="1120px" contentClassName="purchase-review-modal">
    {purchase && <div ref={content} className="purchase-review">
      <div className="purchase-review-heading"><div><span className="purchase-eyebrow">{documentTypes[purchase.document_type] || purchase.document_type}</span><h4>{purchase.folio}</h4></div><span className="purchase-status">{statuses[purchase.status] || purchase.status}</span></div>
      <dl className="purchase-review-meta"><div><dt>Fecha del documento</dt><dd>{purchase.document_date?.slice(0, 10) || '—'}</dd></div>
      {paymentContext && <><div><dt>Sucursal</dt><dd>{paymentContext.branchName}</dd></div><div><dt>Forma de pago</dt><dd>{paymentContext.method}</dd></div>{paymentContext.cashShiftId && <><div><dt>Caja</dt><dd>{paymentContext.registerId}</dd></div><div><dt>Turno revisado</dt><dd>{paymentContext.cashShiftId.slice(-8)}</dd></div></>}</>}
      </dl>
      {purchase.delivered_by_name && <p>Entregó: {purchase.delivered_by_name}</p>}
      {(paymentContext?.message || failure) && <p role="alert">{paymentContext?.message || failure}</p>}
      {paymentContext?.recovering && <p role="status">Hay una confirmación pendiente de respuesta. Recupera el mismo intento antes de continuar.</p>}
      <div className="purchase-section-heading"><h4>Detalle de partidas</h4><span>{purchase.lines?.length || 0} partidas</span></div>
      <div className="purchase-review-table" tabIndex={0} role="region" aria-label="Partidas de la compra"><table><thead><tr><th scope="col">Presentación</th><th scope="col">Cantidad</th><th scope="col">Entrada base</th><th scope="col">Precio</th><th scope="col">Descuento</th><th scope="col">Impuesto</th><th scope="col">Importe</th></tr></thead><tbody>{purchase.lines?.map(line => <tr key={line.id}><td>{line.presentation_snapshot?.name ?? 'Sin referencia histórica'}</td><td>{formatPurchaseDecimal(line.presentation_quantity)}</td><td>{formatPurchaseDecimal(line.base_quantity)} <span className="purchase-unit">{line.presentation_snapshot?.base_unit_code}</span></td><td>${formatPurchaseDecimal(line.unit_price)}</td><td>${formatPurchaseDecimal(line.discount)}</td><td>${formatPurchaseDecimal(line.tax)}</td><td><strong>${formatPurchaseDecimal(line.line_total)}</strong></td></tr>)}</tbody></table></div>
      <PurchaseSummary totals={purchase} registered />
      <p className="purchase-footnote">Confirmar registra las entradas y, cuando corresponde, el retiro de caja de esta nota.</p>
      <div className="purchase-actions">
      <Button variant="secondary" disabled={pending || paymentContext?.recovering} onClick={onClose}>Cerrar revisión</Button> {paymentContext?.canManage && (purchase.status === 'draft' || paymentContext.recovering) && <Button disabled={pending || paymentContext.canConfirm === false} onClick={() => { setPending(true); setFailure(''); void onConfirm().catch(cause => setFailure(cause instanceof Error ? cause.message : 'No se pudo confirmar.')).finally(() => setPending(false)); }}>{pending ? 'Confirmando…' : paymentContext.recovering ? 'Recuperar confirmación pendiente' : 'Confirmar recepción de esta nota'}</Button>}
      </div>
    </div>}
  </Modal>;
}
