/**
 * Generador y formateador de tickets de venta y comandas de cocina térmicas.
 * Replica fielmente el formato Soft Restaurant V9.5 PRO para Kiwi Comida Natural,
 * con soporte para ancho configurable (40 o 42 columnas) y comandos directos ESC/POS.
 */

import { numberToWordsMxn } from './numberToWordsMxn';

export interface ReceiptLine {
  quantity: number;
  productName: string;
  unitPriceCents?: number;
  totalCents: number;
  modifiers?: string[];
  lineNotes?: string | null;
  station?: string | null;
}

export interface TicketPrintData {
  brandName?: string;
  businessName?: string;
  rfc?: string;
  fiscalAddress?: string;
  branchAddress?: string;
  folio: string;
  orderNumber?: string | number;
  createdAt: string;
  customerName?: string | null;
  customerPhone?: string | null;
  driverName?: string | null;
  colonia?: string | null;
  zone?: string | null;
  serviceTypeLabel?: string | null;
  lines: ReceiptLine[];
  subtotalCents?: number;
  taxCents?: number;
  totalCents: number;
  cashTender?: {
    receivedCents: number;
    changeCents: number;
  } | null;
  footerNotes?: string[];
}

export interface KitchenPrintData {
  folio: string;
  orderNumber?: string | number;
  createdAt: string;
  serviceTypeLabel?: string | null;
  customerName?: string | null;
  customerPhone?: string | null;
  driverName?: string | null;
  orderNotes?: string | null;
  station?: string | null;
  lines: ReceiptLine[];
}

// Valores predeterminados basados en el ticket de Soft Restaurant de Kiwi
export const DEFAULT_KIWI_BRAND = 'KIWI COMIDA NATURAL';
export const DEFAULT_KIWI_BUSINESS = 'ELISA AMAYRANI INZUNZA DOMINGUEZ';
export const DEFAULT_KIWI_RFC = 'RFC:IUDE931111KM2';
export const DEFAULT_KIWI_ADDRESS = 'CALLE JOSEFA ORTIZ DE DOMINGUEZ NUM 598 INT 6 COLONIA CHAPULTEPEC CULIACAN SINALOA MEXICO CP 80040';
export const DEFAULT_KIWI_BRANCH = 'SUCURSAL:CALLE JOSEFA ORTIZ DE DOMINGUEZ NUM 598 INT 6 COLONIA CHAPULTEPEC CULIACAN SINALOA';

/** Formatea centavos a texto monetario con dos decimales, ej. 36000 -> "$360.00" */
export function formatReceiptMoney(cents: number): string {
  const value = (cents / 100).toFixed(2);
  return `$${value}`;
}

/** Divide un texto largo en líneas que no excedan el ancho especificado */
export function wrapText(text: string, maxWidth: number): string[] {
  if (!text) return [];
  const words = text.trim().split(/\s+/);
  const lines: string[] = [];
  let currentLine = '';

  for (const word of words) {
    if (!currentLine) {
      currentLine = word;
    } else if (currentLine.length + 1 + word.length <= maxWidth) {
      currentLine += ' ' + word;
    } else {
      lines.push(currentLine);
      currentLine = word;
    }
  }
  if (currentLine) {
    lines.push(currentLine);
  }
  return lines;
}

/** Centra un texto dentro de un ancho determinado */
export function padCenter(text: string, width: number): string {
  if (text.length >= width) return text.substring(0, width);
  const leftPadding = Math.floor((width - text.length) / 2);
  const rightPadding = width - text.length - leftPadding;
  return ' '.repeat(leftPadding) + text + ' '.repeat(rightPadding);
}

/** Alinea dos textos a los extremos de una línea: izquierda y derecha */
export function twoColumns(left: string, right: string, width: number): string {
  const availableLeft = width - right.length - 1;
  const truncatedLeft = left.length > availableLeft ? left.substring(0, availableLeft) : left;
  const spaces = width - truncatedLeft.length - right.length;
  return truncatedLeft + ' '.repeat(Math.max(1, spaces)) + right;
}

/**
 * Formatea el ticket de venta completo como texto monoespaciado (42 columnas por defecto).
 * Replica el diseño idéntico al ticket impreso de Soft Restaurant V9.5 PRO para Kiwi.
 */
