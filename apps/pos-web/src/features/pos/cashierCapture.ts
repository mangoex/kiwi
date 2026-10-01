/** Presentation/capture helpers. Prices, stock and payment calculations remain in Python. */
export function parseCartQuantity(text: string): number | null {
  if (!/^[0-9]+$/.test(text.trim())) return null;
  const value = Number(text.trim());
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

export function requiredGroupsFirst<T extends { minimum_selections: number }>(groups: readonly T[]): T[] {
  return [...groups].sort((left, right) => Number(right.minimum_selections > 0) - Number(left.minimum_selections > 0));
}
