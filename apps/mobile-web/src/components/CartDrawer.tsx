import React, { useState } from 'react';
import { X, Plus, Minus, Trash2, Banknote, CreditCard, ArrowRightLeft, Send } from 'lucide-react';
import { CartItem, CustomerOrderInfo, OrderType, PaymentMethod } from '../types';
import { formatMoney } from '../api';

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
      setFormError('Por favor ingresa un número de teléfono válido (WhatsApp).');
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
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-sheet" style={{ maxHeight: '94vh' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 800 }}>Mi Carrito</h2>
            <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>
              {items.length} producto{items.length !== 1 ? 's' : ''} seleccionado{items.length !== 1 ? 's' : ''}
            </span>
          </div>
          <button type="button" className="modal-close-btn" style={{ position: 'static', background: '#f1f5f9', color: '#0f172a' }} onClick={onClose} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ overflowY: 'auto', flex: 1, padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Cart Items List */}
          <section className="cart-items-list">
            {items.map((item) => (
              <div key={item.cart_id} className="cart-item-row">
                <img
                  src={item.product.image_url}
                  alt={item.product.name}
                  style={{ width: '48px', height: '48px', borderRadius: '8px', objectFit: 'cover', marginRight: '10px' }}
                />
                <div className="cart-item-info">
                  <span className="cart-item-name">{item.product.name}</span>
                  <span className="cart-item-price">{formatMoney(item.line_total_cents)}</span>
                  {item.notes && (
                    <span style={{ fontSize: '11px', color: '#64748b', fontStyle: 'italic' }}>
                      Nota: {item.notes}
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div className="quantity-picker" style={{ padding: '2px' }}>
                    <button
                      type="button"
                      className="quantity-btn"
                      style={{ width: '28px', height: '28px' }}
                      onClick={() => onUpdateQuantity(item.cart_id, -1)}
                      aria-label="Disminuir"
                    >
                      <Minus size={12} />
                    </button>
                    <span style={{ padding: '0 8px', fontSize: '13px', fontWeight: 800 }}>{item.quantity}</span>
                    <button
                      type="button"
                      className="quantity-btn"
                      style={{ width: '28px', height: '28px' }}
                      onClick={() => onUpdateQuantity(item.cart_id, 1)}
                      aria-label="Aumentar"
                    >
                      <Plus size={12} />
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => onRemoveItem(item.cart_id)}
                    style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
                    aria-label="Eliminar producto"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </section>

          {/* Delivery Mode Toggle */}
          <div className="form-group">
            <label className="form-label">Modalidad del Pedido</label>
            <div className="order-type-toggle" style={{ width: '100%' }}>
              <button
                type="button"
                className={`order-type-btn ${orderType === 'takeaway' ? 'active' : ''}`}
                style={{ flex: 1, textAlign: 'center', padding: '8px' }}
                onClick={() => setOrderType('takeaway')}
              >
                🏃 Recoger en Sucursal
              </button>
              <button
                type="button"
                className={`order-type-btn ${orderType === 'delivery' ? 'active' : ''}`}
                style={{ flex: 1, textAlign: 'center', padding: '8px' }}
                onClick={() => setOrderType('delivery')}
              >
                🛵 Envío a Domicilio
              </button>
            </div>
          </div>

          {/* Customer Info */}
          <div className="form-group">
            <label className="form-label" htmlFor="cust-name">Tu Nombre *</label>
            <input
              id="cust-name"
              type="text"
              className="form-input"
              placeholder="Ej. Sofia Ramos"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="cust-phone">Teléfono WhatsApp *</label>
            <input
              id="cust-phone"
              type="tel"
              className="form-input"
              placeholder="Ej. 55 1234 5678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
            />
          </div>

          {/* Address Fields for Delivery */}
          {orderType === 'delivery' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', background: '#f8fafc', padding: '14px', borderRadius: '14px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '13px', fontWeight: 800, color: '#0f172a' }}>📍 Datos de Entrega</span>

              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '8px' }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="addr-street">Calle *</label>
                  <input
                    id="addr-street"
                    type="text"
                    className="form-input"
                    placeholder="Av. Principal"
                    value={street}
                    onChange={(e) => setStreet(e.target.value)}
                    required={orderType === 'delivery'}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="addr-num">Número *</label>
                  <input
                    id="addr-num"
                    type="text"
                    className="form-input"
                    placeholder="123 Int 4B"
                    value={number}
                    onChange={(e) => setNumber(e.target.value)}
                    required={orderType === 'delivery'}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="addr-col">Colonia / Zona *</label>
                <input
                  id="addr-col"
                  type="text"
                  className="form-input"
                  placeholder="Col. Del Valle"
                  value={neighborhood}
                  onChange={(e) => setNeighborhood(e.target.value)}
                  required={orderType === 'delivery'}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="addr-notes">Referencias de entrega</label>
                <input
                  id="addr-notes"
                  type="text"
                  className="form-input"
                  placeholder="Ej. Portón blanco, timbre 2"
                  value={addressNotes}
                  onChange={(e) => setAddressNotes(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Payment Method */}
          <div className="form-group">
            <label className="form-label">Método de Pago</label>
            <div className="payment-methods-grid">
              <button
                type="button"
                className={`payment-method-btn ${paymentMethod === 'cash' ? 'selected' : ''}`}
                onClick={() => setPaymentMethod('cash')}
              >
                <Banknote size={20} />
                <span>Efectivo</span>
              </button>
              <button
                type="button"
                className={`payment-method-btn ${paymentMethod === 'card' ? 'selected' : ''}`}
                onClick={() => setPaymentMethod('card')}
              >
                <CreditCard size={20} />
                <span>Tarjeta</span>
              </button>
              <button
                type="button"
                className={`payment-method-btn ${paymentMethod === 'transfer' ? 'selected' : ''}`}
                onClick={() => setPaymentMethod('transfer')}
              >
                <ArrowRightLeft size={20} />
                <span>Transferencia</span>
              </button>
            </div>
          </div>

          {paymentMethod === 'cash' && (
            <div className="form-group">
              <label className="form-label" htmlFor="cash-amount">¿Con cuánto pagarás? (Opcional, para cambio)</label>
              <input
                id="cash-amount"
                type="text"
                className="form-input"
                placeholder="Ej. $200, $500"
                value={cashAmount}
                onChange={(e) => setCashAmount(e.target.value)}
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label" htmlFor="order-gen-notes">Instrucciones generales del pedido</label>
            <input
              id="order-gen-notes"
              type="text"
              className="form-input"
              placeholder="Ej. Llevar cubiertos biodegradables"
              value={orderNotes}
              onChange={(e) => setOrderNotes(e.target.value)}
            />
          </div>

          {formError && (
            <p style={{ color: '#ef4444', fontSize: '13px', fontWeight: 600 }}>
              ⚠️ {formError}
            </p>
          )}

          <div style={{ paddingTop: '8px', borderTop: '1px solid #f1f5f9' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <span style={{ fontSize: '16px', fontWeight: 800, color: '#0f172a' }}>Total a Pagar</span>
              <span style={{ fontSize: '20px', fontWeight: 800, color: '#10b981' }}>{formatMoney(totalCents)}</span>
            </div>

            <button
              type="submit"
              className="btn-add-main"
              style={{ width: '100%' }}
              disabled={isSubmitting}
            >
              <Send size={18} />
              <span>{isSubmitting ? 'Procesando pedido…' : `Confirmar y Enviar Pedido • ${formatMoney(totalCents)}`}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
