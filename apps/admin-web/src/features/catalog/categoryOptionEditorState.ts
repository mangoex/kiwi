export type CategoryOptionEditorGroup = {
  id?: string;
  code: string;
  name: string;
  status: 'active' | 'inactive' | 'archived';
} | null | undefined;

export type CategoryOptionEditorState = {
  code: string;
  name: string;
  status: 'active' | 'inactive' | 'archived';
};

export type CategoryOptionValueEditorState = {
  id: string;
  code: string;
  name: string;
  displayOrder: number;
  status: 'active' | 'inactive' | 'archived';
};

/** A category change must never retain the selector fields from another category. */
export function categoryOptionEditorState(
  group: CategoryOptionEditorGroup,
): CategoryOptionEditorState {
  return group
    ? { code: group.code, name: group.name, status: group.status }
    : { code: '', name: '', status: 'inactive' };
}

export function categoryOptionEditorHydrationKey(group: CategoryOptionEditorGroup): string {
  if (!group) return '';
  return [group.id || '', group.code, group.name, group.status].join('\u001f');
}

export function categoryOptionValueEditorState(value: {
  id: string;
  code: string;
  name: string;
  display_order: number;
  status: 'active' | 'inactive' | 'archived';
}): CategoryOptionValueEditorState {
  return {
    id: value.id,
    code: value.code,
    name: value.name,
    displayOrder: value.display_order,
    status: value.status,
  };
}
