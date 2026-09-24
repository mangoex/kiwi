export interface CategoryOptionValue {
  id: string;
  code: string;
  name: string;
  display_order: number;
}

export interface CategorySelectionGroup {
  id: string;
  code: string;
  name: string;
  values: CategoryOptionValue[];
}

export interface CategoryOptionProduct {
  id: string;
  category_id?: string;
  name: string;
  selection?: { group_id: string; value_id: string } | null;
}

export interface ProductCategoryReference {
  category_id?: string;
  category?: string;
}

export type CatalogMenuGroupId = 'all' | 'food' | 'drinks' | 'other' | 'favorites';

export const CATALOG_MENU_GROUPS: ReadonlyArray<{ id: CatalogMenuGroupId; label: string }> = [
  { id: 'all', label: 'TODO' },
  { id: 'food', label: 'ALIMENTOS' },
  { id: 'drinks', label: 'BEBIDAS' },
  { id: 'other', label: 'OTROS' },
  { id: 'favorites', label: 'FAVORITOS' },
];

export interface CatalogMenuProduct extends ProductCategoryReference {
  selection?: { group_id: string; value_id: string } | null;
  id: string;
  station?: string;
  classification_code?: string | null;
  catalog_classification_mode?: string;
  catalog_generation?: number;
  catalog_hash?: string;
  catalog_projection_hash?: string;
}

export function categoriesWithAvailableProducts<
  TCategory extends { id: string; name: string },
>(categories: readonly TCategory[], products: readonly ProductCategoryReference[]): TCategory[] {
  if (products.length === 0) return [];
  const categoryIds = new Set(products.map((product) => product.category_id).filter(Boolean));
  const categoryNames = new Set(products.map((product) => product.category).filter(Boolean));
  return categories.filter((category) =>
    category.id === ''
    || category.name === 'Todas'
    || categoryIds.has(category.id)
    || categoryNames.has(category.name),
  );
}

export function validateCatalogClassification(products: readonly CatalogMenuProduct[]): void {
  const modes = new Set(products.map((product) => product.catalog_classification_mode ?? 'legacy'));
  if (modes.size > 1 || [...modes].some((mode) => mode !== 'legacy' && mode !== 'explicit')) {
    throw new Error('El catálogo tiene modos de clasificación incompatibles.');
  }
  if (modes.has('explicit') && products.some((product) => !['food', 'drinks', 'other'].includes(product.classification_code ?? ''))) {
    throw new Error('El catálogo explícito tiene una clasificación pendiente o inválida.');
  }
}

export function validateCatalogClassificationSnapshot(
  categories: readonly { id: string; classification_code?: string | null; catalog_classification_mode?: string; catalog_generation?: number; catalog_hash?: string; catalog_projection_hash?: string; selection_group?: { id: string; values: readonly { id: string }[] } | null }[],
  products: readonly CatalogMenuProduct[],
): void {
  validateCatalogClassification(products);
  const rows = [...categories, ...products];
  if (rows.some((row) => row.catalog_classification_mode === 'explicit' || row.catalog_generation !== undefined || row.catalog_hash !== undefined)) {
    const generations = new Set(rows.map((row) => row.catalog_generation));
    const hashes = new Set(rows.map((row) => row.catalog_hash));
    const invalidMetadata = rows.some((row) => {
      const generation = row.catalog_generation ?? -1;
      if (!Number.isSafeInteger(generation) || generation < 0) return true;
      if ((row.catalog_classification_mode ?? 'legacy') === 'legacy' && generation === 0) {
        return row.catalog_hash !== '';
      }
      return generation === 0 || !row.catalog_hash;
    });
    if (generations.size !== 1 || hashes.size !== 1 || invalidMetadata) {
      throw new Error('Grupos y productos pertenecen a generaciones diferentes del catálogo. Reintenta la carga.');
    }
  }
  if (rows.some((row) => row.catalog_projection_hash !== undefined)
    && (new Set(rows.map((row) => row.catalog_projection_hash)).size !== 1 || rows.some((row) => !row.catalog_projection_hash))) {
    throw new Error('Grupos y productos tienen proyecciones diferentes del catálogo. Reintenta la carga.');
  }
  const categoriesById = new Map(categories.map((category) => [category.id, category]));
  for (const product of products) {
    const category = categoriesById.get(product.category_id ?? '');
    const mode = product.catalog_classification_mode ?? 'legacy';
    const selectionGroup = category?.selection_group;
    if (selectionGroup
      ? product.selection?.group_id !== selectionGroup.id || !selectionGroup.values.some((value) => value.id === product.selection?.value_id)
      : product.selection != null) {
      throw new Error('El subgrupo del producto no corresponde al catálogo. Reintenta la carga.');
    }
    if ((category?.catalog_classification_mode ?? 'legacy') !== mode
      || (mode === 'explicit' && (!category || category.classification_code !== product.classification_code))) {
      throw new Error('La clasificación de grupos y productos no corresponde al mismo catálogo. Reintenta la carga.');
    }
  }
}

