/**
 * Conversión exacta de importes monetarios en centavos MXN a texto en español.
 * Formato estándar mexicano: "SON: [MONTO EN LETRAS] PESOS XX/100 M.N."
 * Ejemplo: 36000 -> "SON: TRESCIENTOS SESENTA PESOS 00/100 M.N."
 */

const UNIDADES: string[] = [
  '',
  'UN',
  'DOS',
  'TRES',
  'CUATRO',
  'CINCO',
  'SEIS',
  'SIETE',
  'OCHO',
  'NUEVE',
  'DIEZ',
  'ONCE',
  'DOCE',
  'TRECE',
  'CATORCE',
  'QUINCE',
  'DIECISEIS',
  'DIECISIETE',
  'DIECIOCHO',
  'DIECINUEVE',
  'VEINTE',
  'VEINTIUN',
  'VEINTIDOS',
  'VEINTITRES',
  'VEINTICUATRO',
  'VEINTICINCO',
  'VEINTISEIS',
  'VEINTISIETE',
  'VEINTIOCHO',
  'VEINTINUEVE',
];

const DECENAS: string[] = [
  '',
  'DIEZ',
  'VEINTE',
  'TREINTA',
  'CUARENTA',
  'CINCUENTA',
  'SESENTA',
  'SETENTA',
  'OCHENTA',
  'NOVENTA',
];

const CENTENAS: string[] = [
  '',
  'CIENTO',
  'DOSCIENTOS',
  'TRESCIENTOS',
  'CUATROCIENTOS',
  'QUINIENTOS',
  'SEISCIENTOS',
  'SETECIENTOS',
  'OCHOCIENTOS',
  'NOVECIENTOS',
];

function convertirGrupo(n: number): string {
  if (n === 0) return '';
  if (n === 100) return 'CIEN';

  let resultado = '';
  const c = Math.floor(n / 100);
  const d = Math.floor((n % 100) / 10);
  const u = n % 10;
  const du = n % 100;

  if (c > 0) {
    resultado += CENTENAS[c] + ' ';
  }

  if (du > 0 && du <= 29) {
    resultado += UNIDADES[du];
  } else if (du > 29) {
    resultado += DECENAS[d];
    if (u > 0) {
      resultado += ' Y ' + UNIDADES[u];
    }
  }

  return resultado.trim();
}

/**
 * Convierte un entero positivo en letras (0 a 999,999,999).
 */
export function enteroALetras(n: number): string {
  if (n === 0) return 'CERO';
  if (n < 0) return 'MENOS ' + enteroALetras(Math.abs(n));

  const millones = Math.floor(n / 1_000_000);
  const restoMillones = n % 1_000_000;
  const miles = Math.floor(restoMillones / 1_000);
  const unidades = restoMillones % 1_000;

  let partes: string[] = [];

  if (millones > 0) {
    if (millones === 1) {
      partes.push('UN MILLON');
    } else {
      partes.push(convertirGrupo(millones) + ' MILLONES');
    }
  }

  if (miles > 0) {
    if (miles === 1) {
      partes.push('UN MIL');
    } else {
      partes.push(convertirGrupo(miles) + ' MIL');
    }
  }

  if (unidades > 0) {
    partes.push(convertirGrupo(unidades));
  }

  return partes.join(' ').trim();
}

/**
 * Convierte centavos enteros a la leyenda mexicana oficial en cheques y tickets:
 * Ej: 36000 -> "SON: TRESCIENTOS SESENTA PESOS 00/100 M.N."
 * Ej: 100 -> "SON: UN PESO 00/100 M.N."
 * Ej: 31034 -> "SON: TRESCIENTOS DIEZ PESOS 34/100 M.N."
 */
export function numberToWordsMxn(totalCents: number): string {
  const cents = Math.max(0, Math.round(totalCents));
  const pesos = Math.floor(cents / 100);
  const residuoCentavos = cents % 100;
  const centavosStr = residuoCentavos.toString().padStart(2, '0');

  const textoPesos = enteroALetras(pesos);
  const moneda = pesos === 1 ? 'PESO' : 'PESOS';

  return `SON: ${textoPesos} ${moneda} ${centavosStr}/100 M.N.`;
}
