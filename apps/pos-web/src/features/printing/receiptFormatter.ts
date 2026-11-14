/**
 * Generador y formateador de tickets de venta y comandas de cocina térmicas.
 * Replica fielmente el formato Soft Restaurant V9.5 PRO para Kiwi Comida Natural,
 * con soporte para ancho configurable (40 o 42 columnas) y comandos directos ESC/POS.
 */

import { numberToWordsMxn } from './numberToWordsMxn';

export interface ReceiptLine {
  productId?: string | null;
  sku?: string | null;
  categoryId?: string | null;
  categoryName?: string | null;
  quantity: number;
  productName: string;
  unitPriceCents?: number;
  totalCents: number;
  modifiers?: string[];
  lineNotes?: string | null;
  station?: string | null;
  printArea?: string | null;
  printAreaName?: string | null;
}

export interface PrintAreaDefinition {
  code: string;
  name: string;
  station: 'kitchen' | 'drinks' | 'packing';
  printComanda: boolean;
  sortOrder: number;
  isSystem?: boolean;
}

export interface PrintRoutingLookup {
  areas?: PrintAreaDefinition[];
  productAreas?: Record<string, string>;
  categoryAreas?: Record<string, string>;
}

export const DEFAULT_PRINT_AREAS: PrintAreaDefinition[] = [
  {
    code: 'salads',
    name: 'ENSALADAS',
    station: 'kitchen',
    printComanda: true,
    sortOrder: 1,
    isSystem: true,
  },
  {
    code: 'baguettes',
    name: 'BAGUETTES(RAPIDO)',
    station: 'kitchen',
    printComanda: true,
    sortOrder: 2,
    isSystem: true,
  },
  {
    code: 'kitchen',
    name: 'BARRA / CALIENTE',
    station: 'kitchen',
    printComanda: true,
    sortOrder: 3,
    isSystem: true,
  },
  {
    code: 'drinks',
    name: 'BEBIDAS (BARRA / FUENTES)',
    station: 'drinks',
    printComanda: true,
    sortOrder: 4,
    isSystem: true,
  },
  {
    code: 'packing',
    name: 'EMPAQUE',
    station: 'packing',
    printComanda: false,
    sortOrder: 5,
    isSystem: true,
  },
  {
    code: 'none',
    name: 'SIN IMPRESION',
    station: 'packing',
    printComanda: false,
    sortOrder: 6,
    isSystem: true,
  },
];

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
  areaCode?: string | null;
  areaName?: string | null;
  lines: ReceiptLine[];
}

const BAGUETTE_BARRA_KEYWORDS = [
  'BAGUETTE',
  'SANDWICH',
  'CUERNITO',
  'PANINI',
  'TORTA',
  'WRAP',
  'SOPA',
  'CREMA',
  'TOSTADA',
  'QUESADILLA',
];

const DRINK_KEYWORDS = [
  'AGUA',
  'JUGO',
  'LICUADO',
  'CAFE',
  'TE ',
  'REFRESCO',
  'BEBIDA',
  'SMOOTHIE',
  'FRAPPE',
  'LIMONADA',
];

const PACKING_KEYWORDS = ['CUBIERTO', 'SERVILLETA', 'BOLSA', 'EMPAQUE'];

/**
 * Extrae el número corto de orden diaria a partir del folio o orderNumber.
 * Ej.: "SUC04-000001" -> "1", "SUC04-000003" -> "3", orderNumber=68 -> "68".
 */
export function extractShortOrderNumber(
  folio?: string | null,
  orderNumber?: string | number | null
): string {
  if (orderNumber !== undefined && orderNumber !== null && String(orderNumber).trim() !== '') {
    const rawOrder = String(orderNumber).trim();
    if (rawOrder !== String(folio || '').trim()) {
      return rawOrder;
    }
  }
  const rawFolio = String(folio || '').trim();
  if (!rawFolio) return '1';
  if (rawFolio.includes('-')) {
    const suffix = rawFolio.split('-').pop()?.trim() || '';
    if (/^\d+$/.test(suffix)) {
      return String(parseInt(suffix, 10));
    }
    const digits = suffix.replace(/\D+/g, '');
    if (digits) return String(parseInt(digits, 10));
  }
  if (/^\d+$/.test(rawFolio)) {
    return String(parseInt(rawFolio, 10));
  }
  return rawFolio;
}

