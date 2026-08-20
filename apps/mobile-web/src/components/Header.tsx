import React from 'react';
import { Search, X, Bike, ShoppingBag } from 'lucide-react';
import { OrderType } from '../types';

interface HeaderProps {
  orderType: OrderType;
  onToggleOrderType: (type: OrderType) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  orderType,
  onToggleOrderType,
  searchQuery,
  onSearchChange,
}) => {
  return (
    <header className="mobile-app-header">
      <div className="mobile-header-top-row">
        <div className="mobile-brand-identity">
          <div className="mobile-brand-logo-badge">🥝</div>
          <div className="mobile-brand-text">
            <h1 className="mobile-brand-title">Kiwi</h1>
            <span className="mobile-brand-subtitle">Fresh Food & Drinks</span>
          </div>
        </div>

        <div className="mobile-order-type-capsule" role="tablist" aria-label="Modalidad de pedido">
          <button
            type="button"
            className={`mobile-order-type-pill ${orderType === 'takeaway' ? 'active' : ''}`}
            onClick={() => onToggleOrderType('takeaway')}
            role="tab"
            aria-selected={orderType === 'takeaway'}
          >
            <ShoppingBag size={14} />
            <span>Recoger</span>
          </button>

          <button
            type="button"
            className={`mobile-order-type-pill ${orderType === 'delivery' ? 'active' : ''}`}
            onClick={() => onToggleOrderType('delivery')}
            role="tab"
            aria-selected={orderType === 'delivery'}
          >
            <Bike size={14} />
            <span>Envío</span>
          </button>
        </div>
      </div>

      <div className="mobile-search-bar-wrapper">
        <Search size={18} className="mobile-search-icon" />
        <input
          type="search"
          className="mobile-search-input"
          placeholder="Buscar platillos, jugos, smoothies, bowls..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
        {searchQuery.trim().length > 0 && (
          <button
            type="button"
            className="mobile-search-clear-btn"
            onClick={() => onSearchChange('')}
            aria-label="Limpiar búsqueda"
          >
            <X size={14} />
          </button>
        )}
      </div>
    </header>
  );
};
