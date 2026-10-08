import React, { useRef, useEffect } from 'react';
import { Category } from '../types';
import { getCategoryIcon, getCategoryTheme } from '../imageMap';

interface CategoryCirclesProps {
  categories: Category[];
  activeCategoryId: string;
  onSelectCategory: (categoryId: string) => void;
  productsCountByCategory?: Record<string, number>;
}

export const CategoryCircles: React.FC<CategoryCirclesProps> = ({
  categories,
  activeCategoryId,
  onSelectCategory,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll the active circle into view smoothly
  useEffect(() => {
    if (!containerRef.current) return;
    const activeEl = containerRef.current.querySelector<HTMLElement>('.category-circle-btn.active');
    if (activeEl) {
      activeEl.scrollIntoView({
        behavior: 'smooth',
        inline: 'center',
        block: 'nearest',
      });
    }
  }, [activeCategoryId]);

  if (categories.length === 0) return null;

  return (
    <section className="category-circles-section" aria-label="Explorar por categoría">
      <div
        ref={containerRef}
        className="category-circles-scroll"
        role="tablist"
        aria-label="Categorías circulares"
      >
        {categories.map((cat) => {
          const isAll = cat.id === 'all' || cat.name === 'Todos';
          const isActive = activeCategoryId === cat.id || (activeCategoryId === '' && isAll);
          const icon = getCategoryIcon(cat.name);
          const theme = getCategoryTheme(cat.name);

          return (
            <button
              key={cat.id}
              type="button"
              className={`category-circle-btn ${isActive ? 'active' : ''}`}
              onClick={() => onSelectCategory(cat.id)}
              role="tab"
              aria-selected={isActive}
              aria-label={`Filtrar por ${cat.name}`}
            >
              <div
                className="category-circle-avatar"
                style={{
                  background: theme.bgGradient,
                  borderColor: isActive ? 'var(--accent-primary)' : theme.borderColor,
                  boxShadow: isActive
                    ? `0 6px 18px ${theme.glowColor}`
                    : '0 3px 8px rgba(15, 23, 42, 0.05)',
                }}
              >
                <span className="category-circle-emoji" role="img" aria-hidden="true">
                  {icon}
                </span>
              </div>
              <span
                className="category-circle-label"
                style={{
                  color: isActive ? theme.textColor : undefined,
                }}
              >
                {cat.name}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
};
