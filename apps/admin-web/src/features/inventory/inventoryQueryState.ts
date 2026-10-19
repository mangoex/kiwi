export interface InventoryBranch { id: string; name: string; timezone: string; warehouse_name?: string | null }
export interface InventoryCapabilities { organization_read: boolean; branches: InventoryBranch[] }
export type InventoryQueryScope = { kind: 'organization'; branch_id: null } | { kind: 'branch'; branch_id: string };

export function initialInventoryScope(capabilities?: InventoryCapabilities): InventoryQueryScope | null {
  if (!capabilities) return null;
  if (capabilities.organization_read) return { kind: 'organization', branch_id: null };
  return capabilities.branches.length === 1 ? { kind: 'branch', branch_id: capabilities.branches[0].id } : null;
}
export function inventoryScopeAllowed(capabilities: InventoryCapabilities | undefined, scope: InventoryQueryScope): boolean {
  return Boolean(capabilities && (scope.kind === 'organization' ? capabilities.organization_read
    : capabilities.branches.some(branch => branch.id === scope.branch_id)));
}

interface ThresholdSource { minimum_quantity: string | null; maximum_quantity: string | null }
export interface ThresholdDraft { minimum?: string; maximum?: string }
const normalize = (value: string) => value.trim().replace(',', '.');
const exact = (value: string): bigint | null => {
  const match = normalize(value).match(/^(\d{1,12})(?:\.(\d{1,6}))?$/);
  return match ? BigInt(match[1]) * 1000000n + BigInt((match[2] || '').padEnd(6, '0')) : null;
};
export function thresholdDraftError(source: ThresholdSource, draft: ThresholdDraft): string {
  for (const value of [draft.minimum, draft.maximum]) {
    if (value !== undefined && !/^\d{1,12}(?:[.,]\d{1,2})?$/.test(value.trim())) {
      return 'Usa máximo 2 decimales, sin signos ni exponentes.';
    }
  }
  const minimum = exact(draft.minimum ?? source.minimum_quantity ?? '');
  const maximum = exact(draft.maximum ?? source.maximum_quantity ?? '');
  if (minimum === null || maximum === null) return 'Captura mínimo y máximo.';
  return maximum < minimum ? 'El máximo debe ser mayor o igual al mínimo.' : '';
}
export function thresholdPayload(source: ThresholdSource, draft: ThresholdDraft, version: number | null) {
  return { minimum_quantity: draft.minimum === undefined ? source.minimum_quantity : normalize(draft.minimum),
    maximum_quantity: draft.maximum === undefined ? source.maximum_quantity : normalize(draft.maximum),
    expected_version: version };
}
