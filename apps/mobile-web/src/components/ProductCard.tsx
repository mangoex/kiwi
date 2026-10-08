import React from 'react';
import { Heart, Plus, Flame } from 'lucide-react';
import { Product } from '../types';
import { formatMoney } from '../api';
import { getProductIconMeta, detectProductSize, cleanBaseProductName } from '../imageMap';

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
  const [imageError, setImageError] = React.useState(false);
  const size = detectProductSize(product.name);
  const displayName = cleanBaseProductName(product.name);
  const iconMeta = getProductIconMeta(product);
  const hasImage = Boolean(product.image_url && product.image_url.trim() && !imageError);

  return (
    <article
      className="product-card-modern"
      onClick={() => onOpenDetail(product)}
      tabIndex={0}
      role="button"
      aria-label={`Ver detalles de ${product.name}`}
    >
      <div
        className={`product-card-visual-wrapper ${hasImage ? 'product-card-has-photo' : 'product-card-icon-avatar'}`}
        style={
          hasImage
            ? undefined
            : {
                background: iconMeta.bgGradient,
                borderColor: iconMeta.borderColor,
              }
        }
      >
        {hasImage ? (
          <img
            src={product.image_url}
            alt={product.name}
            className="product-card-photo"
            onError={() => setImageError(true)}
            loading="lazy"
          />
        ) : (
          <span className="product-card-icon-emoji" role="img" aria-label={iconMeta.badgeLabel}>
            {iconMeta.emoji}
          </span>
        )}

        <span
          className={`product-card-icon-type-chip ${hasImage ? 'chip-on-photo' : ''}`}
          style={hasImage ? undefined : { color: iconMeta.textColor }}
        >
          {iconMeta.badgeLabel}
        </span>

        <button
          type="button"
          className={`product-card-like-btn ${isLiked ? 'liked' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggleLike(product.id);
          }}
          aria-label={isLiked ? 'Quitar de favoritos' : 'Agregar a favoritos'}
        >
          <Heart
            size={17}
            fill={isLiked ? '#ef4444' : 'none'}
            color={isLiked ? '#ef4444' : '#64748b'}
          />
        </button>

        {size && <span className="product-card-size-tag">{size}</span>}
      </div>

      <div className="product-card-body">
        <div className="product-card-meta-line">
          <span className="product-card-category-label">
            {product.category_name || 'Especialidad'}
          </span>
          {product.calories && (
            <span className="product-card-cal-badge">
              <Flame size={12} />
              <span>{product.calories}</span>
            </span>
          )}
        </div>

        <h3 className="product-card-name">{displayName}</h3>

        {product.description && (
          <p className="product-card-description-snippet">{product.description}</p>
        )}

        <div className="product-card-footer-row">
          <div className="product-card-price-group">
            <span className="product-card-price-amount">
              {formatMoney(product.price_cents)}
            </span>
          </div>

          <button
            type="button"
            className="product-card-add-action-btn"
            onClick={(e) => {
              e.stopPropagation();
              onQuickAdd(product);
            }}
            aria-label={`Agregar ${product.name} al pedido`}
          >
            <Plus size={18} strokeWidth={2.4} />
          </button>
        </div>
      </div>
    </article>
  );
};
