import React from 'react';
import { Search, X } from 'lucide-react';
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
    <header className="app-header">
      <div className="header-top">
        <div className="brand-badge">
          <div className="brand-logo-icon">🥝</div>
          <div className="brand-info">
            <h1>Kiwi</h1>
            <span>Food & Drinks</span>
          </div>
        </div>

        <div className="header-actions">
          <div className="order-type-toggle" role="tablist">
            <button
              type="button"
              className={`order-type-btn ${orderType === 'takeaway' ? 'active' : ''}`}
              onClick={() => onToggleOrderType('takeaway')}
            >
              Recoger
            </button>
            <button
              type="button"
              className={`order-type-btn ${orderType === 'delivery' ? 'active' : ''}`}
              onClick={() => onToggleOrderType('delivery')}
            >
              Domicilio
            </button>
          </div>
        </div>
      </div>

      <div className="search-container">
        <Search size={16} className="search-icon" />
        <input
          type="text"
          className="search-input"
          placeholder="Buscar jugos, matcha, sandos, ensaladas…"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
        {searchQuery.trim().length > 0 && (
          <button
            type="button"
            className="search-clear"
            onClick={() => onSearchChange('')}
            aria-label="Limpiar búsqueda"
          >
            <X size={12} />
          </button>
        )}
      </div>
    </header>
  );
};
