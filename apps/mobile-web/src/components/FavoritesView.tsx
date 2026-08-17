import React from 'react';
import { Heart } from 'lucide-react';
import { Product } from '../types';
import { ProductCard } from './ProductCard';

interface FavoritesViewProps {
  favoriteProducts: Product[];
  likedProductIds: Set<string>;
  onToggleLike: (productId: string) => void;
  onOpenDetail: (product: Product) => void;
  onQuickAdd: (product: Product) => void;
  onExploreMenu: () => void;
}

export const FavoritesView: React.FC<FavoritesViewProps> = ({
  favoriteProducts,
  likedProductIds,
  onToggleLike,
  onOpenDetail,
  onQuickAdd,
  onExploreMenu,
}) => {
  if (favoriteProducts.length === 0) {
    return (
      <div style={{ padding: '60px 20px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
        <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: '#fee2e2', color: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Heart size={32} />
        </div>
        <h2 style={{ fontSize: '18px', fontWeight: 800 }}>Aún no tienes favoritos</h2>
        <p style={{ fontSize: '14px', color: '#64748b', maxWidth: '280px', lineHeight: 1.4 }}>
          Toca el corazón o haz doble toque en cualquier platillo del menú para guardarlo aquí.
        </p>
        <button
          type="button"
          className="btn-add-main"
          style={{ width: 'auto', padding: '10px 24px' }}
          onClick={onExploreMenu}
        >
          Explorar el Menú
        </button>
      </div>
    );
  }

  return (
    <div className="feed-container">
      <div className="section-title-bar">
        <h2>Tus Favoritos ❤️</h2>
        <span>{favoriteProducts.length} platillos</span>
      </div>

      {favoriteProducts.map((product) => (
        <ProductCard
          key={product.id}
          product={product}
          isLiked={likedProductIds.has(product.id)}
          onToggleLike={onToggleLike}
          onOpenDetail={onOpenDetail}
          onQuickAdd={onQuickAdd}
        />
      ))}
    </div>
  );
};
