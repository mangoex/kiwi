import React, { useEffect, useMemo, useState } from 'react';
import { fetchApi } from '@restaurantos/api-client';
import {
  CheckCircle2,
  Download,
  Layers,
  Plus,
  Printer,
  RefreshCw,
  Search,
  Trash2,
  Wifi,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

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
              ? `Puente activo · ${detected.length} impresoras detectadas en la PC: ${detected.join(', ')}`
              : 'Puente activo en esta PC · Listo para enviar a impresoras (caja, ensaladas, barra) o IP:9100',
        });
      } else {
        setBridgeStatus({
          checking: false,
          online: false,
          message:
            'Puente local aún no iniciado en esta PC. Puedes escribir los nombres de tus impresoras (caja, ensaladas, barra) y descargar el puente abajo.',
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
        '✓ Áreas de impresión, impresoras del sistema y asignación de productos guardadas correctamente.'
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
          `✓ ${label} enviada directamente a la impresora "${targetPrinterName || targetHost}"`
        );
      } else {
        setTestPrintStatus(
          `Puente local no disponible en este momento; se mostrará vista previa de 42 columnas abajo.`
        );
      }
    } catch {
      setTestPrintStatus(
        `Inicia el Puente Local Kiwi (.bat) en la PC de caja para enviar directo a "${targetPrinterName || targetHost}".`
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

  return (
    <div style={{ padding: '24px', maxWidth: 1200, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <datalist id="admin-os-printers-datalist">
        {suggestedPrinters.map((p) => (
          <option key={p} value={p} />
        ))}
      </datalist>

      {/* Encabezado */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 16,
          background: '#ffffff',
          padding: '20px 24px',
          borderRadius: 14,
          border: '1px solid #e2e8f0',
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: '1.35rem', color: '#0f172a' }}>
            Áreas de Impresión de Comandas y Asignación de Impresoras (PC / Red)
          </h1>
          <p style={{ margin: '6px 0 0', color: '#475569', fontSize: '0.92rem', maxWidth: 760 }}>
            Configura las <strong>Áreas de Impresión</strong> (ej. <code>ENSALADAS</code>,{' '}
            <code>BAGUETTES(RAPIDO)</code>, <code>BARRA</code>, <code>BEBIDAS</code>), asígnales la
            impresora del <strong>Panel de Control de la Computadora</strong> (ej.{' '}
            <code>caja</code>, <code>ensaladas</code>, <code>barra</code>) y vincula tus grupos o
            productos para que cada comanda se imprima por separado en su estación.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button
            type="button"
            className="retro-btn"
            onClick={() => navigate('/products')}
            style={{ padding: '9px 14px', fontWeight: 600 }}
          >
            Ir a Catálogo de Productos
          </button>
          <button
            type="button"
            className="retro-btn primary"
            disabled={saving}
            onClick={() => void handleSaveAll()}
            style={{
              padding: '9px 16px',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              background: '#16a34a',
              color: '#ffffff',
              border: 'none',
              borderRadius: 8,
              cursor: 'pointer',
            }}
          >
            <CheckCircle2 size={16} />
            {saving ? 'Guardando…' : 'Guardar Cambios'}
          </button>
        </div>
      </div>

      {saveMessage && (
        <div
          role="status"
          style={{
            background: '#ecfdf5',
            border: '1px solid #10b981',
            color: '#065f46',
            padding: '12px 16px',
            borderRadius: 10,
            fontWeight: 700,
          }}
        >
          {saveMessage}
        </div>
      )}

      {/* Bloque 1 y 2: Conexión con Impresoras del Panel de Control de la PC + Mapeo por Área */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(520px, 1fr))', gap: 20 }}>
        {/* Panel Izquierdo: Impresora de Caja + Impresoras por Área */}
        <section
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 14,
            padding: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.05rem', color: '#0f172a' }}>
                1. Impresoras de la Computadora por Área de Impresión
              </h2>
              <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#64748b' }}>
                Selecciona o escribe el nombre exacto de la impresora en Windows (Panel de Control) o su IP:9100.
              </p>
            </div>
            <button
              type="button"
              className="retro-btn"
              onClick={() => void detectLocalPrinters(bridgeUrl)}
              disabled={bridgeStatus.checking}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 12px', fontSize: '0.8rem' }}
            >
              <RefreshCw size={14} />
              {bridgeStatus.checking ? 'Detectando…' : 'Detectar Impresoras PC'}
            </button>
          </div>

          <div
            style={{
              background: bridgeStatus.online ? '#f0fdf4' : '#fffbeb',
              border: `1px solid ${bridgeStatus.online ? '#bbf7d0' : '#fde68a'}`,
              borderRadius: 8,
              padding: '8px 12px',
              fontSize: '0.8rem',
              color: bridgeStatus.online ? '#166534' : '#92400e',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Wifi size={15} />
            <span>{bridgeStatus.message}</span>
          </div>

          {/* Impresora de Caja (Ticket de Venta del Cliente) */}
          <div
            style={{
              background: '#f8fafc',
              border: '1px solid #cbd5e1',
              borderRadius: 10,
              padding: 12,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <div style={{ fontWeight: 800, fontSize: '0.88rem', color: '#0f172a' }}>
              NOTA DEL CLIENTE (TICKET DE COMPRA EN CAJA)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1.2fr 0.7fr', gap: 8 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.76rem', color: '#475569' }}>
                <span>Impresora en Panel de Control (PC)</span>
                <input
                  type="text"
                  list="admin-os-printers-datalist"
                  className="retro-input"
                  value={ticketPrinter.printer_name}
                  onChange={(e) => setTicketPrinter({ ...ticketPrinter, printer_name: e.target.value })}
                  placeholder="caja"
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.76rem', color: '#475569' }}>
                <span>IP Red (Opcional)</span>
                <input
                  type="text"
                  className="retro-input"
                  value={ticketPrinter.host}
                  onChange={(e) => setTicketPrinter({ ...ticketPrinter, host: e.target.value })}
                  placeholder="Ej. 192.168.1.200"
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.76rem', color: '#475569' }}>
                <span>Puerto</span>
                <input
                  type="number"
                  className="retro-input"
                  value={ticketPrinter.port}
                  onChange={(e) => setTicketPrinter({ ...ticketPrinter, port: Number(e.target.value) || 9100 })}
                />
              </label>
            </div>
          </div>

          {/* Lista de Áreas de Impresión de Comandas */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
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
                  style={{
                    border: '1px solid #e2e8f0',
                    borderRadius: 10,
                    padding: 12,
                    background: area.print_comanda ? '#ffffff' : '#f8fafc',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: '0.88rem' }}>
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
                      <span>{area.name}</span>
                      <span
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          padding: '2px 7px',
                          borderRadius: 999,
                          background: '#f1f5f9',
                          color: '#475569',
                        }}
                      >
                        código: {area.code}
                      </span>
                    </label>

                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      {area.print_comanda && (
                        <button
                          type="button"
                          className="retro-btn"
                          disabled={testingPrint}
                          onClick={() => {
                            const comandaText =
                              previewData?.comandas.find((c) => c.area_code === area.code)?.text ||
                              `*** COMANDA DE COCINA ***\n${area.name} ORDEN: 3\nESTACION: ${area.name}\n------------------------------------------\n[ 1 ] PRODUCTO DE PRUEBA (${area.name})\n------------------------------------------`;
                            void handleSendTestToBridge(
                              target.printer_name,
                              target.host,
                              target.port,
                              comandaText,
                              `Comanda ${area.name}`
                            );
                          }}
                          style={{ fontSize: '0.75rem', padding: '4px 9px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                        >
                          <Printer size={13} />
                          Probar
                        </button>
                      )}
                      {!area.is_system && (
                        <button
                          type="button"
                          className="retro-btn"
                          onClick={() => handleRemoveArea(area.code)}
                          style={{ fontSize: '0.75rem', padding: '4px 8px', color: '#dc2626' }}
                          title="Eliminar área"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  </div>

                  {area.print_comanda && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1.3fr 1fr', gap: 8 }}>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.74rem', color: '#475569' }}>
                        <span>Título impreso en Comanda</span>
                        <input
                          type="text"
                          className="retro-input"
                          value={area.name}
                          onChange={(e) =>
                            setAreas(
                              areas.map((a) =>
                                a.code === area.code ? { ...a, name: e.target.value.toUpperCase() } : a
                              )
                            )
                          }
                        />
                      </label>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.74rem', color: '#475569' }}>
                        <span>Impresora en Panel de Control (PC)</span>
                        <input
                          type="text"
                          list="admin-os-printers-datalist"
                          className="retro-input"
                          value={target.printer_name}
                          onChange={(e) =>
                            setAreaPrinters({
                              ...areaPrinters,
                              [area.code]: { ...target, printer_name: e.target.value },
                            })
                          }
                          placeholder={area.code === 'salads' ? 'ensaladas' : 'barra'}
                        />
                      </label>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.74rem', color: '#475569' }}>
                        <span>IP Red (Opcional)</span>
                        <input
                          type="text"
                          className="retro-input"
                          value={target.host}
                          onChange={(e) =>
                            setAreaPrinters({
                              ...areaPrinters,
                              [area.code]: { ...target, host: e.target.value },
                            })
                          }
                          placeholder="Ej. 192.168.1.201"
                        />
                      </label>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Agregar nueva Área de Impresión */}
          <div
            style={{
              borderTop: '1px dashed #cbd5e1',
              paddingTop: 12,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <div style={{ fontWeight: 700, fontSize: '0.84rem', color: '#0f172a' }}>
              + Agregar Nueva Área de Impresión (ej. Postres, Plancha, Jugos)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr 1fr 1.2fr auto', gap: 8, alignItems: 'flex-end' }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.74rem' }}>
                <span>Código</span>
                <input
                  type="text"
                  className="retro-input"
                  value={newAreaCode}
                  onChange={(e) => setNewAreaCode(e.target.value)}
                  placeholder="postres"
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.74rem' }}>
                <span>Nombre en Comanda</span>
                <input
                  type="text"
                  className="retro-input"
                  value={newAreaName}
                  onChange={(e) => setNewAreaName(e.target.value)}
                  placeholder="REPOSTERIA FRIA"
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.74rem' }}>
                <span>Estación KDS</span>
                <select
                  className="retro-input"
                  value={newAreaStation}
                  onChange={(e) =>
                    setNewAreaStation(e.target.value as 'kitchen' | 'drinks' | 'packing')
                  }
                >
                  <option value="kitchen">Cocina / Barra</option>
                  <option value="drinks">Bebidas</option>
                  <option value="packing">Empaque</option>
                </select>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.74rem' }}>
                <span>Impresora PC</span>
                <input
                  type="text"
                  list="admin-os-printers-datalist"
                  className="retro-input"
                  value={newAreaPrinterName}
                  onChange={(e) => setNewAreaPrinterName(e.target.value)}
                  placeholder="barra"
                />
              </label>
              <button
                type="button"
                className="retro-btn"
                onClick={handleAddArea}
                style={{ padding: '7px 12px', display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 700 }}
              >
                <Plus size={14} />
                Agregar
              </button>
            </div>
          </div>
        </section>

        {/* Panel Derecho: Vista Previa Real de Separación de Ticket y Comandas (42 columnas exactas) */}
        <section
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 14,
            padding: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: '1.05rem', color: '#0f172a' }}>
              2. Vista Previa de Separación de Ticket y Comandas (42 Columnas Sin Desfase)
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#64748b' }}>
              Simulación de un mismo pedido con Ensalada + Baguette + Bebida: la nota del cliente
              sale en <code>{ticketPrinter.printer_name || 'caja'}</code> y cada área recibe
              únicamente sus productos con su propio corte de papel.
            </p>
          </div>

          {testPrintStatus && (
            <div
              role="status"
              style={{
                background: '#eff6ff',
                border: '1px solid #93c5fd',
                color: '#1e3a8a',
                padding: '8px 12px',
                borderRadius: 8,
                fontSize: '0.82rem',
                fontWeight: 600,
              }}
            >
              {testPrintStatus}
            </div>
          )}

          {previewData && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 540, overflowY: 'auto', background: '#f1f5f9', padding: 12, borderRadius: 10 }}>
              <div>
                <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#0f172a', marginBottom: 4 }}>
                  TICKET DE VENTA DEL CLIENTE → Impresora: <code>{previewData.ticket.printer_name || 'caja'}</code>
                </div>
                <pre
                  style={{
                    margin: 0,
                    background: '#ffffff',
                    padding: '10px 12px',
                    borderRadius: 6,
                    border: '1px solid #cbd5e1',
                    fontFamily: "'Courier New', Consolas, monospace",
                    fontSize: '11px',
                    lineHeight: 1.2,
                    whiteSpace: 'pre',
                    overflowX: 'auto',
                  }}
                >
                  {previewData.ticket.text}
                </pre>
              </div>

              {previewData.comandas.map((comanda) => (
                <div key={comanda.area_code}>
                  <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#047857', marginBottom: 4 }}>
                    COMANDA ÁREA {comanda.area_name} ({comanda.line_count} prod.) → Impresora:{' '}
                    <code>{comanda.printer_name || 'barra'}</code>
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      background: '#ffffff',
                      padding: '10px 12px',
                      borderRadius: 6,
                      border: '1px solid #a7f3d0',
                      fontFamily: "'Courier New', Consolas, monospace",
                      fontSize: '11px',
                      lineHeight: 1.2,
                      whiteSpace: 'pre',
                      overflowX: 'auto',
                    }}
                  >
                    {comanda.text}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Bloque 3: Asignación por Grupo (Categoría) y por Producto */}
      <section
        style={{
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: 14,
          padding: 20,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: '1.05rem', color: '#0f172a', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Layers size={18} />
            3. Asignación Rápida de Grupos (Categorías) y Productos a Áreas de Impresión
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: '0.84rem', color: '#64748b' }}>
            Puedes asignar un Grupo completo (ej. todas las <strong>ENSALADAS</strong> al área{' '}
            <code>ENSALADAS</code> y todos los <strong>BAGUETTES</strong> a{' '}
            <code>BAGUETTES(RAPIDO)</code>) o personalizar producto por producto.
          </p>
        </div>

        {/* Asignación por Grupo / Categoría */}
        {categories.length > 0 && (
          <div>
            <h3 style={{ margin: '0 0 8px', fontSize: '0.9rem', color: '#334155' }}>
              Área de Impresión predeterminada por Grupo / Categoría
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 10 }}>
              {categories.map((cat) => {
                const currentArea =
                  categoryAreas[cat.id] || categoryAreas[cat.name.toUpperCase()] || '';
                return (
                  <div
                    key={cat.id}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 4,
                      padding: '8px 10px',
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: 8,
                    }}
                  >
                    <span style={{ fontWeight: 700, fontSize: '0.82rem', color: '#0f172a' }}>
                      {cat.name}
                    </span>
                    <select
                      className="retro-input"
                      value={currentArea}
                      onChange={(e) => handleAssignCategoryArea(cat, e.target.value)}
                      style={{ fontSize: '0.8rem' }}
                    >
                      <option value="">Automático por nombre / producto</option>
                      {areas.map((a) => (
                        <option key={a.code} value={a.code}>
                          {a.name} ({areaPrinters[a.code]?.printer_name || 'sin impresora'})
                        </option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Asignación individual por Producto */}
        <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 10 }}>
            <h3 style={{ margin: 0, fontSize: '0.9rem', color: '#334155' }}>
              Área de Impresión por Producto ({filteredProducts.length} productos)
            </h3>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <select
                className="retro-input"
                value={selectedCategoryFilter}
                onChange={(e) => setSelectedCategoryFilter(e.target.value)}
                style={{ fontSize: '0.82rem', minWidth: 180 }}
              >
                <option value="all">Todos los grupos</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <div style={{ position: 'relative', minWidth: 240 }}>
                <Search size={14} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                <input
                  type="text"
                  className="retro-input"
                  value={productSearch}
                  onChange={(e) => setProductSearch(e.target.value)}
                  placeholder="Buscar producto o clave…"
                  style={{ paddingLeft: 28, fontSize: '0.82rem', width: '100%' }}
                />
              </div>
            </div>
          </div>

          <div style={{ maxHeight: 340, overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: 8 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: '#f8fafc', textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>
                  <th style={{ padding: '8px 12px' }}>Clave</th>
                  <th style={{ padding: '8px 12px' }}>Producto</th>
                  <th style={{ padding: '8px 12px' }}>Grupo</th>
                  <th style={{ padding: '8px 12px' }}>Área de Impresión de Comanda</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.slice(0, 120).map((prod) => {
                  const assigned = productAreas[prod.id] || '';
                  return (
                    <tr key={prod.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '6px 12px', fontFamily: 'monospace', color: '#64748b' }}>
                        {prod.sku}
                      </td>
                      <td style={{ padding: '6px 12px', fontWeight: 600, color: '#0f172a' }}>
                        {prod.name}
                      </td>
                      <td style={{ padding: '6px 12px', color: '#475569' }}>
                        {prod.category_name ||
                          categories.find((c) => c.id === prod.category_id)?.name ||
                          '—'}
                      </td>
                      <td style={{ padding: '6px 12px' }}>
                        <select
                          className="retro-input"
                          value={assigned}
                          onChange={(e) => handleAssignProductArea(prod.id, e.target.value)}
                          style={{ fontSize: '0.8rem', width: '100%', maxWidth: 300 }}
                        >
                          <option value="">
                            Heredar del grupo / detección automática ({prod.station || 'kitchen'})
                          </option>
                          {areas.map((a) => (
                            <option key={a.code} value={a.code}>
                              {a.name} → Impresora: {areaPrinters[a.code]?.printer_name || 'sin impresora'}
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
        </div>
      </section>
    </div>
  );
};

export default PrintAreasManager;
