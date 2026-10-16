import React, { useId, useState } from 'react';
import { Bike, Check, ChefHat, ChevronDown, Clock, PackageCheck, ShoppingBag, X } from 'lucide-react';
import { formatMoney } from '../api';
import { getTrackingPresentation } from '../orderTracking';
import type { OrderTrackingState } from '../hooks/usePublicOrderTracking';
import './ActiveOrderTracker.css';

interface Props {
  tracking: OrderTrackingState;
  branchPhone?: string;
  onlyReference?: string;
}

export function ActiveOrderTracker({ tracking, branchPhone, onlyReference }: Props) {
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  const reference = onlyReference || tracking.selectedReference;
  const ref = tracking.references.find(item => item.public_reference === reference);
  if (!ref) return null;
  const order = tracking.states[ref.public_reference];
  const error = tracking.errors[ref.public_reference];
  const view = order ? getTrackingPresentation(order) : null;
  const label = order?.folio || `Referencia …${ref.public_reference.slice(-6)}`;
  const checkedAt = tracking.checkedAt[ref.public_reference];
  const phone = branchPhone?.replace(/\D/g, '');
  const icons = [Check, ChefHat, order?.service_type === 'delivery' ? Bike : ShoppingBag, PackageCheck];
  return (
    <section className={`order-tracker${view?.exception ? ' order-tracker--exception' : ''}`}
      aria-label="Seguimiento de tu pedido">
      <div className="order-tracker__header">
        <div>
          <span className="order-tracker__eyebrow">TU PEDIDO · {order?.branch_name || 'KIWI'}</span>
          <strong>{label}</strong>
        </div>
        {!onlyReference && <button type="button" aria-label="Ocultar seguimiento en este navegador"
          className="order-tracker__icon-button" onClick={() => tracking.dismiss(ref.public_reference)}><X size={18} /></button>}
      </div>
      {!onlyReference && tracking.references.length > 1 && (
        <label className="order-tracker__picker">Tus pedidos
          <select value={ref.public_reference} onChange={event => tracking.select(event.target.value)}>
            {tracking.references.map(item => <option key={item.public_reference} value={item.public_reference}>
              {tracking.states[item.public_reference]?.folio || `Referencia …${item.public_reference.slice(-6)}`}
            </option>)}
          </select>
        </label>
      )}
      <div className="order-tracker__status" role="status" aria-live="polite">
        <Clock size={18} aria-hidden="true" />
        <div><h3>{view?.title || (error ? 'Seguimiento no disponible' : 'Consultando tu solicitud')}</h3>
          <p>{view?.description || (error ? 'Reintentaremos la consulta automáticamente.' : 'Esperamos la respuesta de la sucursal.')}</p></div>
      </div>
      {view && <ol className="order-tracker__steps" aria-label="Etapas del pedido">
        {view.steps.map((step, index) => {
          const Icon = icons[index];
          return <li key={step} className={view.step >= index ? 'is-reached' : ''}
            aria-current={view.step === index ? 'step' : undefined}>
            <span className="order-tracker__node"><Icon size={18} aria-hidden="true" /></span>
            <span>{step}</span>
          </li>;
        })}
      </ol>}
      {error && <p className="order-tracker__error" role="alert">{error}</p>}
      {checkedAt && <p className="order-tracker__freshness">Última consulta: {new Date(checkedAt).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}</p>}
      {!tracking.storageAvailable && <p className="order-tracker__error">El seguimiento está disponible en esta pantalla. El navegador no pudo guardarlo para una recarga.</p>}
      {order && <>
        <button type="button" className="order-tracker__details-toggle" aria-expanded={expanded}
          aria-controls={id} onClick={() => setExpanded(value => !value)}>
          <span>{expanded ? 'Ocultar detalle' : 'Ver detalle'} · {formatMoney(order.total_cents)}</span>
          <ChevronDown size={16} className={expanded ? 'is-expanded' : ''} />
        </button>
        {expanded && <div className="order-tracker__details" id={id}>
          <dl><div><dt>Modalidad</dt><dd>{order.service_type === 'delivery' ? 'A domicilio' : order.service_type === 'dine-in' ? 'En sucursal' : 'Para recoger'}</dd></div>
            <div><dt>Actualización de la sucursal</dt><dd>{new Date(order.updated_at).toLocaleString('es-MX')}</dd></div></dl>
          {phone && /^\d{10,15}$/.test(phone) && <a href={`https://wa.me/${phone}?text=${encodeURIComponent(`Hola, quiero consultar mi pedido ${order.folio || 'web'}.`)}`}
            target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Contactar a la sucursal</a>}
        </div>}
      </>}
    </section>
  );
}
