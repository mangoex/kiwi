const shiftDecimalPoint = (rawValue: string, places: number): string => {
  const value = rawValue.trim().replace(',', '.');
  if (!value || !/^\d*(?:\.\d*)?$/.test(value) || value === '.') return '';
  const [rawWhole = '0', fraction = ''] = value.split('.');
  const whole = rawWhole || '0';
  let digits = `${whole}${fraction}`;
  let point = whole.length + places;
  if (point <= 0) {
    digits = `${'0'.repeat(-point)}${digits}`;
    point = 0;
  } else if (point >= digits.length) {
    digits = `${digits}${'0'.repeat(point - digits.length)}`;
    point = digits.length;
  }
  const integer = (point === 0 ? '0' : digits.slice(0, point)).replace(/^0+(?=\d)/, '') || '0';
  const decimals = (point === 0 ? digits : digits.slice(point)).replace(/0+$/, '');
  return decimals ? `${integer}.${decimals}` : integer;
};

export const rateToPercent = (rate: string): string => shiftDecimalPoint(rate, 2);
export const percentToRate = (percent: string): string => shiftDecimalPoint(percent, -2);

// Presentation only: keep the source string for previews and commands.
export const formatRecipeDecimal = (value: string | number | null | undefined): string => {
  const match = String(value ?? '').trim().replace(',', '.').match(/^(-?)(\d+)(?:\.(\d+))?$/);
  if (!match) return '—';
  const [, sign, whole, fraction = ''] = match;
  let hundredths = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0').slice(0, 2));
  if (fraction.length > 2 && fraction[2] >= '5') hundredths += 1n;
  return `${sign && hundredths !== 0n ? '-' : ''}${hundredths / 100n}.${String(hundredths % 100n).padStart(2, '0')}`;
};

// Undefined means an untouched server/AI value, whose internal precision is retained.
export const recipeCaptureError = (input: string | undefined): string => {
  if (input === undefined) return '';
  if (!input.trim()) return 'Ingresa un valor con máximo 2 decimales.';
  return /^\d+(?:[.,]\d{1,2})?$/.test(input.trim())
    ? '' : 'Usa máximo 2 decimales, sin signos ni exponentes.';
};
