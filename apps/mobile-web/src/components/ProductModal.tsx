import React, { useState } from 'react';
import { X, Heart, Plus, Minus, ShoppingBag, Flame, Clock, ChefHat } from 'lucide-react';
import { Product } from '../types';
import { formatMoney } from '../api';
import { getProductImage } from '../imageMap';

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
  const [selectedQuickChoice, setSelectedQuickChoice] = useState('Regular');

  const totalCents = product.price_cents * quantity;
  const imageUrl = getProductImage(product);

  const handleAdd = () => {
    const combinedNotes = [
      selectedQuickChoice !== 'Regular' ? `Opción: ${selectedQuickChoice}` : '',
      notes.trim(),
    ].filter(Boolean).join(' · ');

    onAddToCart(product, quantity, combinedNotes || undefined);
    onClose();
  };

  return (
    <div className="product-modal-backdrop" onClick={onClose}>
      <div
        className="product-modal-bottom-sheet"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={product.name}
      >
        <div className="product-modal-hero-visual">
          <img src={imageUrl} alt={product.name} className="product-modal-hero-photo" />
          <div className="product-modal-hero-scrim" />

          <button
            type="button"
            className="product-modal-close-btn"
            onClick={onClose}
            aria-label="Cerrar modal"
          >
            <X size={20} />
          </button>

          <button
            type="button"
            className={`product-modal-fav-btn ${isLiked ? 'liked' : ''}`}
            onClick={() => onToggleLike(product.id)}
            aria-label={isLiked ? 'Quitar de favoritos' : 'Agregar a favoritos'}
          >
            <Heart
              size={20}
              fill={isLiked ? '#ef4444' : 'none'}
              color={isLiked ? '#ef4444' : '#ffffff'}
            />
          </button>
        </div>

        <div className="product-modal-content-body">
          <div className="product-modal-title-row">
            <div className="product-modal-title-left">
              <span className="product-modal-category-chip">
                {product.category_name || 'Especialidad'}
              </span>
              <h2 className="product-modal-name">{product.name}</h2>
            </div>
            <div className="product-modal-price-tag">
              {formatMoney(product.price_cents)}
            </div>
          </div>

          <div className="product-modal-badges-bar">
            {product.calories && (
              <span className="product-modal-meta-chip">
                <Flame size={14} className="chip-icon-flame" />
                <span>{product.calories}</span>
              </span>
            )}
            {product.prep_time && (
              <span className="product-modal-meta-chip">
                <Clock size={14} className="chip-icon-clock" />
                <span>{product.prep_time}</span>
              </span>
            )}
            <span className="product-modal-meta-chip">
              <ChefHat size={14} className="chip-icon-chef" />
              <span>{product.station === 'cocina' ? 'Cocina' : 'Barra'}</span>
            </span>
          </div>

          {product.description && (
            <div className="product-modal-section">
              <span className="product-modal-section-heading">Descripción</span>
              <p className="product-modal-description-text">{product.description}</p>
            </div>
          )}

          <div className="product-modal-section">
            <span className="product-modal-section-heading">Porción / Tamaño</span>
            <div className="product-modal-quick-choices-grid">
              {['Regular', 'Mediano', 'Grande'].map((choice) => (
                <button
                  key={choice}
                  type="button"
                  className={`product-modal-choice-pill ${selectedQuickChoice === choice ? 'active' : ''}`}
                  onClick={() => setSelectedQuickChoice(choice)}
                >
                  {choice}
                </button>
              ))}
            </div>
          </div>

          <div className="product-modal-section">
            <label className="product-modal-section-heading" htmlFor="modal-notes-input">
              Instrucciones Especiales
            </label>
            <textarea
              id="modal-notes-input"
              className="product-modal-notes-input"
              rows={2}
              placeholder="Ej: Sin cebolla, salsa aparte, bien frío, etc..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={200}
            />
          </div>
        </div>

        <div className="product-modal-sticky-footer">
          <div className="product-modal-quantity-stepper">
            <button
              type="button"
              className="product-modal-stepper-btn"
              onClick={() => setQuantity(Math.max(1, quantity - 1))}
              disabled={quantity <= 1}
              aria-label="Disminuir cantidad"
            >
              <Minus size={16} />
            </button>
            <span className="product-modal-stepper-count">{quantity}</span>
            <button
              type="button"
              className="product-modal-stepper-btn"
              onClick={() => setQuantity(Math.min(99, quantity + 1))}
              aria-label="Aumentar cantidad"
            >
              <Plus size={16} />
            </button>
          </div>

          <button
            type="button"
            className="product-modal-add-cart-btn"
            onClick={handleAdd}
          >
            <ShoppingBag size={19} />
            <span>Agregar • {formatMoney(totalCents)}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