export function formatTicketText(data: TicketPrintData, width: number = 42): string {
  const divider = '='.repeat(width);
  const out: string[] = [];

  // 1. Encabezado corporativo centrado
  const brand = data.brandName || DEFAULT_KIWI_BRAND;
  const business = data.businessName || DEFAULT_KIWI_BUSINESS;
  const rfc = data.rfc || DEFAULT_KIWI_RFC;

  out.push(padCenter(brand, width));
  out.push(padCenter(business, width));
  out.push(padCenter(rfc, width));

  // Dirección fiscal y sucursal
  const address = data.fiscalAddress || DEFAULT_KIWI_ADDRESS;
  wrapText(address, width).forEach((line) => out.push(padCenter(line, width)));

  const branch = data.branchAddress || DEFAULT_KIWI_BRANCH;
  wrapText(branch, width).forEach((line) => out.push(padCenter(line, width)));

  out.push(divider);

  // 2. Metadatos de la orden y entrega
  out.push(padCenter(`FOLIO:${data.folio}`, width));
  out.push(`REPARTIDOR:${data.driverName ? ` ${data.driverName}` : ''}`);

  const orderStr = `ORDEN:${data.orderNumber ?? data.folio}`;
  const dateStr = data.createdAt;
  out.push(twoColumns(orderStr, dateStr, width));

  const clientName = (data.customerName || 'PUBLICO GENERAL').toUpperCase();
  out.push(`CLIENTE:${clientName}`);

  if (data.customerPhone) {
    out.push(`TEL.:${data.customerPhone}`);
  }

  // Zona / Servicio (ej. "J COL. KIWI PASAN POR EL  ZONA:PASA POR EL")
  const colPart = data.colonia ? `COL. ${data.colonia.toUpperCase()} ` : '';
  const zonaPart = data.zone ? `ZONA:${data.zone.toUpperCase()}` : `ZONA:${(data.serviceTypeLabel || 'MOSTRADOR').toUpperCase()}`;
  const deliveryLine = `${colPart}${zonaPart}`.trim();
  if (deliveryLine) {
    wrapText(deliveryLine, width).forEach((line) => out.push(line));
  }

  out.push(divider);

  // 3. Encabezado de la tabla de productos
  // Formato: "CANT.DESCRIPCION                   IMPORTE"
  const colCantW = 5;
  const colImporteW = 10;
  const colDescW = width - colCantW - colImporteW;
  out.push('CANT.DESCRIPCION' + ' '.repeat(Math.max(1, width - 16 - 7)) + 'IMPORTE');

  // 4. Detalle de productos
  for (const line of data.lines) {
    const cantStr = line.quantity.toString().padEnd(colCantW);
    const importeStr = formatReceiptMoney(line.totalCents).padStart(colImporteW);
    const desc = line.productName.toUpperCase();

    if (desc.length <= colDescW) {
      out.push(cantStr + desc.padEnd(colDescW) + importeStr);
    } else {
      // Si el nombre no cabe en una sola línea, envolver
      const wrapped = wrapText(desc, colDescW);
      out.push(cantStr + wrapped[0].padEnd(colDescW) + importeStr);
      for (let i = 1; i < wrapped.length; i++) {
        out.push(' '.repeat(colCantW) + wrapped[i]);
      }
    }

    // Modificadores / Extras (ej. "CHILE JALAPEÑO EXTRA", "POLLO EXTRA")
    if (line.modifiers && line.modifiers.length > 0) {
      for (const mod of line.modifiers) {
        wrapText(`+ ${mod.toUpperCase()}`, width - colCantW).forEach((modLine) => {
          out.push(' '.repeat(colCantW) + modLine);
        });
      }
    }

    // Nota de la línea si existe
    if (line.lineNotes) {
      wrapText(`* ${line.lineNotes}`, width - colCantW).forEach((noteLine) => {
        out.push(' '.repeat(colCantW) + noteLine);
      });
    }
  }

  out.push('');

  // 5. Totales y desglose impositivo
  // En México el IVA es 16%. Si no vienen explícitos, calcular subtotal = total / 1.16
  const totalCents = data.totalCents;
  const subtotalCents = data.subtotalCents ?? Math.round(totalCents / 1.16);
  const taxCents = data.taxCents ?? (totalCents - subtotalCents);

  out.push(twoColumns('SUBTOTAL:', formatReceiptMoney(subtotalCents), width));
  out.push(twoColumns('IVA:', formatReceiptMoney(taxCents), width));
  out.push(twoColumns('TOTAL:', formatReceiptMoney(totalCents), width));

  // 6. Importe con letra
  const textoImporte = numberToWordsMxn(totalCents);
  wrapText(textoImporte, width).forEach((line) => out.push(line));

  out.push('');

  // 7. Cobro y cambio (si aplica)
  if (data.cashTender) {
    const recibidoStr = formatReceiptMoney(data.cashTender.receivedCents);
    const cambioStr = formatReceiptMoney(data.cashTender.changeCents);
    out.push(twoColumns('CANTIDAD A RECIBIR:', recibidoStr, width));
    out.push(twoColumns('CAMBIO REPARTIDOR:', cambioStr, width));
    out.push('');
  }

  // 8. Pie de ticket
  const defaultFooters = [
    'GRACIAS POR SU PREFERENCIA',
    'ESTE NO ES UN COMPROBANTE FISCAL',
    'FACTURA VIGENCIA: ULTIMO DIA DEL MES',
    '*** RESTAURANTOS - KIWI ***',
  ];
  const footers = data.footerNotes && data.footerNotes.length > 0 ? data.footerNotes : defaultFooters;
  for (const footer of footers) {
    out.push(padCenter(footer, width));
  }

  return out.join('\n');
}