export function normalizePrintAreas(
  rawAreas?: ReadonlyArray<
    Partial<PrintAreaDefinition> & { print_comanda?: unknown; sort_order?: unknown }
  > | null
): PrintAreaDefinition[] {
  const byCode = new Map<string, PrintAreaDefinition>();
  for (const area of DEFAULT_PRINT_AREAS) {
    byCode.set(area.code, { ...area });
  }
  if (Array.isArray(rawAreas)) {
    rawAreas.forEach((item, idx) => {
      if (!item || typeof item !== 'object') return;
      const code = String(item.code || '').trim().toLowerCase();
      const name = String(item.name || '').trim().toUpperCase();
      if (!code || !name) return;
      const rawStation = String(item.station || 'kitchen').trim().toLowerCase();
      const station: 'kitchen' | 'drinks' | 'packing' =
        rawStation === 'drinks' || rawStation === 'packing' ? rawStation : 'kitchen';
      const existing = byCode.get(code);
      const printComandaRaw =
        item.printComanda !== undefined
          ? item.printComanda
          : item.print_comanda !== undefined
            ? item.print_comanda
            : existing?.printComanda ?? (code !== 'packing' && code !== 'none');
      const sortOrderRaw =
        item.sortOrder ?? item.sort_order ?? existing?.sortOrder ?? idx + 1;
      byCode.set(code, {
        code,
        name,
        station,
        printComanda: Boolean(printComandaRaw),
        sortOrder: Number(sortOrderRaw) || idx + 1,
        isSystem: Boolean(existing?.isSystem),
      });
    });
  }
  return Array.from(byCode.values()).sort(
    (a, b) => a.sortOrder - b.sortOrder || a.code.localeCompare(b.code)
  );
}

export function resolveProductPrintArea(
  line: Partial<ReceiptLine>,
  routing?: PrintRoutingLookup | null
): string {
  const areas = normalizePrintAreas(routing?.areas);
  const validCodes = new Set(areas.map((a) => a.code));

  const explicit = String(line.printArea || '').trim().toLowerCase();
  if (explicit && validCodes.has(explicit)) {
    return explicit;
  }

  const productAreas = routing?.productAreas || {};
  for (const keyCandidate of [line.productId, line.sku, line.productName]) {
    const key = String(keyCandidate || '').trim();
    if (key && productAreas[key]) {
      const mapped = String(productAreas[key]).trim().toLowerCase();
      if (validCodes.has(mapped)) return mapped;
    }
  }

  const categoryAreas = routing?.categoryAreas || {};
  for (const catCandidate of [line.categoryId, line.categoryName]) {
    const cat = String(catCandidate || '').trim();
    if (cat) {
      for (const variant of [cat, cat.toUpperCase()]) {
        if (categoryAreas[variant]) {
          const mapped = String(categoryAreas[variant]).trim().toLowerCase();
          if (validCodes.has(mapped)) return mapped;
        }
      }
    }
  }

  const stationRaw = String(line.station || '').trim().toLowerCase();
  if (
    stationRaw &&
    validCodes.has(stationRaw) &&
    stationRaw !== 'kitchen' &&
    stationRaw !== 'drinks' &&
    stationRaw !== 'packing'
  ) {
    return stationRaw;
  }

  const nameUpper = String(line.productName || '').trim().toUpperCase();
  const catUpper = String(line.categoryName || '').trim().toUpperCase();
  const combined = `${catUpper} ${nameUpper}`;

  if (combined.includes('ENSALADA') && validCodes.has('salads')) {
    return 'salads';
  }
  if (
    BAGUETTE_BARRA_KEYWORDS.some((kw) => combined.includes(kw)) &&
    validCodes.has('baguettes')
  ) {
    return 'baguettes';
  }
  if (
    (stationRaw === 'drinks' || DRINK_KEYWORDS.some((kw) => combined.includes(kw))) &&
    validCodes.has('drinks')
  ) {
    return 'drinks';
  }
  if (
    (stationRaw === 'packing' || PACKING_KEYWORDS.some((kw) => combined.includes(kw))) &&
    validCodes.has('packing')
  ) {
    return 'packing';
  }
  if (stationRaw && validCodes.has(stationRaw)) {
    return stationRaw;
  }
  return 'kitchen';
}

