const MXN_PATTERN = /^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/;
const MAX_SAFE_CENTS = BigInt(Number.MAX_SAFE_INTEGER);

export function mxnToCentsExact(mxn: string): number {
  const normalized = mxn.trim();
  if (!MXN_PATTERN.test(normalized)) {
    throw new Error('Escribe un importe MXN válido con máximo dos decimales.');
  }
  const [pesos, decimals = ''] = normalized.split('.');
  const cents = BigInt(pesos) * 100n + BigInt(`${decimals}00`.slice(0, 2));
  if (cents > MAX_SAFE_CENTS) {
    throw new Error('El importe excede el rango permitido.');
  }
  return Number(cents);
}

export function centsToMxn(cents: number): string {
  if (!Number.isSafeInteger(cents) || cents < 0) {
    throw new Error('Los centavos deben ser un entero seguro no negativo.');
  }
  const value = BigInt(cents);
  return `${value / 100n}.${(value % 100n).toString().padStart(2, '0')}`;
}

export function surchargeMxnError(
  chargeAdditional: boolean,
  addPriceDeltaMxn: string,
): string | null {
  if (!chargeAdditional) return null;
  try {
    if (mxnToCentsExact(addPriceDeltaMxn) <= 0) {
      return 'El precio adicional debe ser mayor a $0.00.';
    }
  } catch (error) {
    return error instanceof Error ? error.message : 'El importe MXN no es válido.';
  }
  return null;
}
