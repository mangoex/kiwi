/** Parse capture exactly; floating-point multiplication is not a money conversion. */
export function expenseCents(input: string): number {
    const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(input.trim());
    if (!match)
        throw new Error('Escribe un importe con hasta dos decimales.');
    const cents = BigInt(match[1]) * 100n + BigInt((match[2] || '').padEnd(2, '0'));
    if (cents > 2147483647n)
        throw new Error('El importe supera el límite permitido por caja.');
    return Number(cents);
}
export const expenseMethods = { cash: 'Efectivo', transfer: 'Transferencia', card: 'Tarjeta', other: 'Otro' } as const;
