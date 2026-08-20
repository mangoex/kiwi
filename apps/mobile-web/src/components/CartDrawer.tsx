import React, { useState } from 'react';
import { X, Plus, Minus, Trash2, Banknote, CreditCard, ArrowRightLeft, Send, ShoppingBag, MapPin, User, Phone, CheckCircle2 } from 'lucide-react';
import { CartItem, CustomerOrderInfo, OrderType, PaymentMethod } from '../types';
import { formatMoney } from '../api';
import { getProductIconMeta } from '../imageMap';

interface CartDrawerProps {
  items: CartItem[];
  orderType: OrderType;
  onClose: () => void;
  onUpdateQuantity: (cartId: string, delta: number) => void;
  onRemoveItem: (cartId: string) => void;
  onSubmitOrder: (info: CustomerOrderInfo) => void;
  isSubmitting: boolean;
}

export const CartDrawer: React.FC<CartDrawerProps> = ({
  items,
  orderType: initialOrderType,
  onClose,
  onUpdateQuantity,
  onRemoveItem,
  onSubmitOrder,
  isSubmitting,
}) => {
  const [orderType, setOrderType] = useState<OrderType>(initialOrderType);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [street, setStreet] = useState('');
  const [number, setNumber] = useState('');
  const [neighborhood, setNeighborhood] = useState('');
  const [addressNotes, setAddressNotes] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash');
  const [cashAmount, setCashAmount] = useState('');
  const [orderNotes, setOrderNotes] = useState('');
  const [formError, setFormError] = useState('');

  const totalCents = items.reduce((acc, item) => acc + item.line_total_cents, 0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    if (!name.trim()) {
      setFormError('Por favor ingresa tu nombre completo.');
      return;
    }
    if (!phone.trim() || phone.trim().length < 8) {
      setFormError('Por favor ingresa un número de teléfono celular válido (WhatsApp).');
      return;
    }
    if (orderType === 'delivery') {
      if (!street.trim() || !number.trim() || !neighborhood.trim()) {
        setFormError('Para entrega a domicilio, ingresa calle, número y colonia.');
        return;
      }
    }

    const orderInfo: CustomerOrderInfo = {
      name: name.trim(),
      phone: phone.trim(),
      order_type: orderType,
      address_street: street.trim(),
      address_number: number.trim(),
      address_neighborhood: neighborhood.trim(),
      address_notes: addressNotes.trim(),
      payment_method: paymentMethod,
      cash_amount: paymentMethod === 'cash' ? cashAmount.trim() : undefined,
      order_notes: orderNotes.trim(),
    };

    onSubmitOrder(orderInfo);
  };

  return (
    <div className="product-modal-backdrop" onClick={onClose}>
      <div
        className="product-modal-bottom-sheet cart-drawer-sheet"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Carrito de compras"
      >
        <div className="cart-drawer-header">
          <div>
            <h2 className="cart-drawer-title">Tu Pedido</h2>
            <span className="cart-drawer-subtitle">
              {items.length} {items.length === 1 ? 'producto seleccionado' : 'productos seleccionados'}
            </span>
          </div>
          <button
            type="button"
            className="cart-drawer-close-btn"
            onClick={onClose}
            aria-label="Cerrar carrito"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="cart-drawer-form-body">
          {items.length === 0 ? (
            <div className="cart-empty-view">
              <div className="cart-empty-icon-circle">
                <ShoppingBag size={32} />
              </div>
              <h3>Tu comanda está vacía</h3>
              <p>Agrega deliciosos jugos, platillos o bowls desde el menú.</p>
              <button type="button" className="btn-cart-back-menu" onClick={onClose}>
                Explorar el Menú
              </button>
            </div>
          ) : (
            <>
              {/* Cart items list */}
              <section className="cart-items-modern-list" aria-label="Platillos en el carrito">
                {items.map((item) => {
                  const iconMeta = getProductIconMeta(item.product);
                  return (
                    <div key={item.cart_id} className="cart-item-modern-card">
                      <div
                        className="cart-item-thumbnail-avatar"
                        style={{
                          background: iconMeta.bgGradient,
                          borderColor: iconMeta.borderColor,
                        }}
                      >
                        <span className="cart-item-thumbnail-emoji">{iconMeta.emoji}</span>
                      </div>

                      <div className="cart-item-details">
                        <span className="cart-item-name">{item.product.name}</span>
                        <span className="cart-item-price-tag">
                          {formatMoney(item.line_total_cents)}
                        </span>
                        {item.notes && (
                          <span className="cart-item-notes-text">
                            📝 {item.notes}
                          </span>
                        )}
                      </div>

                      <div className="cart-item-actions-cluster">
                        <div className="cart-item-stepper">
                          <button
                            type="button"
                            className="cart-stepper-btn"
                            onClick={() => onUpdateQuantity(item.cart_id, -1)}
                            aria-label="Disminuir cantidad"
                          >
                            <Minus size={13} />
                          </button>
                          <span className="cart-stepper-count">{item.quantity}</span>
                          <button
                            type="button"
                            className="cart-stepper-btn"
                            onClick={() => onUpdateQuantity(item.cart_id, 1)}
                            aria-label="Aumentar cantidad"
                          >
                            <Plus size={13} />
                          </button>
                        </div>

                        <button
                          type="button"
                          className="cart-item-delete-btn"
                          onClick={() => onRemoveItem(item.cart_id)}
                          aria-label={`Eliminar ${item.product.name}`}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </section>

              {/* Order Mode selector */}
              <div className="cart-form-section">
                <label className="cart-form-section-label">Modalidad de entrega</label>
                <div className="cart-order-type-switch">
                  <button
                    type="button"
                    className={`cart-type-switch-btn ${orderType === 'takeaway' ? 'active' : ''}`}
                    onClick={() => setOrderType('takeaway')}
                  >
                    🏃 Para Recoger
                  </button>
                  <button
                    type="button"
                    className={`cart-type-switch-btn ${orderType === 'delivery' ? 'active' : ''}`}
                    onClick={() => setOrderType('delivery')}
                  >
                    🛵 Envío a Domicilio
                  </button>
                </div>
              </div>

              {/* Customer Info */}
              <div className="cart-form-section">
                <label className="cart-form-section-label">Tus Datos de Contacto</label>
                <div className="cart-form-fields-grid">
                  <div className="cart-input-wrapper">
                    <User size={16} className="cart-input-icon" />
                    <input
                      type="text"
                      className="cart-input-field"
                      placeholder="Tu nombre completo *"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                    />
                  </div>

                  <div className="cart-input-wrapper">
                    <Phone size={16} className="cart-input-icon" />
                    <input
                      type="tel"
                      className="cart-input-field"
                      placeholder="Teléfono Celular (WhatsApp) *"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>

              {/* Delivery Address if delivery mode */}
              {orderType === 'delivery' && (
                <div className="cart-form-section">
                  <label className="cart-form-section-label">Dirección de Entrega</label>
                  <div className="cart-form-fields-grid">
                    <div className="cart-input-wrapper">
                      <MapPin size={16} className="cart-input-icon" />
                      <input
                        type="text"
                        className="cart-input-field"
                        placeholder="Calle *"
                        value={street}
                        onChange={(e) => setStreet(e.target.value)}
                        required
                      />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '8px' }}>
                      <input
                        type="text"
                        className="cart-input-field no-icon"
                        placeholder="No. Ext / Int *"
                        value={number}
                        onChange={(e) => setNumber(e.target.value)}
                        required
                      />
                      <input
                        type="text"
                        className="cart-input-field no-icon"
                        placeholder="Colonia *"
                        value={neighborhood}
                        onChange={(e) => setNeighborhood(e.target.value)}
                        required
                      />
                    </div>

                    <input
                      type="text"
                      className="cart-input-field no-icon"
                      placeholder="Referencias de entrega (ej: Portón café, timbre blanco)"
                      value={addressNotes}
                      onChange={(e) => setAddressNotes(e.target.value)}
                    />
                  </div>
                </div>
              )}

              {/* Payment Methods */}
              <div className="cart-form-section">
                <label className="cart-form-section-label">Forma de Pago</label>
                <div className="cart-payment-methods-grid">
                  <button
                    type="button"
                    className={`cart-payment-method-pill ${paymentMethod === 'cash' ? 'active' : ''}`}
                    onClick={() => setPaymentMethod('cash')}
                  >
                    <Banknote size={18} />
                    <span>Efectivo</span>
                  </button>

                  <button
                    type="button"
                    className={`cart-payment-method-pill ${paymentMethod === 'card' ? 'active' : ''}`}
                    onClick={() => setPaymentMethod('card')}
                  >
                    <CreditCard size={18} />
                    <span>Tarjeta (Terminal)</span>
                  </button>

                  <button
                    type="button"
                    className={`cart-payment-method-pill ${paymentMethod === 'transfer' ? 'active' : ''}`}
                    onClick={() => setPaymentMethod('transfer')}
                  >
                    <ArrowRightLeft size={18} />
                    <span>Transferencia</span>
                  </button>
                </div>

                {paymentMethod === 'cash' && (
                  <div style={{ marginTop: '10px' }}>
                    <input
                      type="text"
                      className="cart-input-field no-icon"
                      placeholder="¿Con cuánto vas a pagar? (Para llevar cambio)"
                      value={cashAmount}
                      onChange={(e) => setCashAmount(e.target.value)}
                    />
                  </div>
                )}
              </div>

              {/* Order Notes */}
              <div className="cart-form-section">
                <label className="cart-form-section-label">Comentarios o Indicaciones del Pedido</label>
                <textarea
                  className="cart-input-field no-icon"
                  rows={2}
                  placeholder="Instrucciones generales para el restaurante..."
                  value={orderNotes}
                  onChange={(e) => setOrderNotes(e.target.value)}
                />
              </div>

              {formError && (
                <div className="cart-form-error-alert" role="alert">
                  {formError}
                </div>
              )}

              {/* Financial summary breakdown */}
              <div className="cart-financial-summary-card">
                <div className="cart-summary-line">
                  <span>Subtotal de productos</span>
                  <span>{formatMoney(totalCents)}</span>
                </div>
                <div className="cart-summary-line">
                  <span>Costo de envío</span>
                  <span style={{ color: '#16a34a', fontWeight: 700 }}>
                    {orderType === 'takeaway' ? 'No aplica' : 'Gratis'}
                  </span>
                </div>
                <div className="cart-summary-total-line">
                  <strong>Total a Pagar</strong>
                  <strong className="cart-total-value">{formatMoney(totalCents)}</strong>
                </div>
              </div>

              <div className="cart-submit-sticky-bar">
                <button
                  type="submit"
                  className="btn-cart-submit-order"
                  disabled={isSubmitting || items.length === 0}
                >
                  <Send size={18} />
                  <span>
                    {isSubmitting ? 'Enviando comanda…' : `Enviar Pedido por WhatsApp • ${formatMoney(totalCents)}`}
                  </span>
                </button>
              </div>
            </>
          )}
        </form>
      </div>
    </div>
  );
};
