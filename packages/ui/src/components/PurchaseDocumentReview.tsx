import React, { useState } from 'react';
import { Modal } from './Modal';
import { Button } from './Button';
export interface PurchaseDocumentView {
  id: string; folio: string; document_type: string; status: string; total: string | number;
  document_date?: string; subtotal?: string | number; discount_total?: string | number; tax_total?: string | number;
  lines?: { id: string; presentation_snapshot?: { name?: string; base_unit_code?: string }; presentation_quantity?: string | number; base_quantity?: string | number; unit_price?: string | number; discount?: string | number; tax?: string | number; line_total?: string | number }[];
}
export function PurchaseDocumentReview({ purchase, onClose, onConfirm }: { purchase: PurchaseDocumentView | null; onClose: () => void; onConfirm: () => Promise<void> }) {
  const [pending, setPending] = useState(false);
  return <Modal isOpen={Boolean(purchase)} onClose={() => { if (!pending) onClose(); }} title="Revisar nota registrada" maxWidth="1000px">
    {purchase && <><p>{purchase.document_type} · {purchase.folio} · fecha: {purchase.document_date?.slice(0, 10)} · {purchase.status}</p>
      <div style={{ overflowX: 'auto' }}><table className="premium-table"><thead><tr><th>Presentación</th><th>Cantidad</th><th>Entrada base</th><th>Precio</th><th>Descuento</th><th>Impuesto</th><th>Importe</th></tr></thead><tbody>{purchase.lines?.map(line => <tr key={line.id}><td>{line.presentation_snapshot?.name ?? 'Sin referencia histórica'}</td><td>{line.presentation_quantity}</td><td>{line.base_quantity} {line.presentation_snapshot?.base_unit_code}</td><td>{line.unit_price}</td><td>{line.discount}</td><td>{line.tax}</td><td>{line.line_total}</td></tr>)}</tbody></table></div>
      <p>Subtotal: {purchase.subtotal} · descuentos: {purchase.discount_total} · impuestos: {purchase.tax_total} · total registrado: {purchase.total}</p>
      <p>Confirmar registra las entradas y, cuando corresponde, el retiro de caja de esta nota.</p>
      <Button variant="secondary" disabled={pending} onClick={onClose}>Cerrar revisión</Button> {purchase.status === 'draft' && <Button disabled={pending} onClick={() => { setPending(true); void onConfirm().finally(() => setPending(false)); }}>{pending ? 'Confirmando…' : 'Confirmar recepción de esta nota'}</Button>}
    </>}
  </Modal>;
}
