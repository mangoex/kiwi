export type ProgressiveCatalogStage = 'categories' | 'selection' | 'products' | 'modifiers';

export interface ProgressiveCatalogStageInput {
  hasCategory: boolean;
  selectionRequired: boolean;
  hasModifierProduct: boolean;
  startsAtProducts?: boolean;
}

/** Presentation-only flow; catalog, pricing, cart and modifier authority remain elsewhere. */
export function progressiveCatalogStage({
  hasCategory,
  selectionRequired,
  hasModifierProduct,
  startsAtProducts = false,
}: ProgressiveCatalogStageInput): ProgressiveCatalogStage {
  if (hasModifierProduct) return 'modifiers';
  if (startsAtProducts) return 'products';
  if (!hasCategory) return 'categories';
  if (selectionRequired) return 'selection';
  return 'products';
}

export interface ModifierMinimumGroup {
  id: string;
  minimum_selections: number;
  maximum_selections: number;
}

/** Mirrors existing minimum rules without assigning new requiredness to optional groups. */
export function modifierSelectionsMeetMinimums(
  groups: readonly ModifierMinimumGroup[], selections: Readonly<Record<string, readonly string[]>>,
): boolean {
  return groups.every((group) => (selections[group.id] || []).length >= group.minimum_selections);
}
