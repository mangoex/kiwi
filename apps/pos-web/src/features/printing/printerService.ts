import {
  DEFAULT_PRINT_AREAS,
  formatTicketText,
  formatKitchenText,
  generateEscPosTicket,
  generateEscPosKitchen,
  normalizePrintAreas,
  splitKitchenDataByArea,
  type TicketPrintData,
  type KitchenPrintData,
  type PrintAreaDefinition,
} from './receiptFormatter';

export type AutoPrintCopies = 'both' | 'ticket' | 'kitchen';
export type PrinterConnectionMode = 'network_bridge' | 'browser_silent';

export interface AreaPrinterTarget {
  enabled: boolean;
  printerName: string;
  host: string;
  port: number;
}

export interface PosPrinterConfig {
  autoPrintOnConfirm: boolean;
  autoPrintCopies: AutoPrintCopies;
  kickDrawerOnCash: boolean;
  connectionMode: PrinterConnectionMode;
  bridgeUrl: string;
  ticketPrinterName: string;
  ticketPrinterHost: string;
  ticketPrinterPort: number;
  kitchenPrinterName: string;
  kitchenPrinterHost: string;
  kitchenPrinterPort: number;
  paperWidthMm: 80 | 58;
  printAreas: PrintAreaDefinition[];
  productPrintAreas: Record<string, string>;
  categoryPrintAreas: Record<string, string>;
  areaPrinters: Record<string, AreaPrinterTarget>;
}

export const PRINTER_CONFIG_STORAGE_KEY = 'pos_printer_config_v1';

export const DEFAULT_AREA_PRINTERS: Record<string, AreaPrinterTarget> = {
  salads: { enabled: true, printerName: 'ensaladas', host: '', port: 9100 },
  baguettes: { enabled: true, printerName: 'barra', host: '', port: 9100 },
  kitchen: { enabled: true, printerName: 'barra', host: '', port: 9100 },
  drinks: { enabled: true, printerName: 'bebidas', host: '', port: 9100 },
  packing: { enabled: false, printerName: '', host: '', port: 9100 },
  none: { enabled: false, printerName: '', host: '', port: 9100 },
};

export const DEFAULT_PRINTER_CONFIG: PosPrinterConfig = {
  autoPrintOnConfirm: true,
  autoPrintCopies: 'both',
  kickDrawerOnCash: true,
  connectionMode: 'network_bridge',
  bridgeUrl: 'http://127.0.0.1:9123',
  ticketPrinterName: 'caja',
  ticketPrinterHost: '',
  ticketPrinterPort: 9100,
  kitchenPrinterName: 'barra',
  kitchenPrinterHost: '',
  kitchenPrinterPort: 9100,
  paperWidthMm: 80,
  printAreas: DEFAULT_PRINT_AREAS.map((a) => ({ ...a })),
  productPrintAreas: {},
  categoryPrintAreas: {},
  areaPrinters: {
    salads: { ...DEFAULT_AREA_PRINTERS.salads },
    baguettes: { ...DEFAULT_AREA_PRINTERS.baguettes },
    kitchen: { ...DEFAULT_AREA_PRINTERS.kitchen },
    drinks: { ...DEFAULT_AREA_PRINTERS.drinks },
    packing: { ...DEFAULT_AREA_PRINTERS.packing },
    none: { ...DEFAULT_AREA_PRINTERS.none },
  },
};

function normalizeAreaPrinters(
  areas: PrintAreaDefinition[],
  rawAreaPrinters?: Record<string, Partial<AreaPrinterTarget> & { printer_name?: string }> | null
): Record<string, AreaPrinterTarget> {
  const out: Record<string, AreaPrinterTarget> = {};
  const source = rawAreaPrinters && typeof rawAreaPrinters === 'object' ? rawAreaPrinters : {};
  for (const area of areas) {
    const fallback = DEFAULT_AREA_PRINTERS[area.code] || {
      enabled: area.printComanda,
      printerName: area.printComanda ? area.code : '',
      host: '',
      port: 9100,
    };
    const item = source[area.code] || {};
    const rawPrinterName =
      item.printerName !== undefined
        ? item.printerName
        : item.printer_name !== undefined
          ? item.printer_name
          : fallback.printerName;
    const rawPort = Number(item.port);
    out[area.code] = {
      enabled: typeof item.enabled === 'boolean' ? item.enabled : fallback.enabled,
      printerName: typeof rawPrinterName === 'string' ? rawPrinterName.trim() : fallback.printerName,
      host: typeof item.host === 'string' ? item.host.trim() : fallback.host,
      port: Number.isFinite(rawPort) && rawPort >= 1 && rawPort <= 65535 ? Math.trunc(rawPort) : fallback.port,
    };
  }
  return out;
}

