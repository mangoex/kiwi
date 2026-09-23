import React, { useState } from 'react';
import { X, ChevronDown, ChevronUp } from 'lucide-react';

export interface AccordionSectionProps {
  id?: string;
  title: string;
  badge?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
  action?: React.ReactNode;
}

export const AccordionSection: React.FC<AccordionSectionProps> = ({
  title,
  badge,
  defaultOpen = true,
  children,
  action,
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-gray-200 rounded-lg bg-white overflow-hidden shadow-xs transition-all mb-3">
      <div
        className="w-full px-4 py-3 bg-gray-50/80 hover:bg-gray-100/70 flex items-center justify-between cursor-pointer border-b border-gray-100 transition-colors select-none"
        onClick={() => setIsOpen(!isOpen)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setIsOpen(!isOpen);
          }
        }}
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-gray-800 tracking-tight">{title}</span>
          {badge}
        </div>
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {action}
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="text-gray-400 hover:text-gray-600 p-0.5 rounded transition-colors"
            aria-label={isOpen ? 'Colapsar sección' : 'Expandir sección'}
          >
            {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>
      {isOpen && <div className="p-4 space-y-3 text-sm text-gray-700">{children}</div>}
    </div>
  );
};

export interface FastTabDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  footerActions?: React.ReactNode;
}

export const FastTabDrawer: React.FC<FastTabDrawerProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  badge,
  children,
  footerActions,
}) => {
  if (!isOpen) return null;

  return (
    <aside
      className="fixed top-0 right-0 bottom-0 w-full sm:w-[460px] bg-white border-l border-gray-200 shadow-2xl z-30 flex flex-col transition-all duration-300 animate-in slide-in-from-right"
      aria-label="Panel lateral de detalles FastTab"
    >
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-200 bg-white flex items-center justify-between gap-3 shrink-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-gray-900 truncate tracking-tight">{title}</h2>
            {badge}
          </div>
          {subtitle && (
            <p className="text-xs text-gray-500 truncate mt-0.5">{subtitle}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          title="Cerrar panel (Esc)"
          aria-label="Cerrar panel"
        >
          <X size={18} />
        </button>
      </div>

      {/* Body with continuous scroll */}
      <div className="flex-1 overflow-y-auto p-4 space-y-1 bg-gray-50/50">
        {children}
      </div>

      {/* Optional Sticky Footer */}
      {footerActions && (
        <div className="p-4 border-t border-gray-200 bg-white shrink-0 flex items-center justify-end gap-2 shadow-xs">
          {footerActions}
        </div>
      )}
    </aside>
  );
};

export default FastTabDrawer;
