export function parseCashCents(value: string): number | null {
  const normalized = value.trim();
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  const [whole, fraction = ''] = normalized.split('.');
  const cents = Number(`${whole}${fraction.padEnd(2, '0')}`);
  return Number.isSafeInteger(cents) && cents > 0 ? cents : null;
}

export function nextCashIdempotencyKey(current: string | null): string {
  return current || crypto.randomUUID();
}

export function cashMovementCapabilities(input: {
  canRead: boolean;
  canWithdraw: boolean;
  canDeposit: boolean;
}) {
  const canWrite = input.canWithdraw || input.canDeposit;
  return {
    ...input,
    canWrite,
    canUse: input.canRead || canWrite,
    initialType: input.canWithdraw ? 'withdrawal' as const : 'deposit' as const,
  };
}