export function loadPrinterConfig(storage?: Pick<Storage, 'getItem'> | null): PosPrinterConfig {
  const targetStorage =
    storage !== undefined
      ? storage
      : typeof window !== 'undefined' && window.localStorage
        ? window.localStorage
        : null;

  if (!targetStorage) {
    return {
      ...DEFAULT_PRINTER_CONFIG,
      printAreas: DEFAULT_PRINT_AREAS.map((a) => ({ ...a })),
      areaPrinters: normalizeAreaPrinters(DEFAULT_PRINT_AREAS, null),
    };
  }

  try {
    const raw = targetStorage.getItem(PRINTER_CONFIG_STORAGE_KEY);
    if (!raw) {
      return {
        ...DEFAULT_PRINTER_CONFIG,
        printAreas: DEFAULT_PRINT_AREAS.map((a) => ({ ...a })),
        areaPrinters: normalizeAreaPrinters(DEFAULT_PRINT_AREAS, null),
      };
    }
    const parsed = JSON.parse(raw) as Partial<PosPrinterConfig> & Record<string, unknown>;
    const normalizedAreas = normalizePrintAreas(
      parsed.printAreas as Array<Partial<PrintAreaDefinition> & Record<string, unknown>> | undefined
    );
    const productPrintAreas: Record<string, string> = {};
    if (parsed.productPrintAreas && typeof parsed.productPrintAreas === 'object') {
      for (const [k, v] of Object.entries(parsed.productPrintAreas)) {
        if (typeof v === 'string' && v.trim()) {
          productPrintAreas[k.trim()] = v.trim().toLowerCase();
        }
      }
    }
    const categoryPrintAreas: Record<string, string> = {};
    if (parsed.categoryPrintAreas && typeof parsed.categoryPrintAreas === 'object') {
      for (const [k, v] of Object.entries(parsed.categoryPrintAreas)) {
        if (typeof v === 'string' && v.trim()) {
          categoryPrintAreas[k.trim()] = v.trim().toLowerCase();
        }
      }
    }

    return {
      autoPrintOnConfirm:
        typeof parsed.autoPrintOnConfirm === 'boolean'
          ? parsed.autoPrintOnConfirm
          : DEFAULT_PRINTER_CONFIG.autoPrintOnConfirm,
      autoPrintCopies:
        parsed.autoPrintCopies === 'both' ||
        parsed.autoPrintCopies === 'ticket' ||
        parsed.autoPrintCopies === 'kitchen'
          ? parsed.autoPrintCopies
          : DEFAULT_PRINTER_CONFIG.autoPrintCopies,
      kickDrawerOnCash:
        typeof parsed.kickDrawerOnCash === 'boolean'
          ? parsed.kickDrawerOnCash
          : DEFAULT_PRINTER_CONFIG.kickDrawerOnCash,
      connectionMode:
        parsed.connectionMode === 'network_bridge' || parsed.connectionMode === 'browser_silent'
          ? parsed.connectionMode
          : DEFAULT_PRINTER_CONFIG.connectionMode,
      bridgeUrl:
        typeof parsed.bridgeUrl === 'string' && parsed.bridgeUrl.trim()
          ? parsed.bridgeUrl.trim()
          : DEFAULT_PRINTER_CONFIG.bridgeUrl,
      ticketPrinterName:
        typeof parsed.ticketPrinterName === 'string'
          ? parsed.ticketPrinterName.trim()
          : DEFAULT_PRINTER_CONFIG.ticketPrinterName,
      ticketPrinterHost:
        typeof parsed.ticketPrinterHost === 'string' ? parsed.ticketPrinterHost.trim() : '',
      ticketPrinterPort:
        typeof parsed.ticketPrinterPort === 'number' &&
        parsed.ticketPrinterPort >= 1 &&
        parsed.ticketPrinterPort <= 65535
          ? Math.trunc(parsed.ticketPrinterPort)
          : 9100,
      kitchenPrinterName:
        typeof parsed.kitchenPrinterName === 'string'
          ? parsed.kitchenPrinterName.trim()
          : DEFAULT_PRINTER_CONFIG.kitchenPrinterName,
      kitchenPrinterHost:
        typeof parsed.kitchenPrinterHost === 'string' ? parsed.kitchenPrinterHost.trim() : '',
      kitchenPrinterPort:
        typeof parsed.kitchenPrinterPort === 'number' &&
        parsed.kitchenPrinterPort >= 1 &&
        parsed.kitchenPrinterPort <= 65535
          ? Math.trunc(parsed.kitchenPrinterPort)
          : 9100,
      paperWidthMm: parsed.paperWidthMm === 58 ? 58 : 80,
      printAreas: normalizedAreas,
      productPrintAreas,
      categoryPrintAreas,
      areaPrinters: normalizeAreaPrinters(
        normalizedAreas,
        parsed.areaPrinters as Record<string, Partial<AreaPrinterTarget>> | undefined
      ),
    };
  } catch {
    return {
      ...DEFAULT_PRINTER_CONFIG,
      printAreas: DEFAULT_PRINT_AREAS.map((a) => ({ ...a })),
      areaPrinters: normalizeAreaPrinters(DEFAULT_PRINT_AREAS, null),
    };
  }
}

export function savePrinterConfig(
  config: PosPrinterConfig,
  storage?: Pick<Storage, 'setItem'> | null
): PosPrinterConfig {
  const normalizedAreas = normalizePrintAreas(config.printAreas);
  const normalized: PosPrinterConfig = {
    ...DEFAULT_PRINTER_CONFIG,
    ...config,
    bridgeUrl: (config.bridgeUrl || DEFAULT_PRINTER_CONFIG.bridgeUrl).trim(),
    ticketPrinterName:
      config.ticketPrinterName !== undefined
        ? String(config.ticketPrinterName).trim()
        : DEFAULT_PRINTER_CONFIG.ticketPrinterName,
    ticketPrinterHost: (config.ticketPrinterHost || '').trim(),
    ticketPrinterPort:
      Number.isFinite(config.ticketPrinterPort) &&
      config.ticketPrinterPort >= 1 &&
      config.ticketPrinterPort <= 65535
        ? Math.trunc(config.ticketPrinterPort)
        : 9100,
    kitchenPrinterName:
      config.kitchenPrinterName !== undefined
        ? String(config.kitchenPrinterName).trim()
        : DEFAULT_PRINTER_CONFIG.kitchenPrinterName,
    kitchenPrinterHost: (config.kitchenPrinterHost || '').trim(),
    kitchenPrinterPort:
      Number.isFinite(config.kitchenPrinterPort) &&
      config.kitchenPrinterPort >= 1 &&
      config.kitchenPrinterPort <= 65535
        ? Math.trunc(config.kitchenPrinterPort)
        : 9100,
    paperWidthMm: config.paperWidthMm === 58 ? 58 : 80,
    printAreas: normalizedAreas,
    productPrintAreas: { ...(config.productPrintAreas || {}) },
    categoryPrintAreas: { ...(config.categoryPrintAreas || {}) },
    areaPrinters: normalizeAreaPrinters(normalizedAreas, config.areaPrinters),
  };

  const targetStorage =
    storage !== undefined
      ? storage
      : typeof window !== 'undefined' && window.localStorage
        ? window.localStorage
        : null;

  if (targetStorage) {
    targetStorage.setItem(PRINTER_CONFIG_STORAGE_KEY, JSON.stringify(normalized));
  }
  return normalized;
}

