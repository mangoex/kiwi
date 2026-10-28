import { formatPurchaseDecimal } from './purchaseDraft';

interface PurchaseTotals {
  subtotal?: string | number; discount_total?: string | number;
  tax_total?: string | number; total: string | number;
}
export function PurchaseSummary({ totals, registered = false }: { totals: PurchaseTotals; registered?: boolean }) {
  return <div className="purchase-summary" aria-live="polite">
    <dl className="purchase-summary-breakdown">
      <div><dt>Subtotal</dt><dd>${formatPurchaseDecimal(totals.subtotal)}</dd></div>
      <div><dt>Descuentos</dt><dd>${formatPurchaseDecimal(totals.discount_total)}</dd></div>
      <div><dt>Impuestos</dt><dd>${formatPurchaseDecimal(totals.tax_total)}</dd></div>
    </dl>
    <strong className="purchase-summary-total">{registered ? 'Total registrado' : 'Total'}: ${formatPurchaseDecimal(totals.total)}</strong>
  </div>;
}
