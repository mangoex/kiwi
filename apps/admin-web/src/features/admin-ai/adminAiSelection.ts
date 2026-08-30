export type AdminAiSelection = {
  proposal_id: string;
  kind: string;
  item_ids: string[];
};

export const readAdminAiSelection = (proposalId: string | null): AdminAiSelection | null => {
  if (!proposalId) return null;
  try {
    const raw = sessionStorage.getItem(`admin-ai-selection:${proposalId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AdminAiSelection>;
    if (parsed.proposal_id !== proposalId || !Array.isArray(parsed.item_ids)) return null;
    return {
      proposal_id: proposalId,
      kind: typeof parsed.kind === 'string' ? parsed.kind : '',
      item_ids: parsed.item_ids.filter((id): id is string => typeof id === 'string').slice(0, 100),
    };
  } catch {
    return null;
  }
};