export function productsForCatalogMenuGroup<TProduct extends CatalogMenuProduct>(
  products: readonly TProduct[], groupId: CatalogMenuGroupId, favoriteProductIds: readonly string[],
): TProduct[] {
  validateCatalogClassification(products);
  if (groupId === 'all') return [...products];
  if (products.some((product) => product.catalog_classification_mode === 'explicit') && groupId !== 'favorites') {
    return products.filter((product) => product.classification_code === groupId);
  }
  if (groupId === 'food') return products.filter((product) => product.station === 'kitchen');
  if (groupId === 'drinks') return products.filter((product) => product.station === 'drinks');
  if (groupId === 'other') {
    return products.filter((product) => product.station !== 'kitchen' && product.station !== 'drinks');
  }
  const favorites = new Set(favoriteProductIds);
  return products.filter((product) => favorites.has(product.id));
}

export function categoriesForCatalogMenuGroup<
  TCategory extends { id: string; name: string },
  TProduct extends CatalogMenuProduct,
>(
  categories: readonly TCategory[], products: readonly TProduct[], groupId: CatalogMenuGroupId,
  favoriteProductIds: readonly string[],
): TCategory[] {
  if (groupId === 'favorites') return [];
  const groupedProducts = productsForCatalogMenuGroup(products, groupId, favoriteProductIds);
  return categoriesWithAvailableProducts(categories, groupedProducts).filter(
    (category) => category.id !== '' && category.name !== 'Todas',
  );
}

export interface CategoryOptionState {
  categoryId: string;
  valueId: string;
}

export interface CatalogNavigationState<TCart> extends CategoryOptionState {
  cart: TCart;
  search: string;
  transient: {
    modifierProductId: string | null;
    groups: string[];
    selections: Record<string, string[]>;
    error: string;
  };
}

export type CatalogProjectionState = 'ready' | 'error' | 'selection-empty';

/** Keeps projection recovery independent from cart and product selection. */
export function catalogProjectionState(
  hasCatalogError: boolean,
  group: CategorySelectionGroup | null | undefined,
): CatalogProjectionState {
  if (hasCatalogError) return 'error';
  if (group && availableOptionValues(group).length === 0) return 'selection-empty';
  return 'ready';
}

export function availableOptionValues(group: CategorySelectionGroup): CategoryOptionValue[] {
  return [...group.values].sort((left, right) =>
    left.display_order - right.display_order || left.name.localeCompare(right.name) || left.id.localeCompare(right.id),
  );
}

export function resolveCategoryOptionState(
  category: { selection_group?: CategorySelectionGroup | null }, valueId: string,
): 'products' | 'selection-required' {
  if (!category.selection_group) return 'products';
  return availableOptionValues(category.selection_group).some((value) => value.id === valueId)
    ? 'products'
    : 'selection-required';
}

export function filterProductsForCategoryOption<T extends CategoryOptionProduct>(
  products: readonly T[], categoryId: string, valueId: string, search: string,
): T[] {
  const normalizedSearch = search.trim().toLocaleLowerCase('es-MX');
  return products.filter((product) =>
    (!categoryId || product.category_id === categoryId)
    && (!valueId || product.selection?.value_id === valueId)
    && (!normalizedSearch || product.name.toLocaleLowerCase('es-MX').includes(normalizedSearch)),
  );
}

export function transitionCategoryOption(
  current: CategoryOptionState, categoryId: string, valueId: string,
): CategoryOptionState {
  if (current.categoryId !== categoryId) return { categoryId, valueId: '' };
  return { categoryId, valueId };
}

/** Navigation clears only uncommitted personalization; cart and search are preserved verbatim. */
export function transitionCatalogNavigation<TCart>(
  current: CatalogNavigationState<TCart>, categoryId: string, valueId: string,
): CatalogNavigationState<TCart> {
  const selection = transitionCategoryOption(current, categoryId, valueId);
  return {
    ...current,
    ...selection,
    transient: { modifierProductId: null, groups: [], selections: {}, error: '' },
  };
}
