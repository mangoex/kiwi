import React from 'react';
import { Category } from '../types';
import { getCategoryCover, getCategoryIcon } from '../imageMap';

interface CategoryStoriesProps {
  categories: Category[];
  activeCategoryId: string;
  onSelectCategory: (categoryId: string) => void;
}

export const CategoryStories: React.FC<CategoryStoriesProps> = ({
  categories,
  activeCategoryId,
  onSelectCategory,
}) => {
  return (
    <div className="category-carousel-section">
      <div className="category-stories" role="tablist" aria-label="Categorías de productos">
        {categories.map((cat) => {
          const isAll = cat.id === 'all' || cat.name === 'Todos';
          const isActive = activeCategoryId === cat.id || (activeCategoryId === '' && isAll);
          const cover = getCategoryCover(cat.name);
          const icon = getCategoryIcon(cat.name);

          return (
            <button
              key={cat.id}
              type="button"
              className={`category-card-pill ${isActive ? 'active' : ''}`}
              onClick={() => onSelectCategory(cat.id)}
              role="tab"
              aria-selected={isActive}
            >
              <div className="category-thumb-wrapper">
                {!isAll ? (
                  <img src={cover} alt={cat.name} className="category-thumb-img" loading="lazy" />
                ) : (
                  <div className="category-thumb-all">✨</div>
                )}
                <span className="category-mini-icon">{icon}</span>
              </div>
              <span className="category-card-name">{cat.name}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
