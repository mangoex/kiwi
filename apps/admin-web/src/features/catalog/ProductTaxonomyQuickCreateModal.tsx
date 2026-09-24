import React, { useEffect, useId, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { FolderPlus, X } from 'lucide-react';

export interface QuickCreateCategory {
  id: string;
  name: string;
  display_order?: number;
  status?: string;
}

interface QuickCreatedSubgroup {
  id: string;
  code: string;
  name: string;
  status: 'active' | 'inactive' | 'archived';
}

interface QuickCreateSelectionGroup {
  id: string;
  name: string;
  status: 'active' | 'inactive' | 'archived';
}

export type ProductTaxonomyQuickCreateResult =
  | { kind: 'group'; group: QuickCreateCategory }
  | {
    kind: 'subgroup';
    categoryId: string;
    selectionGroup: QuickCreateSelectionGroup;
    subgroup: QuickCreatedSubgroup;
  };

interface ProductTaxonomyQuickCreateModalProps {
  isOpen: boolean;
  mode: 'group' | 'subgroup';
  categories: QuickCreateCategory[];
  selectedCategory: QuickCreateCategory | null;
  selectionGroup?: QuickCreateSelectionGroup | null;
  onClose: () => void;
  onCreated: (result: ProductTaxonomyQuickCreateResult) => Promise<void> | void;
}

const failureMessage = (reason: unknown): string => reason instanceof ApiError
  ? reason.message
  : reason instanceof Error
    ? reason.message
    : 'No fue posible completar el alta. Intenta nuevamente.';

export function ProductTaxonomyQuickCreateModal({
  isOpen,
  mode,
  categories,
  selectedCategory,
  selectionGroup,
  onClose,
  onCreated,
}: ProductTaxonomyQuickCreateModalProps) {
  const titleId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [name, setName] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    setName('');
    setError('');
    window.requestAnimationFrame(() => inputRef.current?.focus());
  }, [isOpen, mode, selectedCategory?.id]);

  const createMutation = useMutation({
    mutationFn: async (): Promise<ProductTaxonomyQuickCreateResult> => {
      const canonicalName = name.trim().toLocaleUpperCase('es-MX');
      if (!canonicalName) throw new Error('Escribe un nombre antes de guardar.');

      if (mode === 'group') {
        const nextDisplayOrder = categories.reduce(
          (highest, category) => Math.max(highest, category.display_order ?? 0),
          0,
        ) + 1;
        const saved = await fetchApi<{ id: string }>('/categories', {
          method: 'POST',
          body: JSON.stringify({ name: canonicalName, display_order: nextDisplayOrder }),
        });
        return {
          kind: 'group',
          group: { id: saved.id, name: canonicalName, display_order: nextDisplayOrder, status: 'active' },
        };
      }

      if (!selectedCategory) throw new Error('Selecciona un grupo antes de crear el subgrupo.');
      const canonicalSelectionGroup = selectionGroup || await fetchApi<QuickCreateSelectionGroup>(
        `/categories/${selectedCategory.id}/selection-group`,
        { method: 'POST', body: JSON.stringify({}) },
      );
      const groupId = canonicalSelectionGroup.id;
      const subgroup = await fetchApi<QuickCreatedSubgroup>(
        `/catalog/category-option-groups/${groupId}/values`,
        { method: 'POST', body: JSON.stringify({ name: canonicalName }) },
      );
      return {
        kind: 'subgroup',
        categoryId: selectedCategory.id,
        selectionGroup: canonicalSelectionGroup,
        subgroup,
      };
    },
    onSuccess: async (result) => {
      await onCreated(result);
      onClose();
    },
    onError: (reason) => setError(failureMessage(reason)),
  });

  if (!isOpen) return null;

  const isSubgroup = mode === 'subgroup';
  const closeIfIdle = () => {
    if (!createMutation.isPending) onClose();
  };

  return (
    <div
      className="retro-modal-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) closeIfIdle();
      }}
    >
      <div
        className="retro-modal-window product-taxonomy-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={(event) => {
          if (event.key === 'Escape') closeIfIdle();
        }}
      >
        <div className="retro-modal-header">
          <span id={titleId}>{isSubgroup ? 'Nuevo subgrupo' : 'Nuevo grupo'}</span>
          <button
            type="button"
            className="product-taxonomy-modal-close"
            onClick={closeIfIdle}
            disabled={createMutation.isPending}
            aria-label="Cerrar alta rápida"
          >
            <X size={18} />
          </button>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setError('');
            createMutation.mutate();
          }}
        >
          <div className="retro-modal-body">
            <p className="product-taxonomy-modal-copy">
              {isSubgroup
                ? 'El subgrupo se agregará al grupo elegido y quedará seleccionado en este producto.'
                : 'El grupo se agregará al catálogo y quedará seleccionado en este producto.'}
            </p>
            {isSubgroup && (
              <div className="product-taxonomy-context" aria-label="Grupo seleccionado para el nuevo subgrupo">
                <FolderPlus size={18} />
                <span>Grupo seleccionado:</span>
                <strong>{selectedCategory?.name || 'Ninguno'}</strong>
              </div>
            )}
            <label className="product-taxonomy-modal-label" htmlFor={`${titleId}-name`}>
              Nombre del {isSubgroup ? 'subgrupo' : 'grupo'}
            </label>
            <input
              ref={inputRef}
              id={`${titleId}-name`}
              className="productos-form-input product-taxonomy-modal-input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={isSubgroup ? 'Ej. ARTESANALES' : 'Ej. CERVEZAS'}
              autoComplete="off"
              disabled={createMutation.isPending}
            />
            {error && <div className="productos-inline-error" role="alert">{error}</div>}
          </div>
          <div className="retro-modal-footer">
            <button
              type="button"
              className="productos-action-btn"
              onClick={closeIfIdle}
              disabled={createMutation.isPending}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="productos-action-btn save-highlight"
              disabled={!name.trim() || (isSubgroup && !selectedCategory) || createMutation.isPending}
            >
              {createMutation.isPending ? 'Guardando…' : isSubgroup ? 'Agregar subgrupo' : 'Crear grupo'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
