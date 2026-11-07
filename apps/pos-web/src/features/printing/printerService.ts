import {
  formatTicketText,
  formatKitchenText,
  generateEscPosTicket,
  generateEscPosKitchen,
  type TicketPrintData,
  type KitchenPrintData,
} from './receiptFormatter';

export type AutoPrintCopies = 'both' | 'ticket' | 'kitchen';
export type PrinterConnectionMode = 'network_bridge' | 'browser_silent';

export interface PosPrinterConfig {
  autoPrintOnConfirm: boolean;
  autoPrintCopies: AutoPrintCopies;
  kickDrawerOnCash: boolean;
  connectionMode: PrinterConnectionMode;
  bridgeUrl: string;
  ticketPrinterHost: string;
  ticketPrinterPort: number;
  kitchenPrinterHost: string;
  kitchenPrinterPort: number;
  paperWidthMm: 80 | 58;
}

export const PRINTER_CONFIG_STORAGE_KEY = 'pos_printer_config_v1';

export const DEFAULT_PRINTER_CONFIG: PosPrinterConfig = {
  autoPrintOnConfirm: true,
  autoPrintCopies: 'both',
  kickDrawerOnCash: true,
  connectionMode: 'network_bridge',
  bridgeUrl: 'http://127.0.0.1:9123',
  ticketPrinterHost: '',
  ticketPrinterPort: 9100,
  kitchenPrinterHost: '',
  kitchenPrinterPort: 9100,
  paperWidthMm: 80,
};

export function loadPrinterConfig(storage?: Pick<Storage, 'getItem'> | null): PosPrinterConfig {
  const targetStorage =
    storage !== undefined
      ? storage
      : typeof window !== 'undefined' && window.localStorage
        ? window.localStorage
        : null;

  if (!targetStorage) return { ...DEFAULT_PRINTER_CONFIG };

  try {
    const raw = targetStorage.getItem(PRINTER_CONFIG_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PRINTER_CONFIG };
    const parsed = JSON.parse(raw) as Partial<PosPrinterConfig>;
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
      ticketPrinterHost:
        typeof parsed.ticketPrinterHost === 'string' ? parsed.ticketPrinterHost.trim() : '',
      ticketPrinterPort:
        typeof parsed.ticketPrinterPort === 'number' &&
        parsed.ticketPrinterPort >= 1 &&
        parsed.ticketPrinterPort <= 65535
          ? Math.trunc(parsed.ticketPrinterPort)
          : 9100,
      kitchenPrinterHost:
        typeof parsed.kitchenPrinterHost === 'string' ? parsed.kitchenPrinterHost.trim() : '',
      kitchenPrinterPort:
        typeof parsed.kitchenPrinterPort === 'number' &&
        parsed.kitchenPrinterPort >= 1 &&
        parsed.kitchenPrinterPort <= 65535
          ? Math.trunc(parsed.kitchenPrinterPort)
          : 9100,
      paperWidthMm: parsed.paperWidthMm === 58 ? 58 : 80,
    };
  } catch {
    return { ...DEFAULT_PRINTER_CONFIG };
  }
}

