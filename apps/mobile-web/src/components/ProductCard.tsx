import React from 'react';
import { Heart, Plus } from 'lucide-react';
import { Product } from '../types';
import { formatMoney } from '../api';
import { getCategoryIcon, detectProductSize, cleanBaseProductName } from '../imageMap';

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
  const icon = getCategoryIcon(product.category_name || '');
  const size = detectProductSize(product.name);
  const displayName = cleanBaseProductName(product.name);

  return (
    <article className="product-item-card" onClick={() => onOpenDetail(product)}>
      {/* Icon Badge */}
      <div className="product-item-icon-box" aria-hidden="true">
        <span className="product-item-emoji">{icon}</span>
      </div>

      {/* Main Info */}
      <div className="product-item-info">
        <div className="product-item-title-row">
          <h3 className="product-item-title">{displayName}</h3>
          {size && <span className="product-item-size-badge">{size}</span>}
        </div>

        <div className="product-item-submeta">
          <span className="product-item-station">
            {product.station === 'cocina' ? '👩‍🍳 Cocina' : '🍹 Barra'}
          </span>
          {product.category_name && (
            <span className="product-item-cat">{product.category_name}</span>
          )}
        </div>

        <div className="product-item-bottom-row">
          <span className="product-item-price">{formatMoney(product.price_cents)}</span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="product-item-actions" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          className={`btn-item-like ${isLiked ? 'liked' : ''}`}
          onClick={() => onToggleLike(product.id)}
          aria-label={isLiked ? 'Quitar de favoritos' : 'Agregar a favoritos'}
        >
          <Heart
            size={18}
            fill={isLiked ? '#ef4444' : 'none'}
            color={isLiked ? '#ef4444' : '#94a3b8'}
          />
        </button>

        <button
          type="button"
          className="btn-item-add"
          onClick={() => onQuickAdd(product)}
          aria-label={`Agregar ${product.name} al pedido`}
        >
          <Plus size={18} />
        </button>
      </div>
    </article>
  );
};
