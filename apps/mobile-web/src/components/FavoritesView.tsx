import React from 'react';
import { Heart, Compass } from 'lucide-react';
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
      <div className="favorites-empty-container">
        <div className="favorites-empty-icon-circle">
          <Heart size={32} />
        </div>
        <h2 className="favorites-empty-title">Aún no tienes favoritos</h2>
        <p className="favorites-empty-desc">
          Toca el icono de corazón en cualquier platillo para guardarlo aquí y pedirlo más rápido.
        </p>
        <button
          type="button"
          className="btn-favorites-explore"
          onClick={onExploreMenu}
        >
          <Compass size={18} />
          <span>Explorar el Menú</span>
        </button>
      </div>
    );
  }

  return (
    <div className="feed-container">
      <div className="section-title-bar">
        <h2>Tus Favoritos ❤️</h2>
        <span className="section-count-badge">{favoriteProducts.length} platillos</span>
      </div>

      <div className="product-items-grid">
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
    </div>
  );
};
