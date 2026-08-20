import React from 'react';
import { Category } from '../types';
import { getCategoryCover, getCategoryIcon } from '../imageMap';
import { Sparkles } from 'lucide-react';

interface CategoryStoriesProps {
  categories: Category[];
  activeCategoryId: string;
  onSelectCategory: (categoryId: string) => void;
  productsCountByCategory?: Record<string, number>;
}

export const CategoryStories: React.FC<CategoryStoriesProps> = ({
  categories,
  activeCategoryId,
  onSelectCategory,
  productsCountByCategory = {},
}) => {
  return (
    <section className="category-carousel-section" aria-label="Menú de categorías">
      <div className="section-header-compact">
        <div className="section-header-title-group">
          <span className="section-eyebrow">Explora nuestro menú</span>
          <h2 className="section-main-heading">Categorías</h2>
        </div>
        <span className="section-slide-hint">Desliza para ver más →</span>
      </div>

      <div className="category-stories-carousel" role="tablist" aria-label="Categorías de productos">
        {categories.map((cat) => {
          const isAll = cat.id === 'all' || cat.name === 'Todos';
          const isActive = activeCategoryId === cat.id || (activeCategoryId === '' && isAll);
          const cover = getCategoryCover(cat.name);
          const icon = getCategoryIcon(cat.name);
          const count = productsCountByCategory[cat.id] || (isAll ? 'Todo' : '');

          return (
            <button
              key={cat.id}
              type="button"
              className={`category-hero-card ${isActive ? 'active' : ''}`}
              onClick={() => onSelectCategory(cat.id)}
              role="tab"
              aria-selected={isActive}
              aria-label={`Categoría ${cat.name}`}
            >
              <div className="category-hero-bg-wrapper">
                {!isAll ? (
                  <img
                    src={cover}
                    alt={cat.name}
                    className="category-hero-img"
                    loading="lazy"
                  />
                ) : (
                  <div className="category-hero-all-gradient">
                    <Sparkles size={36} className="category-hero-sparkle-icon" />
                  </div>
                )}
                <div className="category-hero-scrim" />
              </div>

              <div className="category-hero-content">
                <div className="category-hero-top-badge">
                  <span className="category-hero-icon-pill">{icon}</span>
                  {count && (
                    <span className="category-hero-count-chip">
                      {typeof count === 'number' ? `${count} platillos` : count}
                    </span>
                  )}
                </div>

                <div className="category-hero-bottom-info">
                  <span className="category-hero-title">{cat.name}</span>
                  <div className="category-hero-indicator-dot" />
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
};
