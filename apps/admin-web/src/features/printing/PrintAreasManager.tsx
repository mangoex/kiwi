import React, { useEffect, useMemo, useState } from 'react';
import { fetchApi } from '@restaurantos/api-client';
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
  Laptop,
  Layers,
  Plus,
  Printer,
  RefreshCw,
  Search,
  Trash2,
  Wifi,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import './PrintAreasManager.css';

export interface PrintAreaItem {
  code: string;
  name: string;
  station: 'kitchen' | 'drinks' | 'packing';
  print_comanda: boolean;
  sort_order: number;
  is_system?: boolean;
}

export interface PrinterTargetConfig {
  enabled: boolean;
  printer_name: string;
  host: string;
  port: number;
}

interface PrintRoutingPayload {
  areas: PrintAreaItem[];
  product_areas: Record<string, string>;
  category_areas: Record<string, string>;
  ticket_printer: PrinterTargetConfig;
  area_printers: Record<string, PrinterTargetConfig>;
  updated_at?: string | null;
}

interface CatalogProductSummary {
  id: string;
  name: string;
  sku: string;
  category_id: string;
  category_name?: string;
  station?: string;
}

interface CategorySummary {
  id: string;
  name: string;
}

interface OrderPreviewResponse {
  order_number: string;
  ticket: {
    printer_name: string;
    host: string;
    port: number;
    text: string;
  };
  comandas: Array<{
    area_code: string;
    area_name: string;
    station: string;
    printer_name: string;
    host: string;
    port: number;
    line_count: number;
    text: string;
  }>;
}

const DEFAULT_AREAS: PrintAreaItem[] = [
  {
    code: 'salads',
    name: 'ENSALADAS',
    station: 'kitchen',
    print_comanda: true,
    sort_order: 1,
    is_system: true,
  },
  {
    code: 'baguettes',
    name: 'BAGUETTES(RAPIDO)',
    station: 'kitchen',
    print_comanda: true,
    sort_order: 2,
    is_system: true,
  },
  {
    code: 'kitchen',
    name: 'BARRA / CALIENTE',
    station: 'kitchen',
    print_comanda: true,
    sort_order: 3,
    is_system: true,
  },
  {
    code: 'drinks',
    name: 'BEBIDAS (BARRA / FUENTES)',
    station: 'drinks',
    print_comanda: true,
    sort_order: 4,
    is_system: true,
  },
  {
    code: 'packing',
    name: 'EMPAQUE',
    station: 'packing',
    print_comanda: false,
    sort_order: 5,
    is_system: true,
  },
  {
    code: 'none',
    name: 'SIN IMPRESION',
    station: 'packing',
    print_comanda: false,
    sort_order: 6,
    is_system: true,
  },
];

const DEFAULT_AREA_PRINTERS: Record<string, PrinterTargetConfig> = {
  salads: { enabled: true, printer_name: 'ensaladas', host: '', port: 9100 },
  baguettes: { enabled: true, printer_name: 'barra', host: '', port: 9100 },
  kitchen: { enabled: true, printer_name: 'barra', host: '', port: 9100 },
  drinks: { enabled: true, printer_name: 'bebidas', host: '', port: 9100 },
  packing: { enabled: false, printer_name: '', host: '', port: 9100 },
  none: { enabled: false, printer_name: '', host: '', port: 9100 },
};

