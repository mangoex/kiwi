export function formatMxnCents(cents: number): string {
  const sign = cents < 0 ? '-' : '';
  const absolute = Math.abs(cents);
  const pesos = Math.floor(absolute / 100).toLocaleString('es-MX');
  const centavos = String(absolute % 100).padStart(2, '0');
  return `${sign}$${pesos}.${centavos}`;
}