/**
 * Sincroniza la configuración de áreas de impresión y mapeo de impresoras desde el backend (/api/v1/print-routing)
 * hacia localStorage para que el POS y el Admin compartan el catálogo de áreas e impresoras.
 */
export async function syncPrintRoutingFromBackend(
  apiBaseUrl: string = '/api/v1',
  authToken?: string | null
): Promise<PosPrinterConfig> {
  const local = loadPrinterConfig();
  try {
    const headers: Record<string, string> = {};
    if (authToken) {
      headers.Authorization = `Bearer ${authToken}`;
    }
    const res = await fetch(`${apiBaseUrl.replace(/\/+$/, '')}/print-routing`, {
      method: 'GET',
      headers,
    });
    if (!res.ok) return local;
    const remote = (await res.json()) as {
      areas?: Array<Record<string, unknown>>;
      product_areas?: Record<string, string>;
      category_areas?: Record<string, string>;
      ticket_printer?: { printer_name?: string; host?: string; port?: number };
      area_printers?: Record<string, { enabled?: boolean; printer_name?: string; host?: string; port?: number }>;
    };
    const areas = normalizePrintAreas(remote.areas);
    const updated = savePrinterConfig({
      ...local,
      printAreas: areas,
      productPrintAreas: {
        ...local.productPrintAreas,
        ...(remote.product_areas || {}),
      },
      categoryPrintAreas: {
        ...local.categoryPrintAreas,
        ...(remote.category_areas || {}),
      },
      ticketPrinterName:
        remote.ticket_printer?.printer_name !== undefined
          ? String(remote.ticket_printer.printer_name).trim()
          : local.ticketPrinterName,
      ticketPrinterHost: remote.ticket_printer?.host || local.ticketPrinterHost,
      ticketPrinterPort: remote.ticket_printer?.port || local.ticketPrinterPort,
      areaPrinters: normalizeAreaPrinters(areas, remote.area_printers || local.areaPrinters),
    });
    return updated;
  } catch {
    return local;
  }
}

export function uint8ToBase64(bytes: Uint8Array): string {
  if (typeof Buffer !== 'undefined') {
    return Buffer.from(bytes).toString('base64');
  }
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...Array.from(chunk));
  }
  return btoa(binary);
}

export async function checkPrintBridgeHealth(
  bridgeUrl: string = DEFAULT_PRINTER_CONFIG.bridgeUrl
): Promise<{ online: boolean; service?: string; error?: string }> {
  const base = bridgeUrl.replace(/\/+$/, '');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 2000);
  try {
    const response = await fetch(`${base}/health`, {
      method: 'GET',
      signal: controller.signal,
    });
    if (!response.ok) {
      return { online: false, error: `HTTP ${response.status}` };
    }
    const data = (await response.json().catch(() => ({}))) as { service?: string; status?: string };
    return { online: true, service: data.service || data.status || 'kiwi-print-bridge' };
  } catch (err) {
    return {
      online: false,
      error: err instanceof Error ? err.message : 'Puente local no disponible',
    };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Consulta al puente local (GET /printers) la lista de impresoras instaladas en el
 * Panel de Control de la computadora (Windows / macOS / Linux).
 */
export async function fetchLocalSystemPrinters(
  bridgeUrl: string = DEFAULT_PRINTER_CONFIG.bridgeUrl
): Promise<{ ok: boolean; printers: string[]; defaultPrinter?: string; error?: string }> {
  const base = (bridgeUrl || DEFAULT_PRINTER_CONFIG.bridgeUrl).replace(/\/+$/, '');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(`${base}/printers`, {
      method: 'GET',
      signal: controller.signal,
    });
    if (!response.ok) {
      return { ok: false, printers: [], error: `HTTP ${response.status}` };
    }
    const data = (await response.json().catch(() => ({}))) as {
      ok?: boolean;
      printers?: string[];
      default_printer?: string;
    };
    const list = Array.isArray(data.printers)
      ? data.printers.map((p) => String(p).trim()).filter(Boolean)
      : [];
    return {
      ok: true,
      printers: list,
      defaultPrinter: data.default_printer,
    };
  } catch (err) {
    return {
      ok: false,
      printers: [],
      error:
        err instanceof Error
          ? err.message
          : 'No se pudo consultar la lista de impresoras del sistema.',
    };
  } finally {
    clearTimeout(timer);
  }
}

