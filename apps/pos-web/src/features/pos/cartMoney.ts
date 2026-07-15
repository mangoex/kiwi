export interface CartMoneyExtra {
  sale_price_cents: number;
  portions: number;
}

export interface CartMoneyLine {
  price_cents: number;
  modifierPriceCents: number;
  ingredientExtras: CartMoneyExtra[];
  quantity: number;
}

export function extraTotalCents(extras: CartMoneyExtra[]): number {
  return extras.reduce(
    (total, extra) => total + (extra.sale_price_cents * extra.portions),
    0,
  );
}

export function cartLineUnitTotalCents(line: Pick<CartMoneyLine, 'price_cents' | 'modifierPriceCents' | 'ingredientExtras'>): number {
  return line.price_cents + line.modifierPriceCents + extraTotalCents(line.ingredientExtras);
}

export function cartLineTotalCents(line: CartMoneyLine): number {
  return cartLineUnitTotalCents(line) * line.quantity;
}

export function cartSubtotalCents(lines: CartMoneyLine[]): number {
  return lines.reduce((total, line) => total + cartLineTotalCents(line), 0);
}

export function formatMxnCents(cents: number): string {
  const sign = cents < 0 ? '-' : '';
  const absolute = Math.abs(cents);
  const pesos = Math.floor(absolute / 100).toLocaleString('es-MX');
  const centavos = String(absolute % 100).padStart(2, '0');
  return `${sign}$${pesos}.${centavos}`;
}
