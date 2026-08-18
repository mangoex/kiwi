import React from 'react';
import { ShoppingBag, ArrowRight } from 'lucide-react';
import { formatMoney } from '../api';

interface FloatingCartBarProps {
  itemCount: number;
  totalCents: number;
  onOpenCart: () => void;
}

export const FloatingCartBar: React.FC<FloatingCartBarProps> = ({
  itemCount,
  totalCents,
  onOpenCart,
}) => {
  if (itemCount <= 0) return null;

  return (
    <div className="floating-cart-wrapper" onClick={onOpenCart} role="button" tabIndex={0}>
      <div className="floating-cart-bar">
        <div className="floating-cart-left">
          <div className="floating-cart-icon-box">
            <ShoppingBag size={20} />
            <span className="floating-cart-count">{itemCount}</span>
          </div>
          <div className="floating-cart-text">
            <span className="floating-cart-label">Tu Pedido</span>
            <span className="floating-cart-total">{formatMoney(totalCents)}</span>
          </div>
        </div>

        <div className="floating-cart-right">
          <span>Ver Carrito</span>
          <ArrowRight size={18} />
        </div>
      </div>
    </div>
  );
};
