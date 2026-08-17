import React from 'react';
import { Category } from '../types';

interface CategoryStoriesProps {
  categories: Category[];
  activeCategoryId: string;
  onSelectCategory: (categoryId: string) => void;
}

const CATEGORY_EMOJIS: Record<string, string> = {
  'all': '✨',
  'Todos': '✨',
  'Jugos y Extractos': '🥤',
  'Smoothies y Licuados': '🍓',
  'Café y Matcha': '🍵',
  'Ensaladas': '🥗',
  'Emparedados y Sandos': '🥪',
  'Panadería': '🥐',
  'Frutas': '🥑',
  'Combos': '🍱',
  'Aguas y Bebidas': '💧',
};

export const CategoryStories: React.FC<CategoryStoriesProps> = ({
  categories,
  activeCategoryId,
  onSelectCategory,
}) => {
  return (
    <div className="category-stories" role="tablist">
      {categories.map((cat) => {
        const isActive = activeCategoryId === cat.id || (activeCategoryId === '' && cat.id === 'all');
        const emoji = CATEGORY_EMOJIS[cat.name] || '🥝';

        return (
          <button
            key={cat.id}
            type="button"
            className={`category-story-item ${isActive ? 'active' : ''}`}
            onClick={() => onSelectCategory(cat.id)}
            role="tab"
            aria-selected={isActive}
          >
            <div className="story-ring">
              <div className="story-circle">
                <span>{emoji}</span>
              </div>
            </div>
            <span className="story-label">{cat.name}</span>
          </button>
        );
      })}
    </div>
  );
};