/**
 * Formatea la comanda para cocina (sin precios ni datos fiscales, con énfasis en tareas y notas).
 */
export function formatKitchenText(data: KitchenPrintData, width: number = 42): string {
  const divider = '-'.repeat(width);
  const out: string[] = [];

  out.push(padCenter('*** COMANDA DE COCINA ***', width));
  if (data.station) {
    out.push(padCenter(`ESTACION: ${data.station.toUpperCase()}`, width));
  }

  const orderStr = `ORDEN:#${data.orderNumber ?? data.folio}`;
  out.push(twoColumns(orderStr, `FOLIO:${data.folio}`, width));
  out.push(twoColumns(`FECHA:${data.createdAt}`, (data.serviceTypeLabel || 'MOSTRADOR').toUpperCase(), width));

  if (data.customerName) {
    out.push(`CLIENTE: ${data.customerName.toUpperCase()}`);
  }
  if (data.driverName) {
    out.push(`REPARTIDOR: ${data.driverName.toUpperCase()}`);
  }

  out.push(divider);

  // Lista clara y prominente de preparación
  for (const line of data.lines) {
    out.push(`[ ${line.quantity} ] ${line.productName.toUpperCase()}`);

    if (line.modifiers && line.modifiers.length > 0) {
      for (const mod of line.modifiers) {
        out.push(`    >> ${mod.toUpperCase()}`);
      }
    }

    if (line.lineNotes) {
      out.push(`    * NOTA: ${line.lineNotes.toUpperCase()}`);
    }
  }

  if (data.orderNotes) {
    out.push(divider);
    out.push('NOTAS DEL PEDIDO:');
    wrapText(data.orderNotes.toUpperCase(), width).forEach((l) => out.push(l));
  }

  out.push(divider);
  out.push(padCenter('RESTAURANTOS KITCHEN', width));

  return out.join('\n');
}

/**
 * Comandos de control estándar ESC/POS para impresoras térmicas (Epson, Bixolon, Xprinter).
 */
export const ESCPOS = {
  INIT: new Uint8Array([0x1b, 0x40]), // ESC @
  ALIGN_LEFT: new Uint8Array([0x1b, 0x61, 0x00]), // ESC a 0
  ALIGN_CENTER: new Uint8Array([0x1b, 0x61, 0x01]), // ESC a 1
  ALIGN_RIGHT: new Uint8Array([0x1b, 0x61, 0x02]), // ESC a 2
  BOLD_ON: new Uint8Array([0x1b, 0x45, 0x01]), // ESC E 1
  BOLD_OFF: new Uint8Array([0x1b, 0x45, 0x00]), // ESC E 0
  CUT_FULL: new Uint8Array([0x1d, 0x56, 0x41, 0x03]), // GS V 65 3 (alimentar y corte total)
  CUT_PARTIAL: new Uint8Array([0x1d, 0x56, 0x42, 0x03]), // GS V 66 3 (alimentar y corte parcial)
  KICK_DRAWER: new Uint8Array([0x1b, 0x70, 0x00, 0x19, 0xfa]), // ESC p 0 25 250 (pulso al cajón de dinero pin 2)
  FEED_LINES: (n: number) => new Uint8Array([0x1b, 0x64, n]), // ESC d n
};

/**
 * Genera el flujo binario completo ESC/POS para enviar a impresora térmica directa.
 */
export function generateEscPosTicket(data: TicketPrintData, kickDrawer: boolean = false): Uint8Array {
  const text = formatTicketText(data, 42);
  const encoder = new TextEncoder();
  const textBytes = encoder.encode(text + '\n\n\n');

  const parts: Uint8Array[] = [ESCPOS.INIT];

  if (kickDrawer) {
    parts.push(ESCPOS.KICK_DRAWER);
  }

  parts.push(textBytes);
  parts.push(ESCPOS.FEED_LINES(3));
  parts.push(ESCPOS.CUT_PARTIAL);

  const totalLength = parts.reduce((acc, p) => acc + p.length, 0);
  const buffer = new Uint8Array(totalLength);
  let offset = 0;
  for (const part of parts) {
    buffer.set(part, offset);
    offset += part.length;
  }
  return buffer;
}

/**
 * Genera el flujo binario completo ESC/POS para comanda de cocina.
 */
export function generateEscPosKitchen(data: KitchenPrintData): Uint8Array {
  const text = formatKitchenText(data, 42);
  const encoder = new TextEncoder();
  const textBytes = encoder.encode(text + '\n\n\n');

  const parts: Uint8Array[] = [
    ESCPOS.INIT,
    textBytes,
    ESCPOS.FEED_LINES(3),
    ESCPOS.CUT_FULL,
  ];

  const totalLength = parts.reduce((acc, p) => acc + p.length, 0);
  const buffer = new Uint8Array(totalLength);
  let offset = 0;
  for (const part of parts) {
    buffer.set(part, offset);
    offset += part.length;
  }
  return buffer;
}
