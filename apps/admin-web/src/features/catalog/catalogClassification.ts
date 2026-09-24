export type ClassificationCode = 'food' | 'drinks' | 'other';
export const CLASSIFICATIONS: ReadonlyArray<{ code: ClassificationCode; label: string }> = [
  { code: 'food', label: 'Alimentos' },
  { code: 'drinks', label: 'Bebidas' },
  { code: 'other', label: 'Otros' },
];
export function classificationLabel(code: string | null | undefined): string {
  return CLASSIFICATIONS.find((item) => item.code === code)?.label ?? 'Pendiente de clasificación';
}
export interface CategoryDraft {
  name: string;
  display_order: number;
  status: 'active' | 'inactive';
  classification_code: ClassificationCode | '';
  configuration_version: number;
}
export function categoryCommandPayload(draft: CategoryDraft, creating: boolean) {
  if (!draft.name.trim()) throw new Error('Escribe el nombre del grupo.');
  if (creating && !draft.classification_code) throw new Error('Selecciona una clasificación.');
  return {
    name: draft.name.trim().toLocaleUpperCase('es-MX'),
    display_order: draft.display_order,
    ...(creating ? {} : { status: draft.status }),
    classification_code: draft.classification_code || null,
    expected_version: creating ? 0 : draft.configuration_version,
  };
}
export interface CategoryAttempt { fingerprint: string; key: string }
export function categoryCommandAttempt(previous: CategoryAttempt | null, target: string, payload: unknown, createKey: () => string): CategoryAttempt {
  const fingerprint = JSON.stringify([target, payload]);
  return previous?.fingerprint === fingerprint ? previous : { fingerprint, key: createKey() };
}
