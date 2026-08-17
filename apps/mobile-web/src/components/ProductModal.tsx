import React, { useState } from 'react';
import { X, Heart, Plus, Minus, ShoppingBag } from 'lucide-react';
import { Product } from '../types';
import { formatMoney } from '../api';

interface ProductModalProps {
  product: Product;
  isLiked: boolean;
  onToggleLike: (productId: string) => void;
  onClose: () => void;
  onAddToCart: (product: Product, quantity: number, notes?: string) => void;
}

export const ProductModal: React.FC<ProductModalProps> = ({
  product,
  isLiked,
  onToggleLike,
  onClose,
  onAddToCart,
}) => {
  const [quantity, setQuantity] = useState(1);
  const [notes, setNotes] = useState('');

  const totalCents = product.price_cents * quantity;

  const handleAdd = () => {
    onAddToCart(product, quantity, notes.trim() || undefined);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-sheet" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header-image">
          <img src={product.image_url} alt={product.name} className="modal-img" />

          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Cerrar">
            <X size={20} />
          </button>

          <button
            type="button"
            className={`btn-heart ${isLiked ? 'liked' : ''}`}
            style={{ position: 'absolute', bottom: '14px', right: '14px' }}
            onClick={() => onToggleLike(product.id)}
            aria-label={isLiked ? 'Quitar de favoritos' : 'Agregar a favoritos'}
          >
            <Heart
              size={20}
              fill={isLiked ? '#ef4444' : 'none'}
              color={isLiked ? '#ef4444' : 'currentColor'}
            />
          </button>
        </div>

        <div className="modal-body">
          <div className="modal-title-row">
            <div>
              <h2>{product.name}</h2>
              <span style={{ fontSize: '13px', color: '#64748b', fontWeight: 600 }}>
                {product.category_name}
              </span>
            </div>
            <span className="modal-price">{formatMoney(product.price_cents)}</span>
          </div>

          {product.description && (
            <p className="modal-desc">{product.description}</p>
          )}

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {product.calories && <span className="meta-chip">🔥 {product.calories}</span>}
            {product.prep_time && <span className="meta-chip">⏱ {product.prep_time}</span>}
            <span className="meta-chip">{product.station === 'cocina' ? '👩‍🍳 Preparado en Cocina' : '🍹 Preparado en Barra'}</span>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="item-notes">Instrucciones o notas especiales</label>
            <textarea
              id="item-notes"
              className="custom-notes-input"
              rows={2}
              placeholder="Ej: Sin popote, aderezo aparte, bien frío..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>

        <div className="modal-footer">
          <div className="quantity-picker">
            <button
              type="button"
              className="quantity-btn"
              onClick={() => setQuantity(Math.max(1, quantity - 1))}
              disabled={quantity <= 1}
              aria-label="Disminuir cantidad"
            >
              <Minus size={14} />
            </button>
            <span className="quantity-count">{quantity}</span>
            <button
              type="button"
              className="quantity-btn"
              onClick={() => setQuantity(quantity + 1)}
              aria-label="Aumentar cantidad"
            >
              <Plus size={14} />
            </button>
          </div>

          <button type="button" className="btn-add-main" onClick={handleAdd}>
            <ShoppingBag size={18} />
            <span>Agregar • {formatMoney(totalCents)}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
