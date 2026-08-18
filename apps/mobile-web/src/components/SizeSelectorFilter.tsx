import React from 'react';

interface SizeSelectorFilterProps {
  availableSizes: string[];
  activeSize: string;
  onSelectSize: (size: string) => void;
}

export const SizeSelectorFilter: React.FC<SizeSelectorFilterProps> = ({
  availableSizes,
  activeSize,
  onSelectSize,
}) => {
  if (availableSizes.length <= 1) return null;

  return (
    <div className="size-filter-bar" role="group" aria-label="Filtrar por tamaño">
      <span className="size-filter-label">Tamaño:</span>
      <div className="size-pills-container">
        <button
          type="button"
          className={`size-pill ${activeSize === 'all' ? 'active' : ''}`}
          onClick={() => onSelectSize('all')}
        >
          Todos
        </button>
        {availableSizes.map((size) => (
          <button
            key={size}
            type="button"
            className={`size-pill ${activeSize === size ? 'active' : ''}`}
            onClick={() => onSelectSize(size)}
          >
            {size}
          </button>
        ))}
      </div>
    </div>
  );
};
