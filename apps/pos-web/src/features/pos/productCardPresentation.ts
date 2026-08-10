export type ProductCardPresentation = 'image' | 'fallback';

export function productCardPresentation(
  imageUrl: string | null | undefined,
): ProductCardPresentation {
  return typeof imageUrl === 'string' && imageUrl.trim() !== '' ? 'image' : 'fallback';
}
