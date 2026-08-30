import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import './Modal.css';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  maxWidth?: string | number;
  contentClassName?: string;
}

export const Modal = ({ isOpen, onClose, title, children, size = 'md', maxWidth, contentClassName }: ModalProps) => {
  const overlayRef = useRef<HTMLDivElement>(null);

  const calculatedMaxWidth = maxWidth || (
    size === 'sm' ? '400px' :
    size === 'md' ? '520px' :
    size === 'lg' ? '700px' :
    size === 'xl' ? '920px' :
    size === '2xl' ? '1180px' : '520px'
  );

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return createPortal(
    <div className="ui-modal-overlay" ref={overlayRef} onClick={(e) => {
      if (e.target === overlayRef.current) onClose();
    }}>
      <div className={`ui-modal-content${contentClassName ? ` ${contentClassName}` : ''}`} role="dialog" aria-modal="true" style={{ maxWidth: calculatedMaxWidth }}>
        {title && (
          <div className="ui-modal-header">
            <h3 className="ui-modal-title">{title}</h3>
            <button className="ui-modal-close" onClick={onClose} aria-label="Cerrar">
              <X size={20} />
            </button>
          </div>
        )}
        <div className="ui-modal-body">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
};
