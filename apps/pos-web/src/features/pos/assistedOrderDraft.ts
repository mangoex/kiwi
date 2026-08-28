export type AssistedOption = {
  id: string;
  name: string;
  price_delta_cents: number;
  kind: 'comment' | 'modifier';
};

export type AssistedSelection = {
  group_id: string;
  option_id: string;
  option_name: string;
  price_delta_cents: number;
  kind: 'comment' | 'modifier';
};

export type AssistedQuestion = {
  line_index: number;
  group_id: string;
  prompt: string;
  minimum_selections: number;
  maximum_selections: number;
  options: AssistedOption[];
};

export type AssistedOrderDraft = {
  customer_name: string;
  phone: string;
  order_type?: 'takeout' | 'delivery' | null;
  lines: Array<{
    product_id: string;
    product_name: string;
    quantity: number;
    selected_options: AssistedSelection[];
  }>;
  questions: AssistedQuestion[];
  status: 'needs_input' | 'ready';
  model: string;
};

export const selectedForQuestion = (draft: AssistedOrderDraft, question: AssistedQuestion) =>
  draft.lines[question.line_index]?.selected_options.filter(
    (option) => option.group_id === question.group_id,
  ) || [];

export const isAssistedDraftComplete = (draft: AssistedOrderDraft | null): boolean => Boolean(
  draft
  && draft.lines.length > 0
  && draft.questions.every((question) => (
    selectedForQuestion(draft, question).length >= question.minimum_selections
  )),
);

export function toggleAssistedOption(
  draft: AssistedOrderDraft,
  question: AssistedQuestion,
  option: AssistedOption,
): AssistedOrderDraft {
  const line = draft.lines[question.line_index];
  if (!line) return draft;
  const current = line.selected_options.filter((item) => item.group_id === question.group_id);
  const alreadySelected = current.some((item) => item.option_id === option.id);
  const nextGroup = alreadySelected
    ? current.filter((item) => item.option_id !== option.id)
    : question.maximum_selections === 1
      ? [{
          group_id: question.group_id,
          option_id: option.id,
          option_name: option.name,
          price_delta_cents: option.price_delta_cents,
          kind: option.kind,
        }]
      : current.length >= question.maximum_selections
        ? current
        : [...current, {
            group_id: question.group_id,
            option_id: option.id,
            option_name: option.name,
            price_delta_cents: option.price_delta_cents,
            kind: option.kind,
          }];
  const lines = draft.lines.map((item, index) => index === question.line_index ? {
    ...item,
    selected_options: [
      ...item.selected_options.filter((selected) => selected.group_id !== question.group_id),
      ...nextGroup,
    ],
  } : item);
  const nextDraft = { ...draft, lines };
  return { ...nextDraft, status: isAssistedDraftComplete(nextDraft) ? 'ready' : 'needs_input' };
}