function triggerDownload(content: string, filename: string, mimeType: string = 'text/plain') {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function buildWindowsBatch(ticketPrinter: string, host: string, port: number): string {
  const lines = [
    '@echo off',
    'title Puente de Impresion Termica Automatica Kiwi POS (Impresoras Windows + TCP 9100)',
    'color 0A',
    'echo ============================================================================',
    'echo   PUENTE DE IMPRESION TERMICA AUTOMATICA - KIWI RESTAURANTOS',
    'echo   Escuchando en: http://127.0.0.1:9123',
    `echo   Impresora Caja (Windows): ${ticketPrinter || 'caja'} ^| Red TCP: ${host || '192.168.1.200'}:${port || 9100}`,
    'echo   Soporta impresoras del Panel de Control (caja, ensaladas, barra) e IP:9100',
    'echo   No cierres esta ventana mientras uses el Punto de Venta o Administrador.',
    'echo ============================================================================',
    'echo.',
    '',
    'powershell -NoProfile -ExecutionPolicy Bypass -Command ^',
    '  "$ErrorActionPreference = \'Continue\'; ^',
    '   Add-Type -TypeDefinition \'using System; using System.Runtime.InteropServices; public class RawPrinterHelper { [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)] public class DOCINFOA { [MarshalAs(UnmanagedType.LPStr)] public string pDocName; [MarshalAs(UnmanagedType.LPStr)] public string pOutputFile; [MarshalAs(UnmanagedType.LPStr)] public string pDataType; } [DllImport(\\\"winspool.Drv\\\", EntryPoint = \\\"OpenPrinterA\\\", SetLastError = true, CharSet = CharSet.Ansi, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool OpenPrinter([MarshalAs(UnmanagedType.LPStr)] string szPrinter, out IntPtr hPrinter, IntPtr pd); [DllImport(\\\"winspool.Drv\\\", EntryPoint = \\\"ClosePrinter\\\", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool ClosePrinter(IntPtr hPrinter); [DllImport(\\\"winspool.Drv\\\", EntryPoint = \\\"StartDocPrinterA\\\", SetLastError = true, CharSet = CharSet.Ansi, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool StartDocPrinter(IntPtr hPrinter, Int32 level, [In, MarshalAs(UnmanagedType.LPStruct)] DOCINFOA di); [DllImport(\\\"winspool.Drv\\\", EntryPoint = \\\"EndDocPrinter\\\", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool EndDocPrinter(IntPtr hPrinter); [DllImport(\\\"winspool.Drv\\\", EntryPoint = \\\"StartPagePrinter\\\", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool StartPagePrinter(IntPtr hPrinter); [DllImport(\\\"winspool.Drv\\\", EntryPoint = \\\"EndPagePrinter\\\", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool EndPagePrinter(IntPtr hPrinter); [DllImport(\\\"winspool.Drv\\\", EntryPoint = \\\"WritePrinter\\\", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)] public static extern bool WritePrinter(IntPtr hPrinter, IntPtr pBytes, Int32 dwCount, out Int32 dwWritten); public static bool SendBytesToPrinter(string szPrinterName, byte[] pBytes) { IntPtr hPrinter = IntPtr.Zero; DOCINFOA di = new DOCINFOA(); di.pDocName = \\\"Kiwi POS RAW Thermal\\\"; di.pDataType = \\\"RAW\\\"; bool bSuccess = false; if (OpenPrinter(szPrinterName.Normalize(), out hPrinter, IntPtr.Zero)) { if (StartDocPrinter(hPrinter, 1, di)) { if (StartPagePrinter(hPrinter)) { IntPtr pUnmanagedBytes = Marshal.AllocCoTaskMem(pBytes.Length); Marshal.Copy(pBytes, 0, pUnmanagedBytes, pBytes.Length); int dwWritten = 0; bSuccess = WritePrinter(hPrinter, pUnmanagedBytes, pBytes.Length, out dwWritten); Marshal.FreeCoTaskMem(pUnmanagedBytes); EndPagePrinter(hPrinter); } EndDocPrinter(hPrinter); } ClosePrinter(hPrinter); } return bSuccess; } }\'; ^',
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
    '         $bodyStr = [string]::new($buf, 0, $read); ^',
    '         $payload = ConvertFrom-Json $bodyStr; ^',
    '         $b64 = $payload.data_base64; ^',
    '         $targetName = if ($payload.printer_name) { $payload.printer_name } else { \'' + (ticketPrinter || 'caja') + '\' }; ^',
    '         $targetHost = $payload.host; ^',
    '         $targetPort = if ($payload.port) { [int]$payload.port } else { ' + (port || 9100) + ' }; ^',
    '         $rawBytes = [System.Convert]::FromBase64String($b64); ^',
    '         if ($targetName -and (-not $targetHost)) { ^',
    '           Write-Host (\'[IMPRIMIENDO EN WINDOWS] \' + $targetName + \' (\' + $rawBytes.Length + \' bytes)\') -ForegroundColor Cyan; ^',
    '           $sent = [RawPrinterHelper]::SendBytesToPrinter($targetName, $rawBytes); ^',
    '           if (-not $sent) { Write-Host (\'[AVISO] No se pudo imprimir por nombre directo, intentando por spooler...\') -ForegroundColor Yellow; } ^',
    '         } elseif ($targetHost) { ^',
    '           Write-Host (\'[IMPRIMIENDO EN RED TCP] \' + $targetHost + \':\' + $targetPort) -ForegroundColor Cyan; ^',
    '           $printer = [System.Net.Sockets.TcpClient]::new($targetHost, $targetPort); ^',
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
    '         $errBody = \'{\"ok\":false,\"error\":\"\' + ($_.Exception.Message -replace \'\"\\r\\n\',\'\') + \'\"}\'; ^',
    '         $errHttp = \'HTTP/1.1 502 Bad Gateway\' + $crlf + \'Access-Control-Allow-Origin: *\' + $crlf + \'Access-Control-Allow-Private-Network: true\' + $crlf + \'Content-Type: application/json\' + $crlf + \'Connection: close\' + $crlf + $crlf + $errBody; ^',
    '         $errBytes = [System.Text.Encoding]::UTF8.GetBytes($errHttp); ^',
    '         $stream.Write($errBytes, 0, $errBytes.Length); ^',
    '         $client.Close(); ^',
    '       } catch {} ^',
    '     } ^',
    '   }',
  ];
  return lines.join('\r\n');
}

function buildPythonScript(ticketPrinter: string, host: string, port: number): string {
  return `#!/usr/bin/env python3
"""
Puente Local de Impresión Térmica Automática — Kiwi RestaurantOS
Recibe trabajos en http://127.0.0.1:9123/print
"""
import base64
import json
import platform
import socket
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_PRINTER_NAME = "${ticketPrinter || 'caja'}"
DEFAULT_PRINTER_HOST = "${host || '192.168.1.200'}"
DEFAULT_PRINTER_PORT = ${port || 9100}
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 9123

def list_os_printers():
    system = platform.system().lower()
    printers = []
    try:
        if system == "windows":
            res = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                printers = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        else:
            res = subprocess.run(["lpstat", "-a"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    p = line.split()[0] if line.split() else ""
                    if p: printers.append(p)
    except Exception:
        pass
    return printers

class BridgeHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"kiwi-print-bridge-py"}')
        elif self.path.startswith("/printers"):
            printers = list_os_printers()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "printers": printers}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/print":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
            raw = base64.b64decode(data.get("data_base64", ""))
            p_name = data.get("printer_name") or DEFAULT_PRINTER_NAME
            p_host = data.get("host")
            p_port = int(data.get("port") or DEFAULT_PRINTER_PORT)
            if p_host:
                with socket.create_connection((p_host, p_port), timeout=5) as s:
                    s.sendall(raw)
            else:
                p = subprocess.Popen(["lp", "-d", p_name], stdin=subprocess.PIPE)
                p.communicate(input=raw)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

if __name__ == "__main__":
    print(f"Puente Kiwi escuchando en http://{LISTEN_HOST}:{LISTEN_PORT}")
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), BridgeHandler)
    server.serve_forever()
`;
}

function syncPosLocalStorageFromAdmin(routing: PrintRoutingPayload, bridgeUrl: string) {
  try {
    const rawExisting = localStorage.getItem('pos_printer_config_v1');
    const existing = rawExisting ? (JSON.parse(rawExisting) as Record<string, unknown>) : {};
    const areaPrintersCamel: Record<
      string,
      { enabled: boolean; printerName: string; host: string; port: number }
    > = {};
    for (const [code, target] of Object.entries(routing.area_printers || {})) {
      areaPrintersCamel[code] = {
        enabled: Boolean(target.enabled),
        printerName: String(target.printer_name || '').trim(),
        host: String(target.host || '').trim(),
        port: Number(target.port) || 9100,
      };
    }
    const merged = {
      autoPrintOnConfirm: existing.autoPrintOnConfirm ?? true,
      autoPrintCopies: existing.autoPrintCopies ?? 'both',
      kickDrawerOnCash: existing.kickDrawerOnCash ?? true,
      connectionMode: existing.connectionMode ?? 'network_bridge',
      bridgeUrl: bridgeUrl || (existing.bridgeUrl as string) || 'http://127.0.0.1:9123',
      ticketPrinterName: routing.ticket_printer?.printer_name || 'caja',
      ticketPrinterHost: routing.ticket_printer?.host || '',
      ticketPrinterPort: routing.ticket_printer?.port || 9100,
      kitchenPrinterName: areaPrintersCamel.baguettes?.printerName || 'barra',
      kitchenPrinterHost: areaPrintersCamel.baguettes?.host || '',
      kitchenPrinterPort: areaPrintersCamel.baguettes?.port || 9100,
      paperWidthMm: existing.paperWidthMm === 58 ? 58 : 80,
      printAreas: routing.areas.map((a) => ({
        code: a.code,
        name: a.name,
        station: a.station,
        printComanda: a.print_comanda,
        sortOrder: a.sort_order,
        isSystem: a.is_system,
      })),
      productPrintAreas: routing.product_areas || {},
      categoryPrintAreas: routing.category_areas || {},
      areaPrinters: areaPrintersCamel,
    };
    localStorage.setItem('pos_printer_config_v1', JSON.stringify(merged));
  } catch {
    // Ignore storage errors
  }
}

export const PrintAreasManager: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'printers' | 'menu' | 'simulator' | 'bridge'>('printers');

  const [areas, setAreas] = useState<PrintAreaItem[]>(DEFAULT_AREAS);
  const [productAreas, setProductAreas] = useState<Record<string, string>>({});
  const [categoryAreas, setCategoryAreas] = useState<Record<string, string>>({});
  const [ticketPrinter, setTicketPrinter] = useState<PrinterTargetConfig>({
    enabled: true,
    printer_name: 'caja',
    host: '',
    port: 9100,
  });
  const [areaPrinters, setAreaPrinters] =
    useState<Record<string, PrinterTargetConfig>>(DEFAULT_AREA_PRINTERS);

  const [categories, setCategories] = useState<CategorySummary[]>([]);
  const [products, setProducts] = useState<CatalogProductSummary[]>([]);
  const [productSearch, setProductSearch] = useState('');
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string>('all');

  const [bridgeUrl, setBridgeUrl] = useState('http://127.0.0.1:9123');
  const [osPrinters, setOsPrinters] = useState<string[]>([]);
  const [bridgeStatus, setBridgeStatus] = useState<{
    checking: boolean;
    online: boolean;
    message: string;
  }>({
    checking: false,
    online: false,
    message: 'Sin verificar',
  });

  const [newAreaCode, setNewAreaCode] = useState('');
  const [newAreaName, setNewAreaName] = useState('');
  const [newAreaStation, setNewAreaStation] = useState<'kitchen' | 'drinks' | 'packing'>('kitchen');
  const [newAreaPrinterName, setNewAreaPrinterName] = useState('');

  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [previewData, setPreviewData] = useState<OrderPreviewResponse | null>(null);
  const [testingPrint, setTestingPrint] = useState(false);
  const [testPrintStatus, setTestPrintStatus] = useState('');

  const detectLocalPrinters = async (urlToCheck: string = bridgeUrl) => {
    const cleanUrl = urlToCheck.replace(/\/+$/, '');
    setBridgeStatus({
      checking: true,
      online: false,
      message: 'Consultando impresoras instaladas en el Panel de Control de esta PC…',
    });
    try {
      const [healthRes, printersRes] = await Promise.all([
        fetch(`${cleanUrl}/health`).catch(() => null),
        fetch(`${cleanUrl}/printers`).catch(() => null),
      ]);
      const detected: string[] = [];
      if (printersRes && printersRes.ok) {
        const body = (await printersRes.json().catch(() => ({}))) as { printers?: string[] };
        if (Array.isArray(body.printers)) {
          body.printers.forEach((p) => {
            if (p && String(p).trim()) detected.push(String(p).trim());
          });
        }
      }
      if (detected.length > 0) {
        setOsPrinters(detected);
      }
      if (healthRes && healthRes.ok) {
        setBridgeStatus({
          checking: false,
          online: true,
          message:
            detected.length > 0
              ? `Puente activo en esta PC (${detected.length} impresoras detectadas: ${detected.join(', ')})`
              : 'Puente activo en esta PC · Listo para enviar a impresoras por nombre (caja, ensaladas, barra) o IP:9100',
        });
      } else {
        setBridgeStatus({
          checking: false,
          online: false,
          message:
            'Puente local aún no iniciado en esta PC. Puedes configurar los nombres de tus impresoras y descargar el puente en la pestaña "Puente PC".',
        });
      }
    } catch {
      setBridgeStatus({
        checking: false,
        online: false,
        message: 'No se pudo conectar con el puente local en 127.0.0.1:9123.',
      });
    }
  };

  const refreshSamplePreview = async (currentRouting?: Partial<PrintRoutingPayload>) => {
    try {
      const sampleOrder = {
        folio: 'SUC04-000003',
        branch_name: 'SUCURSAL CHAPULTEPEC',
        created_at: '14/11/2026 08:23:24 AM',
        service_type_label: 'CONSUMIR AQUI',
        customer_name: 'MIGUEL GONZALEZ',
        total_cents: 38500,
        lines: [
          {
            product_id: 'sample-salad',
            product_name: 'ENSALADA DE ARANDANO',
            category_name: 'ENSALADAS',
            quantity: 1,
            unit_price_cents: 13000,
            line_total_cents: 13000,
            selected_modifiers: [{ text: 'ADEREZO RANCH' }],
          },
          {
            product_id: 'sample-baguette-1',
            product_name: 'SANDWICH INTEGRAL POLLO BBQ',
            category_name: 'BAGUETTES',
            quantity: 1,
            unit_price_cents: 11500,
            line_total_cents: 11500,
            selected_modifiers: [{ text: 'ADEREZO DE CHIPOTLE CHI' }, { text: 'MANCHEGUITO' }],
          },
          {
            product_id: 'sample-baguette-2',
            product_name: 'CUERNITO BBQ',
            category_name: 'BAGUETTES',
            quantity: 1,
            unit_price_cents: 10500,
            line_total_cents: 10500,
            selected_modifiers: [{ text: 'ADEREZO DE CHIPOTLE CHI' }],
          },
          {
            product_id: 'sample-drink',
            product_name: 'AGUA DE FRESA LIMON CHICA',
            category_name: 'AGUAS',
            quantity: 1,
            unit_price_cents: 3500,
            line_total_cents: 3500,
          },
        ],
      };
      if (currentRouting) {
        await fetchApi('/print-routing', {
          method: 'PUT',
          body: JSON.stringify(currentRouting),
        });
      }
      const preview = await fetchApi<OrderPreviewResponse>('/print-routing/preview-order', {
        method: 'POST',
        body: JSON.stringify(sampleOrder),
      });
      if (preview) setPreviewData(preview);
    } catch {
      // Ignore preview errors
    }
  };

  useEffect(() => {
    void detectLocalPrinters();
    void (async () => {
      try {
        const [routingRes, catsRes, prodsRes] = await Promise.all([
          fetchApi<PrintRoutingPayload>('/print-routing').catch(() => null),
          fetchApi<CategorySummary[]>('/categories').catch(() => []),
          fetchApi<CatalogProductSummary[]>('/catalog/products').catch(() => []),
        ]);
        if (routingRes) {
          if (Array.isArray(routingRes.areas) && routingRes.areas.length > 0) {
            setAreas(routingRes.areas);
          }
          setProductAreas(routingRes.product_areas || {});
          setCategoryAreas(routingRes.category_areas || {});
          if (routingRes.ticket_printer) {
            setTicketPrinter(routingRes.ticket_printer);
          }
          if (routingRes.area_printers) {
            setAreaPrinters({ ...DEFAULT_AREA_PRINTERS, ...routingRes.area_printers });
          }
          syncPosLocalStorageFromAdmin(routingRes, bridgeUrl);
        }
        if (Array.isArray(catsRes)) setCategories(catsRes);
        if (Array.isArray(prodsRes)) setProducts(prodsRes);
        void refreshSamplePreview();
      } catch {
        // Fallback to defaults
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSaveAll = async () => {
    setSaving(true);
    setSaveMessage('');
    try {
      const payload: PrintRoutingPayload = {
        areas,
        product_areas: productAreas,
        category_areas: categoryAreas,
        ticket_printer: ticketPrinter,
        area_printers: areaPrinters,
      };
      const saved = await fetchApi<PrintRoutingPayload>('/print-routing', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      const effective = saved || payload;
      syncPosLocalStorageFromAdmin(effective, bridgeUrl);
      await refreshSamplePreview();
      setSaveMessage(
        '✓ Configuración de impresoras, áreas y asignación guardada exitosamente.'
      );
      setTimeout(() => setSaveMessage(''), 5000);
    } catch {
      syncPosLocalStorageFromAdmin(
        {
          areas,
          product_areas: productAreas,
          category_areas: categoryAreas,
          ticket_printer: ticketPrinter,
          area_printers: areaPrinters,
        },
        bridgeUrl
      );
      setSaveMessage('✓ Configuración guardada localmente en este equipo.');
    } finally {
      setSaving(false);
    }
  };

  const handleAddArea = () => {
    const cleanCode = newAreaCode.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
    const cleanName = newAreaName.trim().toUpperCase();
    if (!cleanCode || !cleanName) return;
    const nextAreas: PrintAreaItem[] = [
      ...areas.filter((a) => a.code !== cleanCode),
      {
        code: cleanCode,
        name: cleanName,
        station: newAreaStation,
        print_comanda: true,
        sort_order: areas.length + 1,
        is_system: false,
      },
    ];
    setAreas(nextAreas);
    setAreaPrinters({
      ...areaPrinters,
      [cleanCode]: {
        enabled: true,
        printer_name: newAreaPrinterName.trim() || cleanCode,
        host: '',
        port: 9100,
      },
    });
    setNewAreaCode('');
    setNewAreaName('');
    setNewAreaPrinterName('');
  };

  const handleRemoveArea = (code: string) => {
    setAreas(areas.filter((a) => a.code !== code));
    const nextPrinters = { ...areaPrinters };
    delete nextPrinters[code];
    setAreaPrinters(nextPrinters);
  };

  const handleAssignCategoryArea = (category: CategorySummary, areaCode: string) => {
    const nextCatAreas = { ...categoryAreas };
    if (!areaCode) {
      delete nextCatAreas[category.id];
      delete nextCatAreas[category.name.toUpperCase()];
    } else {
      nextCatAreas[category.id] = areaCode;
      nextCatAreas[category.name.toUpperCase()] = areaCode;
    }
    setCategoryAreas(nextCatAreas);
  };

  const handleAssignProductArea = (productId: string, areaCode: string) => {
    const nextProdAreas = { ...productAreas };
    if (!areaCode) {
      delete nextProdAreas[productId];
    } else {
      nextProdAreas[productId] = areaCode;
    }
    setProductAreas(nextProdAreas);
  };

  const handleSendTestToBridge = async (
    targetPrinterName: string,
    targetHost: string,
    targetPort: number,
    text: string,
    label: string
  ) => {
    setTestingPrint(true);
    setTestPrintStatus('');
    try {
      const encoder = new TextEncoder();
      const textBytes = encoder.encode(text + '\n\n');
      const init = new Uint8Array([0x1b, 0x40]);
      const feed = new Uint8Array([0x1b, 0x64, 0x01]);
      const cut = new Uint8Array([0x1d, 0x56, 0x42, 0x01]);
      const combined = new Uint8Array(init.length + textBytes.length + feed.length + cut.length);
      combined.set(init, 0);
      combined.set(textBytes, init.length);
      combined.set(feed, init.length + textBytes.length);
      combined.set(cut, init.length + textBytes.length + feed.length);

      let binary = '';
      combined.forEach((b) => {
        binary += String.fromCharCode(b);
      });
      const dataBase64 = btoa(binary);

      const res = await fetch(`${bridgeUrl.replace(/\/+$/, '')}/print`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          printer_name: targetPrinterName.trim(),
          host: targetHost.trim(),
          port: targetPort || 9100,
          job_kind: label,
          data_base64: dataBase64,
        }),
      });
      if (res.ok) {
        setTestPrintStatus(
          `✓ ${label} enviada con éxito a la impresora "${targetPrinterName || targetHost}"`
        );
      } else {
        setTestPrintStatus(
          `Puente local respondió con error o la impresora "${targetPrinterName}" no está conectada.`
        );
      }
    } catch {
      setTestPrintStatus(
        `Para imprimir físicamente, inicia el Puente Kiwi (.bat) en la PC conectada a la impresora.`
      );
    } finally {
      setTestingPrint(false);
    }
  };

  const filteredProducts = useMemo(() => {
    const q = productSearch.trim().toLowerCase();
    return products.filter((p) => {
      if (selectedCategoryFilter !== 'all' && p.category_id !== selectedCategoryFilter) {
        return false;
      }
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        (p.sku || '').toLowerCase().includes(q) ||
        (p.category_name || '').toLowerCase().includes(q)
      );
    });
  }, [products, productSearch, selectedCategoryFilter]);

  const suggestedPrinters = useMemo(
    () => Array.from(new Set(['caja', 'ensaladas', 'barra', 'bebidas', ...osPrinters])),
    [osPrinters]
  );

  const getStationBadgeClass = (code: string) => {
    if (code === 'salads') return 'pam-badge-salads';
    if (code === 'baguettes') return 'pam-badge-baguettes';
    if (code === 'kitchen') return 'pam-badge-kitchen';
    if (code === 'drinks') return 'pam-badge-drinks';
    return 'pam-badge-packing';
  };

  return (
    <div className="pam-container">
      <datalist id="admin-os-printers-datalist">
        {suggestedPrinters.map((p) => (
          <option key={p} value={p} />
        ))}
      </datalist>

      {/* Encabezado Principal */}
      <header className="pam-header-card">
        <div>
          <h1 className="pam-title">
            <Printer size={28} color="#10b981" />
            Configuración de Áreas de Impresión y Comandas
          </h1>
          <p className="pam-subtitle">
            Asigna a cada estación de preparación su impresora de la computadora (ej.{' '}
            <strong>caja</strong>, <strong>ensaladas</strong>, <strong>barra</strong>) y separa
            automáticamente las comandas por producto o categoría sin márgenes excesivos ni cortes desalineados.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button
            type="button"
            className="pam-btn pam-btn-secondary"
            onClick={() => navigate('/products')}
          >
            Ir a Catálogo de Productos
            <ArrowRight size={16} />
          </button>

          <button
            type="button"
            className="pam-btn pam-btn-primary"
            disabled={saving}
            onClick={() => void handleSaveAll()}
          >
            <CheckCircle2 size={18} />
            {saving ? 'Guardando…' : 'Guardar Cambios'}
          </button>
        </div>
      </header>

      {/* Pestañas de Navegación Segmentada */}
      <nav className="pam-tabs-nav" aria-label="Secciones de configuración de impresión">
        <button
          type="button"
          className={`pam-tab-button ${activeTab === 'printers' ? 'active' : ''}`}
          onClick={() => setActiveTab('printers')}
        >
          <Printer size={18} />
          1. Estaciones e Impresoras
        </button>

        <button
          type="button"
          className={`pam-tab-button ${activeTab === 'menu' ? 'active' : ''}`}
          onClick={() => setActiveTab('menu')}
        >
          <Layers size={18} />
          2. Asignación del Menú
        </button>

        <button
          type="button"
          className={`pam-tab-button ${activeTab === 'simulator' ? 'active' : ''}`}
          onClick={() => setActiveTab('simulator')}
        >
          <FileText size={18} />
          3. Simulador de Tickets (42 col)
        </button>

        <button
          type="button"
          className={`pam-tab-button ${activeTab === 'bridge' ? 'active' : ''}`}
          onClick={() => setActiveTab('bridge')}
        >
          <Laptop size={18} />
          4. Puente PC y Diagnóstico
        </button>
      </nav>

      {/* Mensaje de Confirmación de Guardado */}
      {saveMessage && (
        <div
          role="status"
          style={{
            background: '#ecfdf5',
            border: '1px solid #10b981',
            color: '#065f46',
            padding: '14px 20px',
            borderRadius: 12,
            fontWeight: 700,
            fontSize: '0.95rem',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <Check size={20} />
          {saveMessage}
        </div>
      )}

      {/* TAB 1: ESTACIONES E IMPRESORAS */}
      {activeTab === 'printers' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Banner de estado de conexión */}
          <div className={`pam-status-banner ${bridgeStatus.online ? 'online' : 'offline'}`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Wifi size={18} />
              <span>{bridgeStatus.message}</span>
            </div>
            <button
              type="button"
              className="pam-btn pam-btn-secondary pam-btn-sm"
              onClick={() => void detectLocalPrinters(bridgeUrl)}
              disabled={bridgeStatus.checking}
            >
              <RefreshCw size={14} className={bridgeStatus.checking ? 'spin' : ''} />
              {bridgeStatus.checking ? 'Consultando…' : 'Detectar Impresoras PC'}
            </button>
          </div>

          {/* Tarjeta de Impresora de Caja (Ticket del Cliente) */}
          <section className="pam-caja-card">
            <div className="pam-caja-header">
              <div>
                <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: '#0f172a' }}>
                  Nota del Cliente (Ticket de Venta en Caja)
                </h2>
                <p style={{ margin: '4px 0 0', fontSize: '0.88rem', color: '#475569' }}>
                  Aquí se imprime el comprobante de pago completo para el comensal. Por lo general la impresora se llama <code>caja</code> en Windows.
                </p>
              </div>

              <button
                type="button"
                className="pam-btn pam-btn-secondary pam-btn-sm"
                disabled={testingPrint}
                onClick={() => {
                  const sampleText =
                    previewData?.ticket.text ||
                    '*** KIWI RESTAURANTOS ***\nTICKET DE CLIENTE - CAJA\nORDEN: SUC04-000003\nTOTAL: $385.00';
                  void handleSendTestToBridge(
                    ticketPrinter.printer_name,
                    ticketPrinter.host,
                    ticketPrinter.port,
                    sampleText,
                    'Ticket de Caja'
                  );
                }}
              >
                <Printer size={15} />
                Probar Impresora de Caja
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
              <div className="pam-field">
                <label className="pam-label">Nombre exacto de la Impresora en Windows / PC</label>
                <input
                  type="text"
                  list="admin-os-printers-datalist"
                  className="pam-input"
                  value={ticketPrinter.printer_name}
                  onChange={(e) => setTicketPrinter({ ...ticketPrinter, printer_name: e.target.value })}
                  placeholder="ej. caja"
                />
                <span className="pam-hint">Nombre configurado en el Panel de Control de la computadora.</span>
                {osPrinters.length > 0 && (
                  <div className="pam-pills-container">
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Sugerencias detectadas:</span>
                    {osPrinters.map((p) => (
                      <button
                        key={p}
                        type="button"
                        className={`pam-pill ${ticketPrinter.printer_name.toLowerCase() === p.toLowerCase() ? 'active' : ''}`}
                        onClick={() => setTicketPrinter({ ...ticketPrinter, printer_name: p })}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="pam-field">
                <label className="pam-label">IP de Red Ethernet / Wi-Fi (Opcional)</label>
                <input
                  type="text"
                  className="pam-input"
                  value={ticketPrinter.host}
                  onChange={(e) => setTicketPrinter({ ...ticketPrinter, host: e.target.value })}
                  placeholder="ej. 192.168.1.200"
                />
                <span className="pam-hint">Déjalo vacío si la impresora está conectada por cable USB o compartida en Windows.</span>
              </div>

              <div className="pam-field" style={{ maxWidth: 140 }}>
                <label className="pam-label">Puerto TCP</label>
                <input
                  type="number"
                  className="pam-input"
                  value={ticketPrinter.port}
                  onChange={(e) => setTicketPrinter({ ...ticketPrinter, port: Number(e.target.value) || 9100 })}
                />
                <span className="pam-hint">Estándar: 9100</span>
              </div>
            </div>
          </section>

          {/* Tarjeta de Lista de Áreas de Impresión de Comandas */}
          <section className="pam-card">
            <div>
              <h2 className="pam-card-title">
                <Printer size={22} color="#047857" />
                Áreas de Impresión de Comandas para Cocina y Barra
              </h2>
              <p className="pam-card-desc">
                Cada área cuenta con su propio nombre de comanda, su impresora física asignada y su corte de papel independiente. Si activas el interruptor, los productos asignados a esta área se imprimirán aquí.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {areas.map((area) => {
                const target = areaPrinters[area.code] || {
                  enabled: area.print_comanda,
                  printer_name: area.print_comanda ? area.code : '',
                  host: '',
                  port: 9100,
                };
                return (
                  <div
                    key={area.code}
                    className={`pam-area-item ${!area.print_comanda ? 'disabled' : ''}`}
                  >
                    <div className="pam-area-header">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
                        {/* iOS Switch */}
                        <label className="pam-switch" title={area.print_comanda ? 'Comanda activada' : 'Comanda desactivada'}>
                          <input
                            type="checkbox"
                            checked={area.print_comanda}
                            onChange={(e) => {
                              const checked = e.target.checked;
                              setAreas(
                                areas.map((a) =>
                                  a.code === area.code ? { ...a, print_comanda: checked } : a
                                )
                              );
                              setAreaPrinters({
                                ...areaPrinters,
                                [area.code]: { ...target, enabled: checked },
                              });
                            }}
                          />
                          <span className="pam-switch-slider" />
                        </label>

                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0f172a' }}>
                              {area.name}
                            </span>
                            <span className={`pam-badge ${getStationBadgeClass(area.code)}`}>
                              {area.code.toUpperCase()}
                            </span>
                          </div>
                          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                            {area.print_comanda
                              ? `Imprime comanda separada en la impresora "${target.printer_name || area.code}"`
                              : 'No imprime comanda (área inactiva para impresión)'}
                          </span>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        {area.print_comanda && (
                          <button
                            type="button"
                            className="pam-btn pam-btn-secondary pam-btn-sm"
                            disabled={testingPrint}
                            onClick={() => {
                              const comandaText =
                                previewData?.comandas.find((c) => c.area_code === area.code)?.text ||
                                `*** COMANDA DE PRUEBA ***\n${area.name} ORDEN: 3\nESTACION: ${area.name}\n------------------------------------------\n[ 1 ] PRODUCTO DE PRUEBA (${area.name})\n------------------------------------------`;
                              void handleSendTestToBridge(
                                target.printer_name,
                                target.host,
                                target.port,
                                comandaText,
                                `Comanda ${area.name}`
                              );
                            }}
                          >
                            <Printer size={14} />
                            Probar Comanda
                          </button>
                        )}

                        {!area.is_system && (
                          <button
                            type="button"
                            className="pam-btn pam-btn-danger pam-btn-sm"
                            onClick={() => handleRemoveArea(area.code)}
                            title="Eliminar esta área de comanda"
                          >
                            <Trash2 size={14} />
                            Eliminar
                          </button>
                        )}
                      </div>
                    </div>

                    {area.print_comanda && (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14, paddingTop: 6 }}>
                        <div className="pam-field">
                          <label className="pam-label">Título impreso en la Comanda</label>
                          <input
                            type="text"
                            className="pam-input"
                            value={area.name}
                            onChange={(e) =>
                              setAreas(
                                areas.map((a) =>
                                  a.code === area.code ? { ...a, name: e.target.value.toUpperCase() } : a
                                )
                              )
                            }
                            placeholder="ej. ENSALADAS"
                          />
                        </div>

                        <div className="pam-field">
                          <label className="pam-label">Impresora en Windows (Panel de Control)</label>
                          <input
                            type="text"
                            list="admin-os-printers-datalist"
                            className="pam-input"
                            value={target.printer_name}
                            onChange={(e) =>
                              setAreaPrinters({
                                ...areaPrinters,
                                [area.code]: { ...target, printer_name: e.target.value },
                              })
                            }
                            placeholder={area.code === 'salads' ? 'ensaladas' : 'barra'}
                          />
                          {osPrinters.length > 0 && (
                            <div className="pam-pills-container">
                              {osPrinters.map((p) => (
                                <button
                                  key={p}
                                  type="button"
                                  className={`pam-pill ${target.printer_name.toLowerCase() === p.toLowerCase() ? 'active' : ''}`}
                                  onClick={() =>
                                    setAreaPrinters({
                                      ...areaPrinters,
                                      [area.code]: { ...target, printer_name: p },
                                    })
                                  }
                                >
                                  {p}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="pam-field">
                          <label className="pam-label">IP de Red (Opcional)</label>
                          <input
                            type="text"
                            className="pam-input"
                            value={target.host}
                            onChange={(e) =>
                              setAreaPrinters({
                                ...areaPrinters,
                                [area.code]: { ...target, host: e.target.value },
                              })
                            }
                            placeholder="ej. 192.168.1.201"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Agregar nueva Área */}
            <div style={{ borderTop: '2px dashed #e2e8f0', paddingTop: 20, marginTop: 10 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: '1rem', fontWeight: 700, color: '#0f172a' }}>
                + Agregar Nueva Área de Comanda (ej. Postres, Plancha, Jugos)
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr)) auto', gap: 12, alignItems: 'flex-end' }}>
                <div className="pam-field">
                  <label className="pam-label">Código único</label>
                  <input
                    type="text"
                    className="pam-input"
                    value={newAreaCode}
                    onChange={(e) => setNewAreaCode(e.target.value)}
                    placeholder="ej. postres"
                  />
                </div>

                <div className="pam-field">
                  <label className="pam-label">Nombre en Comanda</label>
                  <input
                    type="text"
                    className="pam-input"
                    value={newAreaName}
                    onChange={(e) => setNewAreaName(e.target.value)}
                    placeholder="ej. REPOSTERIA FRIA"
                  />
                </div>

                <div className="pam-field">
                  <label className="pam-label">Estación KDS</label>
                  <select
                    className="pam-select"
                    value={newAreaStation}
                    onChange={(e) =>
                      setNewAreaStation(e.target.value as 'kitchen' | 'drinks' | 'packing')
                    }
                  >
                    <option value="kitchen">Cocina / Barra</option>
                    <option value="drinks">Bebidas</option>
                    <option value="packing">Empaque</option>
                  </select>
                </div>

                <div className="pam-field">
                  <label className="pam-label">Impresora PC</label>
                  <input
                    type="text"
                    list="admin-os-printers-datalist"
                    className="pam-input"
                    value={newAreaPrinterName}
                    onChange={(e) => setNewAreaPrinterName(e.target.value)}
                    placeholder="ej. barra"
                  />
                </div>

                <button
                  type="button"
                  className="pam-btn pam-btn-primary"
                  onClick={handleAddArea}
                >
                  <Plus size={18} />
                  Agregar Área
                </button>
              </div>
            </div>
          </section>
        </div>
      )}

      {/* TAB 2: ASIGNACIÓN DEL MENÚ (GRUPOS Y PRODUCTOS) */}
      {activeTab === 'menu' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Asignación por Grupo / Categoría */}
          <section className="pam-card">
            <div>
              <h2 className="pam-card-title">
                <Layers size={22} color="#0284c7" />
                Asignación Rápida por Grupo / Categoría
              </h2>
              <p className="pam-card-desc">
                Todo producto nuevo o existente perteneciente al grupo se enviará automáticamente a esta impresora, a menos que tenga una excepción individual abajo.
              </p>
            </div>

            <div className="pam-groups-grid">
              {categories.map((cat) => {
                const currentArea =
                  categoryAreas[cat.id] || categoryAreas[cat.name.toUpperCase()] || '';
                return (
                  <div key={cat.id} className="pam-group-card">
                    <div className="pam-group-header">
                      <span style={{ fontWeight: 800, fontSize: '0.95rem', color: '#0f172a' }}>
                        {cat.name}
                      </span>
                      {currentArea ? (
                        <span className={`pam-badge ${getStationBadgeClass(currentArea)}`}>
                          {currentArea.toUpperCase()}
                        </span>
                      ) : (
                        <span className="pam-badge pam-badge-packing">Automático</span>
                      )}
                    </div>

                    <select
                      className="pam-select"
                      value={currentArea}
                      onChange={(e) => handleAssignCategoryArea(cat, e.target.value)}
                    >
                      <option value="">Automático (Heredar por nombre/tipo)</option>
                      {areas
                        .filter((a) => a.print_comanda)
                        .map((a) => (
                          <option key={a.code} value={a.code}>
                            {a.name} → Impresora: {areaPrinters[a.code]?.printer_name || a.code}
                          </option>
                        ))}
                      <option value="none">Sin comanda (No imprimir)</option>
                    </select>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Asignación Individual por Producto */}
          <section className="pam-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
              <div>
                <h2 className="pam-card-title">
                  <Search size={22} color="#475569" />
                  Asignación Individual por Producto ({filteredProducts.length} productos)
                </h2>
                <p className="pam-card-desc">
                  Utiliza esta tabla para excepciones específicas (ej. un producto especial dentro de una categoría que se deba preparar en otra estación).
                </p>
              </div>

              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <select
                  className="pam-select"
                  value={selectedCategoryFilter}
                  onChange={(e) => setSelectedCategoryFilter(e.target.value)}
                  style={{ width: 220 }}
                >
                  <option value="all">Todas las categorías</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>

                <div style={{ position: 'relative', width: 260 }}>
                  <Search
                    size={18}
                    style={{
                      position: 'absolute',
                      left: 12,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: '#94a3b8',
                    }}
                  />
                  <input
                    type="text"
                    className="pam-input"
                    value={productSearch}
                    onChange={(e) => setProductSearch(e.target.value)}
                    placeholder="Buscar por nombre o clave…"
                    style={{ paddingLeft: 38 }}
                  />
                </div>
              </div>
            </div>

            <div className="pam-table-container">
              <table className="pam-table">
                <thead>
                  <tr>
                    <th style={{ width: 120 }}>Clave SKU</th>
                    <th>Producto</th>
                    <th style={{ width: 180 }}>Categoría</th>
                    <th style={{ width: 340 }}>Área de Comanda Destino</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProducts.slice(0, 150).map((prod) => {
                    const assigned = productAreas[prod.id] || '';
                    return (
                      <tr key={prod.id}>
                        <td style={{ fontFamily: 'monospace', color: '#64748b', fontWeight: 600 }}>
                          {prod.sku || '—'}
                        </td>
                        <td style={{ fontWeight: 700, color: '#0f172a' }}>
                          {prod.name}
                        </td>
                        <td style={{ color: '#475569' }}>
                          <span className="pam-badge pam-badge-packing">
                            {prod.category_name ||
                              categories.find((c) => c.id === prod.category_id)?.name ||
                              'General'}
                          </span>
                        </td>
                        <td>
                          <select
                            className="pam-select"
                            value={assigned}
                            onChange={(e) => handleAssignProductArea(prod.id, e.target.value)}
                          >
                            <option value="">
                              Heredar del grupo ({categories.find((c) => c.id === prod.category_id)?.name || 'Automático'})
                            </option>
                            {areas.map((a) => (
                              <option key={a.code} value={a.code}>
                                {a.name} → {areaPrinters[a.code]?.printer_name || a.code}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}

      {/* TAB 3: SIMULADOR DE TICKETS (42 COLUMNAS) */}
      {activeTab === 'simulator' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <section className="pam-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 14 }}>
              <div>
                <h2 className="pam-card-title">
                  <FileText size={22} color="#059669" />
                  Simulador de Impresión Térmica en Vivo (42 Columnas Sin Desfase)
                </h2>
                <p className="pam-card-desc">
                  Este simulador representa exactamente cómo se enviará el texto binario ESC/POS a cada impresora física. En un pedido con Ensalada + Baguettes + Bebida, observa la separación limpia de tickets:
                </p>
              </div>

              <button
                type="button"
                className="pam-btn pam-btn-secondary pam-btn-sm"
                onClick={() => void refreshSamplePreview()}
              >
                <RefreshCw size={14} />
                Actualizar Simulación
              </button>
            </div>

            {testPrintStatus && (
              <div
                role="status"
                style={{
                  background: '#eff6ff',
                  border: '1px solid #93c5fd',
                  color: '#1e3a8a',
                  padding: '12px 16px',
                  borderRadius: 10,
                  fontSize: '0.9rem',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <AlertCircle size={18} />
                {testPrintStatus}
              </div>
            )}

            {previewData && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20 }}>
                {/* Ticket de Venta de Caja */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.9rem', fontWeight: 800, color: '#0f172a' }}>
                      Ticket de Venta del Cliente
                    </span>
                    <span className="pam-badge pam-badge-packing">
                      Impresora: {previewData.ticket.printer_name || 'caja'}
                    </span>
                  </div>

                  <div className="pam-sim-paper">
                    {previewData.ticket.text}
                  </div>

                  <button
                    type="button"
                    className="pam-btn pam-btn-secondary pam-btn-sm"
                    disabled={testingPrint}
                    onClick={() =>
                      void handleSendTestToBridge(
                        previewData.ticket.printer_name,
                        previewData.ticket.host,
                        previewData.ticket.port,
                        previewData.ticket.text,
                        'Ticket de Cliente'
                      )
                    }
                  >
                    <Printer size={14} />
                    Imprimir este Ticket en Caja
                  </button>
                </div>

                {/* Comandas separadas por Área */}
                {previewData.comandas.map((comanda) => (
                  <div key={comanda.area_code} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: 800, color: '#047857' }}>
                        Comanda: {comanda.area_name} ({comanda.line_count} prod.)
                      </span>
                      <span className={`pam-badge ${getStationBadgeClass(comanda.area_code)}`}>
                        Impresora: {comanda.printer_name || 'barra'}
                      </span>
                    </div>

                    <div className="pam-sim-paper" style={{ borderLeft: '4px solid #10b981' }}>
                      {comanda.text}
                    </div>

                    <button
                      type="button"
                      className="pam-btn pam-btn-secondary pam-btn-sm"
                      disabled={testingPrint}
                      onClick={() =>
                        void handleSendTestToBridge(
                          comanda.printer_name,
                          comanda.host,
                          comanda.port,
                          comanda.text,
                          `Comanda ${comanda.area_name}`
                        )
                      }
                    >
                      <Printer size={14} />
                      Imprimir Comanda {comanda.area_name}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* TAB 4: PUENTE PC Y DIAGNÓSTICO */}
      {activeTab === 'bridge' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Estado del Puente en esta Computadora */}
          <section className="pam-card">
            <h2 className="pam-card-title">
              <Laptop size={22} color="#059669" />
              Diagnóstico del Puente Local en la Computadora
            </h2>

            <div className={`pam-status-banner ${bridgeStatus.online ? 'online' : 'offline'}`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Wifi size={20} />
                <span style={{ fontWeight: 600 }}>{bridgeStatus.message}</span>
              </div>

              <button
                type="button"
                className="pam-btn pam-btn-secondary pam-btn-sm"
                onClick={() => void detectLocalPrinters(bridgeUrl)}
                disabled={bridgeStatus.checking}
              >
                <RefreshCw size={14} className={bridgeStatus.checking ? 'spin' : ''} />
                Consultar Estado
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
              <label className="pam-label">URL del Puente Local (Servicio en Segundo Plano)</label>
              <div style={{ display: 'flex', gap: 12 }}>
                <input
                  type="text"
                  className="pam-input"
                  value={bridgeUrl}
                  onChange={(e) => setBridgeUrl(e.target.value)}
                  style={{ maxWidth: 360 }}
                />
                <button
                  type="button"
                  className="pam-btn pam-btn-secondary"
                  onClick={() => void detectLocalPrinters(bridgeUrl)}
                >
                  Probar Conexión
                </button>
              </div>
              <span className="pam-hint">
                Por defecto escucha en <code>http://127.0.0.1:9123</code> en la PC donde está conectado el cajón de dinero y las impresoras.
              </span>
            </div>

            {/* Impresoras Detectadas en Windows */}
            <div style={{ marginTop: 16 }}>
              <h3 style={{ margin: '0 0 8px', fontSize: '0.95rem', fontWeight: 700, color: '#0f172a' }}>
                Impresoras registradas en el Panel de Control de esta PC:
              </h3>
              {osPrinters.length > 0 ? (
                <div className="pam-pills-container">
                  {osPrinters.map((p) => (
                    <span key={p} className="pam-pill active">
                      <Check size={14} />
                      {p}
                    </span>
                  ))}
                </div>
              ) : (
                <p style={{ margin: 0, fontSize: '0.88rem', color: '#64748b' }}>
                  Aún no se detectan impresoras. Inicia el puente abajo para listar automáticamente tus impresoras de Windows (ej. caja, ensaladas, barra).
                </p>
              )}
            </div>
          </section>

          {/* Tarjetas de Descarga del Puente */}
          <section className="pam-card">
            <h2 className="pam-card-title">
              <Download size={22} color="#0284c7" />
              Descarga del Puente Kiwi (Sin Instalaciones Complejas)
            </h2>
            <p className="pam-card-desc">
              El puente es un ejecutable ligero que corre en la PC de caja para recibir los tickets y enviarlos a las impresoras térmicas USB o de red sin cuadros de diálogo de Windows.
            </p>

            <div className="pam-download-grid">
              <div className="pam-download-card">
                <h4>
                  <Laptop size={18} />
                  Windows (Recomendado para PC de Caja)
                </h4>
                <p>
                  Archivo <code>.bat</code> con PowerShell y soporte nativo Win32 Spooler. No requiere instalar Python ni programas externos.
                </p>
                <button
                  type="button"
                  className="pam-btn pam-btn-primary"
                  onClick={() => {
                    const content = buildWindowsBatch(
                      ticketPrinter.printer_name,
                      ticketPrinter.host,
                      ticketPrinter.port
                    );
                    triggerDownload(content, 'Iniciar-Impresora-Kiwi-POS.bat', 'application/x-bat');
                  }}
                >
                  <Download size={16} />
                  Descargar Iniciar-Impresora-Kiwi-POS.bat
                </button>
              </div>

              <div className="pam-download-card">
                <h4>
                  <ExternalLink size={18} />
                  Linux / macOS (Multiplataforma)
                </h4>
                <p>
                  Script ligero en Python 3 para servidores o terminales con sistema CUPS o impresoras Ethernet directas.
                </p>
                <button
                  type="button"
                  className="pam-btn pam-btn-secondary"
                  onClick={() => {
                    const content = buildPythonScript(
                      ticketPrinter.printer_name,
                      ticketPrinter.host,
                      ticketPrinter.port
                    );
                    triggerDownload(content, 'kiwi_print_bridge.py', 'text/x-python');
                  }}
                >
                  <Download size={16} />
                  Descargar kiwi_print_bridge.py
                </button>
              </div>
            </div>

            {/* Pasos de Configuración en Windows */}
            <div style={{ marginTop: 16 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: '0.95rem', fontWeight: 700, color: '#0f172a' }}>
                Pasos para activar en la computadora de caja:
              </h3>
              <ul className="pam-steps-list">
                <li className="pam-step-item">
                  <span className="pam-step-number">1</span>
                  <span>
                    Descarga el archivo <code>Iniciar-Impresora-Kiwi-POS.bat</code> en la computadora donde están conectadas las impresoras.
                  </span>
                </li>
                <li className="pam-step-item">
                  <span className="pam-step-number">2</span>
                  <span>
                    Haz doble clic sobre el archivo descargado. Se abrirá una ventana negra que dirá <em>[LISTO] Puente activo en http://127.0.0.1:9123</em>.
                  </span>
                </li>
                <li className="pam-step-item">
                  <span className="pam-step-number">3</span>
                  <span>
                    Regresa a esta pantalla o al Punto de Venta. Las impresoras se detectarán automáticamente y la comanda de ensaladas, baguettes y ticket de cliente saldrán de inmediato en cada una.
                  </span>
                </li>
              </ul>
            </div>
          </section>
        </div>
      )}
    </div>
  );
};

export default PrintAreasManager;
