import React from 'react';
import { Compass, Heart, ShoppingBag } from 'lucide-react';

export type NavTab = 'explore' | 'favorites' | 'cart';

interface BottomNavProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  cartCount: number;
  favoritesCount: number;
}

export const BottomNav: React.FC<BottomNavProps> = ({
  currentTab,
  onSelectTab,
  cartCount,
  favoritesCount,
}) => {
  return (
    <nav className="bottom-nav" role="navigation" aria-label="Navegación principal">
      <button
        type="button"
        className={`nav-item ${currentTab === 'explore' ? 'active' : ''}`}
        onClick={() => onSelectTab('explore')}
      >
        <Compass size={22} />
        <span>Menú</span>
      </button>

      <button
        type="button"
        className={`nav-item ${currentTab === 'favorites' ? 'active' : ''}`}
        onClick={() => onSelectTab('favorites')}
      >
        <Heart size={22} fill={currentTab === 'favorites' ? 'currentColor' : 'none'} />
        <span>Favoritos</span>
        {favoritesCount > 0 && <span className="nav-item-badge">{favoritesCount}</span>}
      </button>

      <button
        type="button"
        className={`nav-item ${currentTab === 'cart' ? 'active' : ''}`}
        onClick={() => onSelectTab('cart')}
      >
        <ShoppingBag size={22} />
        <span>Carrito</span>
        {cartCount > 0 && <span className="nav-item-badge">{cartCount}</span>}
      </button>
    </nav>
  );
};