export async function sendEscPosToBridge(
  bridgeUrl: string,
  host: string,
  port: number,
  payloadBytes: Uint8Array,
  jobKind: string = 'ticket',
  printerName: string = ''
): Promise<{ ok: boolean; message: string }> {
  const base = (bridgeUrl || DEFAULT_PRINTER_CONFIG.bridgeUrl).replace(/\/+$/, '');
  const cleanHost = (host || '').trim();
  const cleanPrinterName = (printerName || '').trim();
  if (!cleanHost && !cleanPrinterName) {
    return {
      ok: false,
      message: 'No se ha configurado nombre de impresora ni dirección IP.',
    };
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 4000);
  try {
    const response = await fetch(`${base}/print`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        printer_name: cleanPrinterName,
        host: cleanHost,
        port: port || 9100,
        job_kind: jobKind,
        data_base64: uint8ToBase64(payloadBytes),
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errBody = (await response.json().catch(() => ({}))) as { error?: string; message?: string };
      return {
        ok: false,
        message:
          errBody.error ||
          errBody.message ||
          `El puente local respondió con código HTTP ${response.status}.`,
      };
    }
    const targetDesc = cleanHost
      ? `${cleanHost}:${port || 9100}`
      : `impresora "${cleanPrinterName}"`;
    return {
      ok: true,
      message: `Impresión ESC/POS enviada a ${targetDesc}`,
    };
  } catch (err) {
    return {
      ok: false,
      message:
        err instanceof Error
          ? `No se pudo contactar el puente local en ${base}: ${err.message}`
          : `No se pudo contactar el puente local en ${base}`,
    };
  } finally {
    clearTimeout(timer);
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Construye el documento HTML aislado para impresión térmica (80mm o 58mm).
 * Calibrado a 7.8pt con white-space: pre para que las 42 columnas quepan exactamente
 * en una sola línea dentro de los 72mm imprimibles sin partirse en la columna 34,
 * y sin desperdiciar papel en blanco al final.
 */
export function buildThermalPrintHtml(pages: string[], paperWidthMm: 80 | 58 = 80): string {
  const contentWidthMm = paperWidthMm === 58 ? 52 : 74;
  const fontSizePt = paperWidthMm === 58 ? '6.5pt' : '7.8pt';
  const sheetsHtml = pages
    .map(
      (pageText, idx) =>
        `<pre class="thermal-sheet${idx < pages.length - 1 ? ' page-break' : ''}">${escapeHtml(pageText.trimEnd())}</pre>`
    )
    .join('\n');

  return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Ticket Térmico Kiwi</title>
  <style>
    @page {
      size: ${paperWidthMm}mm auto;
      margin: 0mm;
    }
    * {
      box-sizing: border-box;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    html, body {
      margin: 0 !important;
      padding: 0 !important;
      width: ${contentWidthMm}mm;
      background: #ffffff !important;
      color: #000000 !important;
      font-family: 'Courier New', Consolas, 'Liberation Mono', Courier, monospace;
      font-size: ${fontSizePt};
      line-height: 1.15;
    }
    .thermal-sheet {
      margin: 0;
      padding: 1.5mm 1mm 2mm 1mm;
      width: ${contentWidthMm}mm;
      white-space: pre;
      overflow-x: hidden;
      font-family: 'Courier New', Consolas, 'Liberation Mono', Courier, monospace;
      font-size: ${fontSizePt};
      line-height: 1.15;
      letter-spacing: -0.1px;
      color: #000000;
      background: #ffffff;
    }
    .page-break {
      page-break-after: always;
      break-after: page;
      border-bottom: 1px dashed #000;
      margin-bottom: 1.5mm;
    }
  </style>
</head>
<body>
${sheetsHtml}
</body>
</html>`;
}

/**
 * Imprime únicamente las hojas térmicas de 80mm/58mm en un iframe aislado
 * para evitar imprimir el layout completo del navegador y permitir corte por copia.
 */
export function printThermalIframe(pages: string[], paperWidthMm: 80 | 58 = 80): boolean {
  if (typeof document === 'undefined' || pages.length === 0) return false;

  const existingFrame = document.getElementById('kiwi-thermal-print-frame');
  if (existingFrame && existingFrame.parentNode) {
    existingFrame.parentNode.removeChild(existingFrame);
  }

  const iframe = document.createElement('iframe');
  iframe.id = 'kiwi-thermal-print-frame';
  iframe.setAttribute('aria-hidden', 'true');
  iframe.style.position = 'fixed';
  iframe.style.right = '0';
  iframe.style.bottom = '0';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = '0';
  iframe.style.opacity = '0';
  iframe.style.pointerEvents = 'none';
  document.body.appendChild(iframe);

  const html = buildThermalPrintHtml(pages, paperWidthMm);
  const frameDoc = iframe.contentWindow?.document || iframe.contentDocument;
  if (!frameDoc || !iframe.contentWindow) {
    window.print();
    return true;
  }

  frameDoc.open();
  frameDoc.write(html);
  frameDoc.close();

  const triggerPrint = () => {
    try {
      iframe.contentWindow?.focus();
      iframe.contentWindow?.print();
    } catch {
      window.print();
    }
  };

  if (frameDoc.readyState === 'complete') {
    setTimeout(triggerPrint, 60);
  } else {
    iframe.onload = () => setTimeout(triggerPrint, 60);
  }

  return true;
}

export interface DispatchPrintOptions {
  ticketData: TicketPrintData;
  kitchenData?: KitchenPrintData | null;
  copies?: AutoPrintCopies;
  targetAreaCode?: string | null;
  kickDrawer?: boolean;
  forceBrowserDialog?: boolean;
  config?: PosPrinterConfig;
}

export interface DispatchPrintResult {
  method: 'network_escpos' | 'browser_iframe' | 'none';
  ok: boolean;
  message: string;
}

export function resolveKitchenJobsForOrder(
  ticketData: TicketPrintData,
  kitchenData?: KitchenPrintData | null,
  config?: PosPrinterConfig,
  targetAreaCode?: string | null
): KitchenPrintData[] {
  const cfg = config || loadPrinterConfig();
  const baseKitchen: KitchenPrintData = kitchenData || {
    folio: ticketData.folio,
    orderNumber: ticketData.orderNumber,
    createdAt: ticketData.createdAt,
    serviceTypeLabel: ticketData.serviceTypeLabel,
    customerName: ticketData.customerName,
    customerPhone: ticketData.customerPhone,
    driverName: ticketData.driverName,
    lines: ticketData.lines,
  };

  // Si ya viene filtrada para un área específica, conservarla
  if (baseKitchen.areaCode && !targetAreaCode) {
    return [baseKitchen];
  }

  const splitJobs = splitKitchenDataByArea(baseKitchen, {
    areas: cfg.printAreas,
    productAreas: cfg.productPrintAreas,
    categoryAreas: cfg.categoryPrintAreas,
  });

  if (targetAreaCode) {
    const filtered = splitJobs.filter((j) => j.areaCode === targetAreaCode);
    if (filtered.length > 0) return filtered;
  }

  if (splitJobs.length > 0) {
    return splitJobs;
  }
  return baseKitchen.lines.length > 0 ? [baseKitchen] : [];
}

function resolvePrinterForArea(
  areaCode: string | null | undefined,
  config: PosPrinterConfig
): { enabled: boolean; printerName: string; host: string; port: number } {
  const code = (areaCode || 'kitchen').trim().toLowerCase();
  const areaTarget = config.areaPrinters?.[code];
  if (areaTarget) {
    if (!areaTarget.enabled) {
      return { enabled: false, printerName: '', host: '', port: 9100 };
    }
    const pName =
      areaTarget.printerName.trim() ||
      config.kitchenPrinterName.trim() ||
      config.ticketPrinterName.trim();
    const pHost =
      areaTarget.host.trim() ||
      config.kitchenPrinterHost.trim() ||
      config.ticketPrinterHost.trim();
    const pPort =
      areaTarget.port ||
      config.kitchenPrinterPort ||
      config.ticketPrinterPort ||
      9100;
    return { enabled: true, printerName: pName, host: pHost, port: pPort };
  }
  return {
    enabled: true,
    printerName: config.kitchenPrinterName.trim() || config.ticketPrinterName.trim(),
    host: config.kitchenPrinterHost.trim() || config.ticketPrinterHost.trim(),
    port: config.kitchenPrinterPort || config.ticketPrinterPort || 9100,
  };
}

export async function dispatchPosPrintJob(
  options: DispatchPrintOptions
): Promise<DispatchPrintResult> {
  const config = options.config || loadPrinterConfig();
  const copies = options.copies || config.autoPrintCopies || 'both';
  const widthCols = config.paperWidthMm === 58 ? 32 : 42;

  const kitchenJobs = resolveKitchenJobsForOrder(
    options.ticketData,
    options.kitchenData,
    config,
    options.targetAreaCode
  );

  const shouldPrintTicket = copies === 'both' || copies === 'ticket';
  const shouldPrintKitchen = copies === 'both' || copies === 'kitchen';
  const kickDrawer = Boolean(options.kickDrawer && config.kickDrawerOnCash);

  // 1. Intentar impresión directa silenciosa por Puente Local (Impresora Windows/OS por nombre o Red TCP 9100)
  const ticketHost = config.ticketPrinterHost.trim();
  const ticketPrinterName = config.ticketPrinterName.trim();
  const hasBridgeTarget = Boolean(ticketHost || ticketPrinterName);

  if (!options.forceBrowserDialog && config.connectionMode === 'network_bridge' && hasBridgeTarget) {
    const results: string[] = [];
    let allSucceeded = true;

    if (shouldPrintTicket) {
      const ticketBytes = generateEscPosTicket(options.ticketData, kickDrawer);
      const res = await sendEscPosToBridge(
        config.bridgeUrl,
        ticketHost,
        config.ticketPrinterPort || 9100,
        ticketBytes,
        'ticket',
        ticketPrinterName
      );
      if (res.ok) {
        const dest = ticketHost
          ? `${ticketHost}:${config.ticketPrinterPort || 9100}`
          : ticketPrinterName;
        results.push(`Ticket -> ${dest}`);
      } else {
        allSucceeded = false;
      }
    }

    if (shouldPrintKitchen && allSucceeded) {
      for (const job of kitchenJobs) {
        const areaCode = job.areaCode || 'kitchen';
        const areaLabel = job.areaName || job.station || areaCode.toUpperCase();
        const target = resolvePrinterForArea(areaCode, config);
        if (!target.enabled) continue;
        if (!target.host && !target.printerName) continue;

        const kitchenBytes = generateEscPosKitchen(job);
        const res = await sendEscPosToBridge(
          config.bridgeUrl,
          target.host,
          target.port,
          kitchenBytes,
          `kitchen:${areaCode}`,
          target.printerName
        );
        if (res.ok) {
          const dest = target.host ? `${target.host}:${target.port}` : target.printerName;
          results.push(`Comanda ${areaLabel} -> ${dest}`);
        } else {
          allSucceeded = false;
          break;
        }
      }
    }

    if (allSucceeded && results.length > 0) {
      return {
        method: 'network_escpos',
        ok: true,
        message: `Impresión directa enviada (${results.join(' · ')})`,
      };
    }
  }

  // 2. Respaldo o modo navegador: impresión térmica aislada de 80mm/58mm en iframe (cada área en su propia hoja con corte)
  const pages: string[] = [];
  if (shouldPrintTicket) {
    pages.push(formatTicketText(options.ticketData, widthCols));
  }
  if (shouldPrintKitchen) {
    for (const job of kitchenJobs) {
      pages.push(formatKitchenText(job, widthCols));
    }
  }

  const printed = printThermalIframe(pages, config.paperWidthMm);
  if (printed) {
    const comandaAreasLabel =
      kitchenJobs.length > 1
        ? `${kitchenJobs.length} Comandas por Área (${kitchenJobs.map((j) => j.areaName || j.areaCode).join(', ')})`
        : 'Comanda de Cocina';
    const label =
      copies === 'both'
        ? `Ticket de Venta y ${comandaAreasLabel}`
        : copies === 'ticket'
          ? 'Ticket de Venta'
          : comandaAreasLabel;
    return {
      method: 'browser_iframe',
      ok: true,
      message: `${label} enviados a impresión térmica (${config.paperWidthMm}mm).`,
    };
  }

  return {
    method: 'none',
    ok: false,
    message: 'No fue posible iniciar la impresión en este dispositivo.',
  };
}

/**
 * Genera el script puente para Windows (.bat con PowerShell + C# Win32 RawPrinterHelper embebido).
 * - GET /health -> estado del servicio
 * - GET /printers -> lista las impresoras instaladas en el Panel de Control de Windows (ej. "caja", "ensaladas", "barra")
 * - POST /print -> envía bytes ESC/POS RAW tanto por nombre de impresora de Windows como por IP:9100
 */
export function buildWindowsPrintBridgeBat(config: PosPrinterConfig): string {
  const defaultHost = config.ticketPrinterHost.trim() || '192.168.1.200';
  const defaultPort = config.ticketPrinterPort || 9100;
  const defaultPrinterName = config.ticketPrinterName.trim() || 'caja';
  const lines = [
    '@echo off',
    'title Puente de Impresion Termica Automatica Kiwi POS (Impresoras Windows + TCP 9100)',
    'color 0A',
    'echo ============================================================================',
    'echo   PUENTE DE IMPRESION TERMICA AUTOMATICA - KIWI RESTAURANTOS',
    'echo   Escuchando en: http://127.0.0.1:9123',
    `echo   Impresora Caja (Windows): ${defaultPrinterName} ^| Red TCP: ${defaultHost}:${defaultPort}`,
    'echo   Soporta impresoras del Panel de Control (caja, ensaladas, barra) e IP:9100',
    'echo   No cierres esta ventana mientras uses el Punto de Venta o Administrador.',
    'echo ============================================================================',
    'echo.',
    '',
    'powershell -NoProfile -ExecutionPolicy Bypass -Command ^',
    '  "$ErrorActionPreference = \'Continue\'; ^',
    '   Add-Type -TypeDefinition \'using System; using System.Runtime.InteropServices; public class RawPrinterHelper { [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)] public class DOCINFOA { [MarshalAs(UnmanagedType.LPStr)] public string pDocName; [MarshalAs(UnmanagedType.LPStr)] public string pOutputFile; [MarshalAs(UnmanagedType.LPStr)] public string pDataType; } [DllImport(\"winspool.Drv\", EntryPoint = \"OpenPrinterA\", SetLastError = true, CharSet = CharSet.Ansi, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool OpenPrinter([MarshalAs(UnmanagedType.LPStr)] string szPrinter, out IntPtr hPrinter, IntPtr pd); [DllImport(\"winspool.Drv\", EntryPoint = \"ClosePrinter\", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool ClosePrinter(IntPtr hPrinter); [DllImport(\"winspool.Drv\", EntryPoint = \"StartDocPrinterA\", SetLastError = true, CharSet = CharSet.Ansi, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool StartDocPrinter(IntPtr hPrinter, Int32 level, [In, MarshalAs(UnmanagedType.LPStruct)] DOCINFOA di); [DllImport(\"winspool.Drv\", EntryPoint = \"EndDocPrinter\", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool EndDocPrinter(IntPtr hPrinter); [DllImport(\"winspool.Drv\", EntryPoint = \"StartPagePrinter\", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool StartPagePrinter(IntPtr hPrinter); [DllImport(\"winspool.Drv\", EntryPoint = \"EndPagePrinter\", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool EndPagePrinter(IntPtr hPrinter); [DllImport(\"winspool.Drv\", EntryPoint = \"WritePrinter\", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool WritePrinter(IntPtr hPrinter, IntPtr pBytes, Int32 dwCount, out Int32 dwWritten); public static bool SendBytesToPrinter(string szPrinterName, byte[] pBytes) { IntPtr hPrinter = IntPtr.Zero; DOCINFOA di = new DOCINFOA(); di.pDocName = \"Kiwi POS RAW Thermal\"; di.pDataType = \"RAW\"; bool bSuccess = false; if (OpenPrinter(szPrinterName.Normalize(), out hPrinter, IntPtr.Zero)) { if (StartDocPrinter(hPrinter, 1, di)) { if (StartPagePrinter(hPrinter)) { IntPtr pUnmanagedBytes = Marshal.AllocCoTaskMem(pBytes.Length); Marshal.Copy(pBytes, 0, pUnmanagedBytes, pBytes.Length); int dwWritten = 0; bSuccess = WritePrinter(hPrinter, pUnmanagedBytes, pBytes.Length, out dwWritten); Marshal.FreeCoTaskMem(pUnmanagedBytes); EndPagePrinter(hPrinter); } EndDocPrinter(hPrinter); } ClosePrinter(hPrinter); } return bSuccess; } }\'; ^',
    '   $crlf = [char]13 + [char]10; ^',
    '   $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 9123); ^',
    '   $listener.Start(); ^',
    '   Write-Host \'[LISTO] Puente activo en http://127.0.0.1:9123 -> soporta impresoras de Windows (caja, ensaladas, barra) e IP:9100.\' -ForegroundColor Green; ^',
    '   while ($true) { ^',
    '     try { ^',
    '       $client = $listener.AcceptTcpClient(); ^',
    '       $stream = $client.GetStream(); ^',
    '       $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8); ^',
    '       $requestLine = $reader.ReadLine(); ^',
    '       if (-not $requestLine) { $client.Close(); continue; } ^',
    '       $parts = $requestLine.Split(\' \'); ^',
    '       $method = $parts[0]; ^',
    '       $path = if ($parts.Length -gt 1) { $parts[1] } else { \'/\' }; ^',
    '       $contentLength = 0; ^',
    '       while ($true) { ^',
    '         $header = $reader.ReadLine(); ^',
    '         if ([string]::IsNullOrEmpty($header)) { break; } ^',
    '         if ($header -match \'^Content-Length:\\s*(\\d+)\') { $contentLength = [int]$matches[1]; } ^',
    '       } ^',
    '       $cors = \'HTTP/1.1 200 OK\' + $crlf + \'Access-Control-Allow-Origin: *\' + $crlf + \'Access-Control-Allow-Methods: GET, POST, OPTIONS\' + $crlf + \'Access-Control-Allow-Headers: Content-Type\' + $crlf + \'Access-Control-Allow-Private-Network: true\' + $crlf + \'Content-Type: application/json\' + $crlf + \'Connection: close\' + $crlf + $crlf; ^',
    '       if ($method -eq \'OPTIONS\') { ^',
    '         $resp = [System.Text.Encoding]::UTF8.GetBytes($cors + \'{}\'); ^',
    '         $stream.Write($resp, 0, $resp.Length); ^',
    '         $client.Close(); continue; ^',
    '       } ^',
    '       if ($path -eq \'/health\') { ^',
    '         $resp = [System.Text.Encoding]::UTF8.GetBytes($cors + \'{\"status\":\"ok\",\"service\":\"kiwi-print-bridge-win\"}\'); ^',
    '         $stream.Write($resp, 0, $resp.Length); ^',
    '         $client.Close(); continue; ^',
    '       } ^',
    '       if ($method -eq \'GET\' -and $path -match \'^/printers\') { ^',
    '         $printerList = @(Get-Printer | Select-Object -ExpandProperty Name); ^',
    '         $jsonPrinters = (@{ ok = $true; printers = $printerList } | ConvertTo-Json -Compress); ^',
    '         $resp = [System.Text.Encoding]::UTF8.GetBytes($cors + $jsonPrinters); ^',
    '         $stream.Write($resp, 0, $resp.Length); ^',
    '         $client.Close(); continue; ^',
    '       } ^',
    '       if ($method -eq \'POST\' -and $path -eq \'/print\' -and $contentLength -gt 0) { ^',
    '         $buf = New-Object char[] $contentLength; ^',
    '         $read = 0; ^',
    '         while ($read -lt $contentLength) { ^',
    '           $r = $reader.Read($buf, $read, $contentLength - $read); ^',
    '           if ($r -le 0) { break; } ^',
    '           $read += $r; ^',
    '         } ^',
    '         $jsonStr = -join $buf; ^',
    '         $payload = $jsonStr | ConvertFrom-Json; ^',
    '         $rawBytes = [System.Convert]::FromBase64String($payload.data_base64); ^',
    '         $printerName = if ($payload.printer_name) { [string]$payload.printer_name } else { \'\' }; ^',
    '         $targetHost = if ($payload.host) { [string]$payload.host } else { \'\' }; ^',
    `         $targetPort = if ($payload.port) { [int]$payload.port } else { ${defaultPort} }; ^`,
    '         if ($targetHost) { ^',
    '           $printer = [System.Net.Sockets.TcpClient]::new(); ^',
    '           $connectTask = $printer.ConnectAsync($targetHost, $targetPort); ^',
    '           if (-not $connectTask.Wait(3500)) { $printer.Close(); throw (\'Tiempo de espera agotado conectando a \' + $targetHost + \':\' + $targetPort); } ^',
    '           $pStream = $printer.GetStream(); ^',
    '           $pStream.Write($rawBytes, 0, $rawBytes.Length); ^',
    '           $pStream.Flush(); ^',
    '           $printer.Close(); ^',
    '           Write-Host (\'[\' + (Get-Date -Format \'HH:mm:ss\') + \'] Impreso \' + $payload.job_kind + \' por RED en \' + $targetHost + \':\' + $targetPort + \' (\' + $rawBytes.Length + \' bytes)\') -ForegroundColor Cyan; ^',
    '         } elseif ($printerName) { ^',
    '           $sent = [RawPrinterHelper]::SendBytesToPrinter($printerName, $rawBytes); ^',
    '           if (-not $sent) { throw (\'No se pudo imprimir en la impresora de Windows: \' + $printerName); } ^',
    '           Write-Host (\'[\' + (Get-Date -Format \'HH:mm:ss\') + \'] Impreso \' + $payload.job_kind + \' en impresora Windows \"\' + $printerName + \'\" (\' + $rawBytes.Length + \' bytes)\') -ForegroundColor Green; ^',
    '         } else { ^',
    `           $fallbackHost = '${defaultHost}'; ^`,
    '           $printer = [System.Net.Sockets.TcpClient]::new(); ^',
    '           $connectTask = $printer.ConnectAsync($fallbackHost, $targetPort); ^',
    '           if (-not $connectTask.Wait(3500)) { $printer.Close(); throw (\'Tiempo de espera agotado conectando a \' + $fallbackHost + \':\' + $targetPort); } ^',
    '           $pStream = $printer.GetStream(); ^',
    '           $pStream.Write($rawBytes, 0, $rawBytes.Length); ^',
    '           $pStream.Flush(); ^',
    '           $printer.Close(); ^',
    '         } ^',
    '         $resp = [System.Text.Encoding]::UTF8.GetBytes($cors + \'{\"ok\":true}\'); ^',
    '         $stream.Write($resp, 0, $resp.Length); ^',
    '       } else { ^',
    '         $resp = [System.Text.Encoding]::UTF8.GetBytes($cors + \'{\"ok\":false}\'); ^',
    '         $stream.Write($resp, 0, $resp.Length); ^',
    '       } ^',
    '       $client.Close(); ^',
    '     } catch { ^',
    '       Write-Host (\'[ERROR] \' + $_.Exception.Message) -ForegroundColor Red; ^',
    '       try { ^',
    '         $errBody = \'{\"ok\":false,\"error\":\"\' + ($_.Exception.Message -replace \'\"\',\'\'\'\') + \'\"}\'; ^',
    '         $errHttp = \'HTTP/1.1 502 Bad Gateway\' + $crlf + \'Access-Control-Allow-Origin: *\' + $crlf + \'Access-Control-Allow-Private-Network: true\' + $crlf + \'Content-Type: application/json\' + $crlf + \'Connection: close\' + $crlf + $crlf + $errBody; ^',
    '         $errBytes = [System.Text.Encoding]::UTF8.GetBytes($errHttp); ^',
    '         $stream.Write($errBytes, 0, $errBytes.Length); ^',
    '         $client.Close(); ^',
    '       } catch {} ^',
    '     } ^',
    '   }"',
    'pause',
    '',
  ];
  return lines.join('\r\n');
}

/**
 * Genera el script puente multiplataforma en Python 3 (sin dependencias externas)
 * para listar impresoras del sistema (GET /printers) y enviar comandos ESC/POS
 * ya sea por nombre de impresora del sistema (CUPS / Windows) o por socket TCP 9100.
 */
export function buildPythonPrintBridgeScript(config: PosPrinterConfig): string {
  const defaultHost = config.ticketPrinterHost.trim() || '192.168.1.200';
  const defaultPort = config.ticketPrinterPort || 9100;
  const defaultPrinterName = config.ticketPrinterName.trim() || 'caja';
  return `#!/usr/bin/env python3
"""
Puente Local de Impresión Térmica Automática — Kiwi RestaurantOS
Recibe trabajos desde https://kiwipos.mimenu.onl en http://127.0.0.1:9123/print
y envía el flujo binario ESC/POS directo a la impresora configurada por nombre (ej. caja, ensaladas, barra)
o por TCP al puerto 9100 de la impresora en red.
"""
import base64
import json
import platform
import socket
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_PRINTER_NAME = "${defaultPrinterName}"
DEFAULT_PRINTER_HOST = "${defaultHost}"
DEFAULT_PRINTER_PORT = ${defaultPort}
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 9123


def list_os_printers():
    system = platform.system().lower()
    printers = []
    try:
        if "windows" in system:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"],
                text=True,
                timeout=4,
            )
            printers = [line.strip() for line in out.splitlines() if line.strip()]
        else:
            out = subprocess.check_output(["lpstat", "-a"], text=True, timeout=4)
            for line in out.splitlines():
                parts = line.strip().split()
                if parts:
                    printers.append(parts[0])
    except Exception:
        pass
    return printers


class PrintBridgeHandler(BaseHTTPRequestHandler):
    def _send_cors(self, status=200):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

    def do_OPTIONS(self):
        self._send_cors(200)
        self.wfile.write(b"{}")

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send_cors(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "service": "kiwi-print-bridge-py",
                "default_printer_name": DEFAULT_PRINTER_NAME,
                "default_printer": f"{DEFAULT_PRINTER_HOST}:{DEFAULT_PRINTER_PORT}",
            }).encode("utf-8"))
            return
        if self.path.startswith("/printers"):
            self._send_cors(200)
            self.wfile.write(json.dumps({
                "ok": True,
                "printers": list_os_printers(),
            }).encode("utf-8"))
            return
        self._send_cors(404)
        self.wfile.write(b'{"error":"not_found"}')

    def do_POST(self):
        if not self.path.startswith("/print"):
            self._send_cors(404)
            self.wfile.write(b'{"error":"not_found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            printer_name = (body.get("printer_name") or "").strip()
            host = (body.get("host") or "").strip()
            port = int(body.get("port") or DEFAULT_PRINTER_PORT)
            raw_bytes = base64.b64decode(body["data_base64"])

            if host:
                with socket.create_connection((host, port), timeout=4.0) as sock:
                    sock.sendall(raw_bytes)
                target_used = f"{host}:{port}"
            elif printer_name:
                proc = subprocess.run(
                    ["lp", "-d", printer_name, "-o", "raw"],
                    input=raw_bytes,
                    capture_output=True,
                    timeout=5,
                )
                if proc.returncode != 0:
                    raise RuntimeError(proc.stderr.decode("utf-8", errors="replace") or f"lp fallo para {printer_name}")
                target_used = printer_name
            else:
                with socket.create_connection((DEFAULT_PRINTER_HOST, port), timeout=4.0) as sock:
                    sock.sendall(raw_bytes)
                target_used = f"{DEFAULT_PRINTER_HOST}:{port}"

            self._send_cors(200)
            self.wfile.write(json.dumps({
                "ok": True,
                "target": target_used,
                "bytes": len(raw_bytes),
            }).encode("utf-8"))
        except Exception as exc:
            self._send_cors(502)
            self.wfile.write(json.dumps({
                "ok": False,
                "error": str(exc),
            }).encode("utf-8"))


if __name__ == "__main__":
    print(f"[KIWI PRINT BRIDGE] Escuchando en http://{LISTEN_HOST}:{LISTEN_PORT}")
    print(f"[KIWI PRINT BRIDGE] Impresora por defecto: {DEFAULT_PRINTER_NAME} / {DEFAULT_PRINTER_HOST}:{DEFAULT_PRINTER_PORT}")
    HTTPServer((LISTEN_HOST, LISTEN_PORT), PrintBridgeHandler).serve_forever()
`;
}
