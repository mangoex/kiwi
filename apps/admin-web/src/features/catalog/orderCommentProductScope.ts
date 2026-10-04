export type CategorySelectionState = 'none' | 'partial' | 'all';

function normalizedIds(ids: string[]): string[] {
  return [...new Set(ids)].sort();
}

export function categorySelectionState(
  categoryProductIds: string[],
  selectedProductIds: string[],
): CategorySelectionState {
  const categoryIds = new Set(categoryProductIds);
  if (categoryIds.size === 0) return 'none';

  const selectedCount = new Set(selectedProductIds.filter((id) => categoryIds.has(id))).size;
  if (selectedCount === 0) return 'none';
  return selectedCount === categoryIds.size ? 'all' : 'partial';
}

export function toggleProductSelection(
  selectedProductIds: string[],
  productId: string,
  checked: boolean,
): string[] {
  const next = new Set(selectedProductIds);
  if (checked) next.add(productId);
  else next.delete(productId);
  return normalizedIds([...next]);
}

export function toggleCategoryProducts(
  selectedProductIds: string[],
  categoryProductIds: string[],
  checked: boolean,
): string[] {
  const next = new Set(selectedProductIds);
  categoryProductIds.forEach((productId) => {
    if (checked) next.add(productId);
    else next.delete(productId);
  });
  return normalizedIds([...next]);
}

export function assignmentImpact(currentProductIds: string[], desiredProductIds: string[]) {
  const current = new Set(currentProductIds);
  const desired = new Set(desiredProductIds);
  return {
    added: normalizedIds([...desired].filter((id) => !current.has(id))),
    removed: normalizedIds([...current].filter((id) => !desired.has(id))),
    retained: normalizedIds([...desired].filter((id) => current.has(id))),
  };
}
