import React from 'react';
import { Search, X, Bike, ShoppingBag, Utensils, MapPin, ChevronDown } from 'lucide-react';
import { OrderType, BranchInfo } from '../types';

interface HeaderProps {
  orderType: OrderType;
  onToggleOrderType: (type: OrderType) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  selectedBranch: BranchInfo | null;
  onOpenBranchSelector: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  orderType,
  onToggleOrderType,
  searchQuery,
  onSearchChange,
  selectedBranch,
  onOpenBranchSelector,
}) => {
  const distanceText = selectedBranch?.distance_km !== undefined && selectedBranch?.distance_km !== null
    ? (selectedBranch.distance_km < 0.1
        ? 'Estás aquí'
        : selectedBranch.distance_km < 1
        ? `${Math.round(selectedBranch.distance_km * 1000)}m`
        : `${selectedBranch.distance_km}km`)
    : null;

  return (
    <header className="mobile-app-header">
      {/* Branch location selector banner */}
      <div
        onClick={onOpenBranchSelector}
        className="flex items-center justify-between px-3 py-1.5 bg-emerald-50 active:bg-emerald-100 border-b border-emerald-100 cursor-pointer text-xs transition-colors"
      >
        <div className="flex items-center gap-1.5 overflow-hidden text-emerald-900">
          <MapPin size={13} className="text-emerald-600 shrink-0" />
          <span className="font-bold truncate">
            {selectedBranch ? selectedBranch.name : 'Elige tu sucursal'}
          </span>
          {distanceText && (
            <span className="text-[11px] bg-emerald-200/80 text-emerald-800 px-1.5 py-0.2 rounded-full font-medium shrink-0">
              {distanceText}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 text-emerald-700 font-semibold text-[11px] shrink-0 ml-1">
          <span>Cambiar</span>
          <ChevronDown size={12} />
        </div>
      </div>

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
            className={`mobile-order-type-pill ${orderType === 'dine-in' ? 'active' : ''}`}
            onClick={() => onToggleOrderType('dine-in')}
            role="tab"
            aria-selected={orderType === 'dine-in'}
            title="Comer aquí en barra"
          >
            <Utensils size={13} />
            <span>Comer aquí</span>
          </button>

          <button
            type="button"
            className={`mobile-order-type-pill ${orderType === 'takeaway' ? 'active' : ''}`}
            onClick={() => onToggleOrderType('takeaway')}
            role="tab"
            aria-selected={orderType === 'takeaway'}
            title="Para llevar"
          >
            <ShoppingBag size={13} />
            <span>Llevar</span>
          </button>

          <button
            type="button"
            className={`mobile-order-type-pill ${orderType === 'delivery' ? 'active' : ''}`}
            onClick={() => onToggleOrderType('delivery')}
            role="tab"
            aria-selected={orderType === 'delivery'}
            title="Envío a domicilio"
          >
            <Bike size={13} />
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
