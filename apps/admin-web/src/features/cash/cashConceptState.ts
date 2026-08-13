export type CashConceptForm = {
  code: string;
  name: string;
  allowed_movement_type: 'deposit' | 'withdrawal' | 'both';
  valid_from: string;
};

export const formatLocalDateTime = (value: Date) => {
  const pad = (part: number) => String(part).padStart(2, '0');
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
};

const versionFields = (form: CashConceptForm) => ({
  name: form.name.trim(),
  allowed_movement_type: form.allowed_movement_type,
  requires_reference: true,
  requires_evidence: true,
  valid_from: new Date(form.valid_from).toISOString(),
});

export const createCashConceptPayload = (form: CashConceptForm) => ({
  code: form.code.trim().toUpperCase(),
  ...versionFields(form),
});

export const versionCashConceptPayload = (form: CashConceptForm) => versionFields(form);

export const canManageCashConcepts = (user: { permissions?: string[] }) =>
  Boolean(user.permissions?.includes('cash.concept.manage'));

export const cashConceptViewState = ({
  loading,
  error,
  conceptCount,
}: {
  loading: boolean;
  error: string;
  conceptCount: number;
}) => {
  if (loading) return 'loading';
  if (error) return 'error';
  return conceptCount ? 'data' : 'empty';
};

export const retainSuccessMessageAfterLoad = (message: string) => message;

export const commandKeyStore = () => {
  const keys: Record<string, string> = {};
  return {
    get(operation: string, create: () => string) {
      keys[operation] ||= create();
      return keys[operation];
    },
    clear(operation: string) {
      delete keys[operation];
    },
  };
};
