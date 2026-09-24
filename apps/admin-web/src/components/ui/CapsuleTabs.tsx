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

const getVisibleCount = (width: number, maximum: number, itemCount: number) => {
  if (itemCount === 0) return 1;
  if (width > 0 && width < 460) return Math.min(2, itemCount);
  if (width > 0 && width < 760) return Math.min(3, itemCount);
  return Math.min(maximum, itemCount);
};

export default function CapsuleTabs<T extends string>({
  items,
  value,
  onValueChange,
  ariaLabel,
  className,
  idPrefix = 'capsule-tabs',
  maxVisibleCount = 5,
}: CapsuleTabsProps<T>) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const tabRefs = useRef<Map<T, HTMLButtonElement>>(new Map());
  const [containerWidth, setContainerWidth] = useState(0);
  const [navigation, setNavigation] = useState({
    anchorValue: value,
    page: 0,
    visibleCount: 0,
  });

  const visibleCount = getVisibleCount(containerWidth, Math.max(1, maxVisibleCount), items.length);
  const totalPages = Math.max(1, Math.ceil(items.length / visibleCount));
  const activeIndex = Math.max(0, items.findIndex((item) => item.value === value));
  const activePage = Math.floor(activeIndex / visibleCount);
  const requestedPage = navigation.anchorValue === value && navigation.visibleCount === visibleCount
    ? navigation.page
    : activePage;
  const safePage = Math.min(requestedPage, totalPages - 1);
  const pageStart = safePage * visibleCount;
  const currentPageTabs = items.slice(pageStart, pageStart + visibleCount);
  const activeTabIsVisible = currentPageTabs.some((item) => item.value === value);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const updateWidth = () => setContainerWidth(container.getBoundingClientRect().width);
    updateWidth();

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateWidth);
      return () => window.removeEventListener('resize', updateWidth);
    }

    const observer = new ResizeObserver(updateWidth);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const selectTab = (item: CapsuleTabItem<T>, index: number) => {
    onValueChange(item.value);
    setNavigation({
      anchorValue: item.value,
      page: Math.floor(index / visibleCount),
      visibleCount,
    });
  };

  const focusTab = (index: number) => {
    const nextItem = items[index];
    if (!nextItem) return;

    selectTab(nextItem, index);
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

  const goToPage = (nextPage: number) => {
    setNavigation({
      anchorValue: value,
      page: Math.min(Math.max(nextPage, 0), totalPages - 1),
      visibleCount,
    });
  };

  return (
    <div
      ref={containerRef}
      className={['capsule-tabs', className].filter(Boolean).join(' ')}
      aria-label={ariaLabel}
    >
      {totalPages > 1 && (
        <div className="capsule-tabs__pagination" aria-label="Páginas de configuración">
          {Array.from({ length: totalPages }, (_, index) => (
            <button
              key={index}
              type="button"
              className={`capsule-tabs__dot ${index === safePage ? 'is-active' : ''}`}
              aria-label={`Mostrar página ${index + 1} de ${totalPages}`}
              aria-current={index === safePage ? 'page' : undefined}
              onClick={() => goToPage(index)}
            />
          ))}
        </div>
      )}

      <div className="capsule-tabs__navigation">
        <button
          type="button"
          className="capsule-tabs__arrow"
          aria-label="Mostrar pestañas anteriores"
          title="Pestañas anteriores"
          disabled={safePage === 0}
          onClick={() => goToPage(safePage - 1)}
        >
          <ChevronLeft aria-hidden="true" size={19} />
        </button>

        <div className="capsule-tabs__viewport">
          <div
            key={`${safePage}-${visibleCount}`}
            className="capsule-tabs__list"
            role="tablist"
            aria-label={ariaLabel}
            style={{ gridTemplateColumns: `repeat(${Math.max(1, currentPageTabs.length)}, minmax(0, 1fr))` }}
          >
            {currentPageTabs.map((item, visibleIndex) => {
              const index = pageStart + visibleIndex;
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
                  tabIndex={isActive || (!activeTabIsVisible && visibleIndex === 0) ? 0 : -1}
                  title={item.label}
                  className={`capsule-tabs__tab ${isActive ? 'is-active' : ''}`}
                  onClick={() => selectTab(item, index)}
                  onKeyDown={(event) => handleKeyDown(event, index)}
                >
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        <button
          type="button"
          className="capsule-tabs__arrow"
          aria-label="Mostrar pestañas siguientes"
          title="Pestañas siguientes"
          disabled={safePage === totalPages - 1}
          onClick={() => goToPage(safePage + 1)}
        >
          <ChevronRight aria-hidden="true" size={19} />
        </button>
      </div>

      <span className="capsule-tabs__status" aria-live="polite">
        Página {safePage + 1} de {totalPages}
      </span>
    </div>
  );
}
