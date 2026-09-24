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
