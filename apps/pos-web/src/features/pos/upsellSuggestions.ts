export type UpsellRecommendation = {
  product_id: string;
  product_name: string;
  price_cents: number;
  reason: string;
};

export const addDismissedUpsellProduct = (
  dismissedProductIds: ReadonlySet<string>,
  productId: string,
): Set<string> => {
  const nextDismissedProductIds = new Set(dismissedProductIds);
  nextDismissedProductIds.add(productId);
  return nextDismissedProductIds;
};

export const getVisibleUpsellRecommendations = (
  recommendations: readonly UpsellRecommendation[],
  dismissedProductIds: ReadonlySet<string>,
  limit = 2,
): UpsellRecommendation[] => recommendations
  .filter((recommendation) => !dismissedProductIds.has(recommendation.product_id))
  .slice(0, Math.max(0, limit));
