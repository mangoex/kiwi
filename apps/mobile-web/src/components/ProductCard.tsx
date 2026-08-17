import React, { useState } from 'react';
import { Heart, Plus } from 'lucide-react';
import { Product } from '../types';
import { formatMoney } from '../api';

interface ProductCardProps {
  product: Product;
  isLiked: boolean;
  onToggleLike: (productId: string) => void;
  onOpenDetail: (product: Product) => void;
  onQuickAdd: (product: Product) => void;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  isLiked,
  onToggleLike,
  onOpenDetail,
  onQuickAdd,
}) => {
  const [showHeartSplash, setShowHeartSplash] = useState(false);
  const [lastTap, setLastTap] = useState<number>(0);

  const handleImageTap = () => {
    const now = Date.now();
    const DOUBLE_TAP_DELAY = 300;
    if (now - lastTap < DOUBLE_TAP_DELAY) {
      // Double tap detected: Like with splash
      if (!isLiked) {
        onToggleLike(product.id);
      }
      setShowHeartSplash(true);
      setTimeout(() => setShowHeartSplash(false), 800);
    } else {
      // Single tap: open detail
      setTimeout(() => {
        // Only open if double tap didn't trigger
        if (Date.now() - now >= DOUBLE_TAP_DELAY) {
          onOpenDetail(product);
        }
      }, DOUBLE_TAP_DELAY);
    }
    setLastTap(now);
  };

  return (
    <article className="product-card">
      <div className="card-image-wrapper" onClick={handleImageTap}>
        <img
          src={product.image_url}
          alt={product.name}
          className="card-image"
          loading="lazy"
        />

        {/* Top Badges */}
        <div className="card-top-badges">
          {product.tags && product.tags[0] ? (
            <span className="badge-tag">{product.tags[0]}</span>
          ) : (
            <span className="badge-tag">Kiwi Fresh</span>
          )}
          {product.prep_time && (
            <span className="badge-prep">⏱ {product.prep_time}</span>
          )}
        </div>

        {/* Heart Splash on Double Tap */}
        {showHeartSplash && (
          <div className="heart-splash">
            <Heart size={80} fill="#ef4444" color="#ef4444" />
          </div>
        )}

        {/* Heart Like Button */}
        <button
          type="button"
          className={`btn-heart ${isLiked ? 'liked' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggleLike(product.id);
          }}
          aria-label={isLiked ? 'Quitar de favoritos' : 'Agregar a favoritos'}
        >
          <Heart
            size={20}
            fill={isLiked ? '#ef4444' : 'none'}
            color={isLiked ? '#ef4444' : 'currentColor'}
          />
        </button>
      </div>

      <div className="card-content" onClick={() => onOpenDetail(product)}>
        <div className="card-header-row">
          <h3>{product.name}</h3>
          <span className="card-price">{formatMoney(product.price_cents)}</span>
        </div>

        {product.description && (
          <p className="card-description">{product.description}</p>
        )}

        <div className="card-footer">
          <div className="card-meta-chips">
            {product.calories && (
              <span className="meta-chip">🔥 {product.calories}</span>
            )}
            <span className="meta-chip">{product.station === 'cocina' ? '👩‍🍳 Cocina' : '🍹 Barra'}</span>
          </div>

          <button
            type="button"
            className="btn-quick-add"
            onClick={(e) => {
              e.stopPropagation();
              onQuickAdd(product);
            }}
            aria-label={`Agregar ${product.name} al carrito`}
          >
            <Plus size={16} />
            <span>Agregar</span>
          </button>
        </div>
      </div>
    </article>
  );
};
