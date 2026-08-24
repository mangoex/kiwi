import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Category } from '../types';
import { getCategoryCover, getCategoryIcon } from '../imageMap';
import { Sparkles, ChevronLeft, ChevronRight } from 'lucide-react';

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
  const carouselRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);

  // Sync active index when activeCategoryId changes
  useEffect(() => {
    const idx = categories.findIndex((c) => c.id === activeCategoryId);
    if (idx !== -1) {
      setActiveIndex(idx);
    }
  }, [activeCategoryId, categories]);

  // Handle scroll to calculate visible card index
  const handleScroll = useCallback(() => {
    const el = carouselRef.current;
    if (!el || categories.length === 0) return;
    const scrollLeft = el.scrollLeft;
    const itemWidth = el.scrollWidth / categories.length;
    const newIdx = Math.min(
      categories.length - 1,
      Math.max(0, Math.round(scrollLeft / itemWidth))
    );
    setActiveIndex(newIdx);
  }, [categories.length]);

  const scrollToCategoryIndex = (index: number) => {
    const el = carouselRef.current;
    if (!el) return;
    const cards = el.querySelectorAll<HTMLElement>('.category-hero-card');
    if (cards[index]) {
      cards[index].scrollIntoView({
        behavior: 'smooth',
        inline: 'center',
        block: 'nearest',
      });
    }
    setActiveIndex(index);
    if (categories[index]) {
      onSelectCategory(categories[index].id);
    }
  };

  const handleScrollLeft = () => {
    scrollToCategoryIndex(Math.max(0, activeIndex - 1));
  };

  const handleScrollRight = () => {
    scrollToCategoryIndex(Math.min(categories.length - 1, activeIndex + 1));
  };

  return (
    <section className="category-carousel-section" aria-label="Menú de categorías">
      <div className="section-header-compact">
        <div className="section-header-title-group">
          <span className="section-eyebrow">Explora nuestro menú</span>
          <h2 className="section-main-heading">Categorías</h2>
        </div>
        <div className="section-header-nav-hints">
          <span className="section-slide-hint">Desliza para ver más</span>
          <div className="category-nav-arrows">
            <button
              type="button"
              className="category-nav-arrow-btn"
              onClick={handleScrollLeft}
              disabled={activeIndex === 0}
              aria-label="Categoría anterior"
            >
              <ChevronLeft size={15} />
            </button>
            <button
              type="button"
              className="category-nav-arrow-btn"
              onClick={handleScrollRight}
              disabled={activeIndex === categories.length - 1}
              aria-label="Siguiente categoría"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      </div>

      <div
        ref={carouselRef}
        className="category-stories-carousel"
        role="tablist"
        aria-label="Categorías de productos"
        onScroll={handleScroll}
      >
        {categories.map((cat, idx) => {
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
              onClick={() => {
                onSelectCategory(cat.id);
                scrollToCategoryIndex(idx);
              }}
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
                    <Sparkles size={40} className="category-hero-sparkle-icon" />
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

      {/* Indicador de movimiento horizontal / pills de navegación */}
      <div className="category-scroll-indicator-wrap" aria-label="Indicador de posición horizontal">
        <div className="category-scroll-indicator-track">
          {categories.map((cat, idx) => {
            const isDotActive = activeIndex === idx;
            return (
              <button
                key={`dot-${cat.id}`}
                type="button"
                className={`category-indicator-pill ${isDotActive ? 'active' : ''}`}
                onClick={() => scrollToCategoryIndex(idx)}
                aria-label={`Ir a categoría ${cat.name}`}
                title={cat.name}
              />
            );
          })}
        </div>
      </div>
    </section>
  );
};
