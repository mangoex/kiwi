import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import './CapsuleTabs.css';

export interface CapsuleTabItem<T extends string = string> {
  value: T;
  label: string;
}

interface CapsuleTabsProps<T extends string> {
  items: readonly CapsuleTabItem<T>[];
  value: T;
  onValueChange: (value: T) => void;
  ariaLabel: string;
  className?: string;
  idPrefix?: string;
  maxVisibleCount?: number;
}

export default function CapsuleTabs<T extends string>({
  items,
  value,
  onValueChange,
  ariaLabel,
  className,
  idPrefix = 'capsule-tabs',
}: CapsuleTabsProps<T>) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const tabRefs = useRef<Map<T, HTMLButtonElement>>(new Map());
  const [scrollState, setScrollState] = useState({ left: false, right: false });

  const updateScrollState = () => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    setScrollState({
      left: viewport.scrollLeft > 2,
      right: viewport.scrollLeft + viewport.clientWidth < viewport.scrollWidth - 2,
    });
  };

  useEffect(() => {
    updateScrollState();
    window.addEventListener('resize', updateScrollState);
    return () => window.removeEventListener('resize', updateScrollState);
  }, [items]);

  useEffect(() => {
    tabRefs.current.get(value)?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  }, [value]);

  const scrollTabs = (direction: -1 | 1) => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    viewport.scrollBy({ left: direction * Math.max(220, viewport.clientWidth * 0.7), behavior: 'smooth' });
  };

  const focusTab = (index: number) => {
    const nextItem = items[index];
    if (!nextItem) return;
    onValueChange(nextItem.value);
    window.requestAnimationFrame(() => tabRefs.current.get(nextItem.value)?.focus());
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % items.length;
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + items.length) % items.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = items.length - 1;
    if (nextIndex === null || items.length === 0) return;
    event.preventDefault();
    focusTab(nextIndex);
  };

  return (
    <div className={['capsule-tabs', className].filter(Boolean).join(' ')} aria-label={ariaLabel}>
      <div className="capsule-tabs__navigation">
        <button
          type="button"
          className="capsule-tabs__arrow"
          aria-label="Desplazar pestañas a la izquierda"
          disabled={!scrollState.left}
          onClick={() => scrollTabs(-1)}
        >
          <ChevronLeft aria-hidden="true" size={19} />
        </button>
        <div ref={viewportRef} className="capsule-tabs__viewport" onScroll={updateScrollState}>
          <div className="capsule-tabs__list" role="tablist" aria-label={ariaLabel}>
            {items.map((item, index) => {
              const isActive = item.value === value;
              return (
                <button
                  key={item.value}
                  ref={(node) => {
                    if (node) tabRefs.current.set(item.value, node);
                    else tabRefs.current.delete(item.value);
                  }}
                  id={`${idPrefix}-tab-${index}`}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  aria-controls={`${idPrefix}-panel-${index}`}
                  tabIndex={isActive ? 0 : -1}
                  className={`capsule-tabs__tab ${isActive ? 'is-active' : ''}`}
                  onClick={() => onValueChange(item.value)}
                  onKeyDown={(event) => handleKeyDown(event, index)}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
        <button
          type="button"
          className="capsule-tabs__arrow"
          aria-label="Desplazar pestañas a la derecha"
          disabled={!scrollState.right}
          onClick={() => scrollTabs(1)}
        >
          <ChevronRight aria-hidden="true" size={19} />
        </button>
      </div>
    </div>
  );
}