/**
 * Divide una comanda general en múltiples comandas independientes por Área de Impresión
 * (ej. una para ENSALADAS, otra para BAGUETTES(RAPIDO), otra para BEBIDAS), omitiendo
 * las áreas marcadas con printComanda = false (como EMPAQUE o SIN IMPRESION).
 */
export function splitKitchenDataByArea(
  data: KitchenPrintData,
  routing?: PrintRoutingLookup | null,
  includeNonPrinting: boolean = false
): KitchenPrintData[] {
  const areas = normalizePrintAreas(routing?.areas);
  const areaMap = new Map(areas.map((a) => [a.code, a]));

  const grouped = new Map<string, ReceiptLine[]>();
  for (const line of data.lines || []) {
    const areaCode = resolveProductPrintArea(line, routing);
    const areaInfo = areaMap.get(areaCode) || {
      code: areaCode,
      name: areaCode.toUpperCase(),
      station: 'kitchen' as const,
      printComanda: true,
      sortOrder: 99,
    };
    if (!includeNonPrinting && !areaInfo.printComanda) {
      continue;
    }
    const enrichedLine: ReceiptLine = {
      ...line,
      printArea: areaCode,
      printAreaName: areaInfo.name,
    };
    const list = grouped.get(areaCode) || [];
    list.push(enrichedLine);
    grouped.set(areaCode, list);
  }

  const orderedCodes = Array.from(grouped.keys()).sort((a, b) => {
    const sortA = areaMap.get(a)?.sortOrder ?? 99;
    const sortB = areaMap.get(b)?.sortOrder ?? 99;
    return sortA - sortB || a.localeCompare(b);
  });

  const shortOrder = extractShortOrderNumber(data.folio, data.orderNumber);
  return orderedCodes.map((areaCode) => {
    const areaInfo = areaMap.get(areaCode);
    const areaName = areaInfo?.name || areaCode.toUpperCase();
    return {
      ...data,
      orderNumber: shortOrder,
      areaCode,
      areaName,
      station: areaName,
      lines: grouped.get(areaCode) || [],
    };
  });
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

  const shortOrder = extractShortOrderNumber(data.folio, data.orderNumber);
  const orderStr = `ORDEN:${shortOrder}`;
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
 * Formatea la comanda para cocina (sin precios ni datos fiscales, con énfasis en área, tareas y notas).
 */
export function formatKitchenText(data: KitchenPrintData, width: number = 42): string {
  const divider = '-'.repeat(width);
  const out: string[] = [];

  const shortOrder = extractShortOrderNumber(data.folio, data.orderNumber);
  const areaLabel = String(data.areaName || data.station || '').trim().toUpperCase();

  out.push(padCenter('*** COMANDA DE COCINA ***', width));
  if (areaLabel) {
    out.push(padCenter(`${areaLabel} ORDEN: ${shortOrder}`, width));
    out.push(padCenter(`ESTACION: ${areaLabel}`, width));
  }

  const orderStr = `ORDEN:#${shortOrder}`;
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
  CUT_FULL: new Uint8Array([0x1d, 0x56, 0x41, 0x01]), // GS V 65 1 (alimentación mínima y corte total)
  CUT_PARTIAL: new Uint8Array([0x1d, 0x56, 0x42, 0x01]), // GS V 66 1 (alimentación mínima y corte parcial)
  KICK_DRAWER: new Uint8Array([0x1b, 0x70, 0x00, 0x19, 0xfa]), // ESC p 0 25 250 (pulso al cajón de dinero pin 2)
  FEED_LINES: (n: number) => new Uint8Array([0x1b, 0x64, n]), // ESC d n
};

/**
 * Genera el flujo binario completo ESC/POS para enviar a impresora térmica directa.
 */
export function generateEscPosTicket(data: TicketPrintData, kickDrawer: boolean = false): Uint8Array {
  const text = formatTicketText(data, 42);
  const encoder = new TextEncoder();
  const textBytes = encoder.encode(text + '\n\n');

  const parts: Uint8Array[] = [ESCPOS.INIT];

  if (kickDrawer) {
    parts.push(ESCPOS.KICK_DRAWER);
  }

  parts.push(textBytes);
  parts.push(ESCPOS.FEED_LINES(1));
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
  const textBytes = encoder.encode(text + '\n\n');

  const parts: Uint8Array[] = [
    ESCPOS.INIT,
    textBytes,
    ESCPOS.FEED_LINES(1),
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
