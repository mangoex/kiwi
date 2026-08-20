import React from 'react';
import { ShoppingBag, ArrowRight } from 'lucide-react';
import { formatMoney } from '../api';

interface FloatingCartBarProps {
  totalCount: number;
  totalCents: number;
  onOpenCart: () => void;
}

export const FloatingCartBar: React.FC<FloatingCartBarProps> = ({
  totalCount,
  totalCents,
  onOpenCart,
}) => {
  if (totalCount === 0) return null;

  return (
    <div className="mobile-floating-cart-anchor">
      <button
        type="button"
        className="mobile-floating-cart-banner"
        onClick={onOpenCart}
        aria-label="Abrir carrito de compras"
      >
        <div className="mobile-floating-cart-left">
          <div className="mobile-floating-cart-badge">{totalCount}</div>
          <div className="mobile-floating-cart-meta">
            <span className="mobile-floating-cart-label">Ver Pedido</span>
            <span className="mobile-floating-cart-items-text">
              {totalCount} {totalCount === 1 ? 'producto' : 'productos'}
            </span>
          </div>
        </div>

        <div className="mobile-floating-cart-right">
          <span className="mobile-floating-cart-total-amount">
            {formatMoney(totalCents)}
          </span>
          <ArrowRight size={18} />
        </div>
      </button>
    </div>
  );
};