export function savePrinterConfig(
  config: PosPrinterConfig,
  storage?: Pick<Storage, 'setItem'> | null
): PosPrinterConfig {
  const normalized: PosPrinterConfig = {
    ...DEFAULT_PRINTER_CONFIG,
    ...config,
    bridgeUrl: (config.bridgeUrl || DEFAULT_PRINTER_CONFIG.bridgeUrl).trim(),
    ticketPrinterHost: (config.ticketPrinterHost || '').trim(),
    ticketPrinterPort:
      Number.isFinite(config.ticketPrinterPort) &&
      config.ticketPrinterPort >= 1 &&
      config.ticketPrinterPort <= 65535
        ? Math.trunc(config.ticketPrinterPort)
        : 9100,
    kitchenPrinterHost: (config.kitchenPrinterHost || '').trim(),
    kitchenPrinterPort:
      Number.isFinite(config.kitchenPrinterPort) &&
      config.kitchenPrinterPort >= 1 &&
      config.kitchenPrinterPort <= 65535
        ? Math.trunc(config.kitchenPrinterPort)
        : 9100,
    paperWidthMm: config.paperWidthMm === 58 ? 58 : 80,
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

export async function sendEscPosToBridge(
  bridgeUrl: string,
  host: string,
  port: number,
  payloadBytes: Uint8Array,
  jobKind: 'ticket' | 'kitchen'
): Promise<{ ok: boolean; message: string }> {
  const base = (bridgeUrl || DEFAULT_PRINTER_CONFIG.bridgeUrl).replace(/\/+$/, '');
  const cleanHost = host.trim();
  if (!cleanHost) {
    return { ok: false, message: 'No se ha configurado la dirección IP de la impresora.' };
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
    return {
      ok: true,
      message: `Impresión ESC/POS enviada a ${cleanHost}:${port || 9100}`,
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

export function buildThermalPrintHtml(pages: string[], paperWidthMm: 80 | 58 = 80): string {
  const contentWidthMm = paperWidthMm === 58 ? 52 : 72;
  const fontSizePt = paperWidthMm === 58 ? '8.5pt' : '9.5pt';
  const sheetsHtml = pages
    .map(
      (pageText, idx) =>
        `<pre class="thermal-sheet${idx < pages.length - 1 ? ' page-break' : ''}">${escapeHtml(pageText)}</pre>`
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
      font-family: 'Courier New', Courier, monospace;
      font-size: ${fontSizePt};
      line-height: 1.18;
    }
    .thermal-sheet {
      margin: 0;
      padding: 2mm 1mm 5mm 1mm;
      width: ${contentWidthMm}mm;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: 'Courier New', Courier, monospace;
      font-size: ${fontSizePt};
      line-height: 1.18;
      color: #000000;
      background: #ffffff;
    }
    .page-break {
      page-break-after: always;
      break-after: page;
      border-bottom: 1px dashed #000;
      margin-bottom: 3mm;
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
  kickDrawer?: boolean;
  forceBrowserDialog?: boolean;
  config?: PosPrinterConfig;
}

export interface DispatchPrintResult {
  method: 'network_escpos' | 'browser_iframe' | 'none';
  ok: boolean;
  message: string;
}

export async function dispatchPosPrintJob(
  options: DispatchPrintOptions
): Promise<DispatchPrintResult> {
  const config = options.config || loadPrinterConfig();
  const copies = options.copies || config.autoPrintCopies || 'both';
  const widthCols = config.paperWidthMm === 58 ? 32 : 42;

  const activeKitchenData: KitchenPrintData = options.kitchenData || {
    folio: options.ticketData.folio,
    orderNumber: options.ticketData.orderNumber,
    createdAt: options.ticketData.createdAt,
    serviceTypeLabel: options.ticketData.serviceTypeLabel,
    customerName: options.ticketData.customerName,
    customerPhone: options.ticketData.customerPhone,
    driverName: options.ticketData.driverName,
    lines: options.ticketData.lines,
  };

  const shouldPrintTicket = copies === 'both' || copies === 'ticket';
  const shouldPrintKitchen = copies === 'both' || copies === 'kitchen';
  const kickDrawer = Boolean(options.kickDrawer && config.kickDrawerOnCash);

  // 1. Intentar impresión directa silenciosa por Red TCP 9100 (ESC/POS) si hay IP configurada
  const ticketHost = config.ticketPrinterHost.trim();
  const kitchenHost = (config.kitchenPrinterHost || config.ticketPrinterHost).trim();

  if (!options.forceBrowserDialog && config.connectionMode === 'network_bridge' && ticketHost) {
    const results: string[] = [];
    let allSucceeded = true;

    if (shouldPrintTicket) {
      const ticketBytes = generateEscPosTicket(options.ticketData, kickDrawer);
      const res = await sendEscPosToBridge(
        config.bridgeUrl,
        ticketHost,
        config.ticketPrinterPort || 9100,
        ticketBytes,
        'ticket'
      );
      if (res.ok) {
        results.push(`Ticket -> ${ticketHost}:${config.ticketPrinterPort || 9100}`);
      } else {
        allSucceeded = false;
      }
    }

    if (shouldPrintKitchen && allSucceeded) {
      const kitchenBytes = generateEscPosKitchen(activeKitchenData);
      const targetPort = config.kitchenPrinterHost.trim()
        ? config.kitchenPrinterPort || 9100
        : config.ticketPrinterPort || 9100;
      const res = await sendEscPosToBridge(
        config.bridgeUrl,
        kitchenHost,
        targetPort,
        kitchenBytes,
        'kitchen'
      );
      if (res.ok) {
        results.push(`Comanda -> ${kitchenHost}:${targetPort}`);
      } else {
        allSucceeded = false;
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

  // 2. Respaldo o modo navegador: impresión térmica aislada de 80mm/58mm en iframe (compatible con --kiosk-printing)
  const pages: string[] = [];
  if (shouldPrintTicket) {
    pages.push(formatTicketText(options.ticketData, widthCols));
  }
  if (shouldPrintKitchen) {
    pages.push(formatKitchenText(activeKitchenData, widthCols));
  }

  const printed = printThermalIframe(pages, config.paperWidthMm);
  if (printed) {
    const label =
      copies === 'both'
        ? 'Ticket de Venta y Comanda de Cocina'
        : copies === 'ticket'
          ? 'Ticket de Venta'
          : 'Comanda de Cocina';
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
 * Genera el script puente para Windows (.bat con PowerShell embebido, sin requerir permisos de administrador ni instalar Python/Node)
 * que escucha en 127.0.0.1:9123 y reenvía comandos binarios ESC/POS al puerto TCP 9100 de la impresora de red.
 */
export function buildWindowsPrintBridgeBat(config: PosPrinterConfig): string {
  const defaultHost = config.ticketPrinterHost.trim() || '192.168.1.200';
  const defaultPort = config.ticketPrinterPort || 9100;
  const lines = [
    '@echo off',
    'title Puente de Impresion Termica Automatica Kiwi POS (TCP 9100)',
    'color 0A',
    'echo ============================================================================',
    'echo   PUENTE DE IMPRESION TERMICA AUTOMATICA - KIWI RESTAURANTOS',
    'echo   Escuchando en: http://127.0.0.1:9123',
    `echo   Impresora Red por defecto: ${defaultHost}:${defaultPort}`,
    'echo   No cierres esta ventana mientras uses el Punto de Venta.',
    'echo ============================================================================',
    'echo.',
    '',
    'powershell -NoProfile -ExecutionPolicy Bypass -Command ^',
    '  "$ErrorActionPreference = \'Continue\'; ^',
    '   $crlf = [char]13 + [char]10; ^',
    '   $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 9123); ^',
    '   $listener.Start(); ^',
    '   Write-Host \'[LISTO] Puente activo en http://127.0.0.1:9123 -> enviando directo a IP:9100 sin dialogo.\' -ForegroundColor Green; ^',
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
    `         $targetHost = if ($payload.host) { $payload.host } else { '${defaultHost}' }; ^`,
    `         $targetPort = if ($payload.port) { [int]$payload.port } else { ${defaultPort} }; ^`,
    '         $rawBytes = [System.Convert]::FromBase64String($payload.data_base64); ^',
    '         $printer = [System.Net.Sockets.TcpClient]::new(); ^',
    '         $connectTask = $printer.ConnectAsync($targetHost, $targetPort); ^',
    '         if (-not $connectTask.Wait(3500)) { $printer.Close(); throw (\'Tiempo de espera agotado conectando a \' + $targetHost + \':\' + $targetPort); } ^',
    '         $pStream = $printer.GetStream(); ^',
    '         $pStream.Write($rawBytes, 0, $rawBytes.Length); ^',
    '         $pStream.Flush(); ^',
    '         $printer.Close(); ^',
    '         Write-Host (\'[\' + (Get-Date -Format \'HH:mm:ss\') + \'] Impreso \' + $payload.job_kind + \' en \' + $targetHost + \':\' + $targetPort + \' (\' + $rawBytes.Length + \' bytes)\') -ForegroundColor Cyan; ^',
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
 * para enviar comandos ESC/POS por socket TCP directo al puerto 9100 de la impresora de red.
 */
export function buildPythonPrintBridgeScript(config: PosPrinterConfig): string {
  const defaultHost = config.ticketPrinterHost.trim() || '192.168.1.200';
  const defaultPort = config.ticketPrinterPort || 9100;
  return `#!/usr/bin/env python3
"""
Puente Local de Impresión Térmica Automática — Kiwi RestaurantOS
Recibe trabajos desde https://kiwipos.mimenu.onl en http://127.0.0.1:9123/print
y envía el flujo binario ESC/POS directo por TCP al puerto 9100 de la impresora en red.
"""
import base64
import json
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_PRINTER_HOST = "${defaultHost}"
DEFAULT_PRINTER_PORT = ${defaultPort}
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 9123


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
                "default_printer": f"{DEFAULT_PRINTER_HOST}:{DEFAULT_PRINTER_PORT}",
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
            host = (body.get("host") or DEFAULT_PRINTER_HOST).strip()
            port = int(body.get("port") or DEFAULT_PRINTER_PORT)
            raw_bytes = base64.b64decode(body["data_base64"])

            with socket.create_connection((host, port), timeout=4.0) as sock:
                sock.sendall(raw_bytes)

            self._send_cors(200)
            self.wfile.write(json.dumps({
                "ok": True,
                "host": host,
                "port": port,
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
    print(f"[KIWI PRINT BRIDGE] Impresora TCP/IP por defecto: {DEFAULT_PRINTER_HOST}:{DEFAULT_PRINTER_PORT}")
    HTTPServer((LISTEN_HOST, LISTEN_PORT), PrintBridgeHandler).serve_forever()
`;
}
