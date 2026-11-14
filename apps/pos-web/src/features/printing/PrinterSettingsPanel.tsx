import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Download,
  Laptop,
  Plus,
  Printer,
  RefreshCw,
  Trash2,
  Wifi,
} from 'lucide-react';
import {
  buildPythonPrintBridgeScript,
  buildWindowsPrintBridgeBat,
  checkPrintBridgeHealth,
  dispatchPosPrintJob,
  fetchLocalSystemPrinters,
  loadPrinterConfig,
  savePrinterConfig,
  syncPrintRoutingFromBackend,
  type AutoPrintCopies,
  type PosPrinterConfig,
  type PrinterConnectionMode,
} from './printerService';
import type { TicketPrintData, KitchenPrintData, PrintAreaDefinition } from './receiptFormatter';
import './PrinterSettingsPanel.css';

export function PrinterSettingsPanel({ branchName }: { branchName?: string }) {
  const [config, setConfig] = useState<PosPrinterConfig>(() => loadPrinterConfig());
  const [osPrinters, setOsPrinters] = useState<string[]>([]);
  const [savedNotice, setSavedNotice] = useState('');
  const [testNotice, setTestNotice] = useState('');
  const [testing, setTesting] = useState(false);
  const [newAreaCode, setNewAreaCode] = useState('');
  const [newAreaName, setNewAreaName] = useState('');
  const [newAreaPrinter, setNewAreaPrinter] = useState('');
  const [bridgeStatus, setBridgeStatus] = useState<{
    checking: boolean;
    online: boolean;
    detail: string;
  }>({ checking: false, online: false, detail: 'Sin verificar' });

  const verifyBridge = async (urlToUse?: string) => {
    const targetUrl = urlToUse ?? config.bridgeUrl;
    setBridgeStatus({
      checking: true,
      online: false,
      detail: 'Verificando puente local e impresoras de la PC…',
    });
    const [res, printersRes] = await Promise.all([
      checkPrintBridgeHealth(targetUrl),
      fetchLocalSystemPrinters(targetUrl),
    ]);
    if (printersRes.ok && printersRes.printers.length > 0) {
      setOsPrinters(printersRes.printers);
    }
    if (res.online) {
      const printerCount = printersRes.printers.length;
      setBridgeStatus({
        checking: false,
        online: true,
        detail: `Puente Kiwi conectado en esta PC · ${
          printerCount > 0
            ? `${printerCount} impresoras detectadas: ${printersRes.printers.join(', ')}`
            : 'Listo para imprimir automáticamente en Caja, Ensaladas, Barra'
        }`,
      });
    } else {
      setBridgeStatus({
        checking: false,
        online: false,
        detail:
          'Puente local no detectado en esta PC. Se requiere para que los tickets y comandas se impriman solos sin que salga la ventana de confirmación de Chrome.',
      });
    }
  };

  useEffect(() => {
    void verifyBridge(config.bridgeUrl);
    void syncPrintRoutingFromBackend().then((synced) => setConfig(synced));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async () => {
    const saved = savePrinterConfig(config);
    setConfig(saved);
    try {
      const areaPrintersPayload: Record<string, Record<string, unknown>> = {};
      for (const [code, target] of Object.entries(saved.areaPrinters)) {
        areaPrintersPayload[code] = {
          enabled: target.enabled,
          printer_name: target.printerName,
          host: target.host,
          port: target.port,
        };
      }
      await fetch('/api/v1/print-routing', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          areas: saved.printAreas.map((a) => ({
            code: a.code,
            name: a.name,
            station: a.station,
            print_comanda: a.printComanda,
            sort_order: a.sortOrder,
          })),
          product_areas: saved.productPrintAreas,
          category_areas: saved.categoryPrintAreas,
          ticket_printer: {
            enabled: true,
            printer_name: saved.ticketPrinterName,
            host: saved.ticketPrinterHost,
            port: saved.ticketPrinterPort,
          },
          area_printers: areaPrintersPayload,
        }),
      });
    } catch {
      // Persistencia local
    }
    setSavedNotice('✓ Configuración de impresoras y comandas guardada correctamente.');
    void verifyBridge(saved.bridgeUrl);
    setTimeout(() => setSavedNotice(''), 4000);
  };

  const handleAddCustomArea = () => {
    const cleanCode = newAreaCode.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
    const cleanName = newAreaName.trim().toUpperCase();
    if (!cleanCode || !cleanName) return;
    const nextAreas: PrintAreaDefinition[] = [
      ...config.printAreas.filter((a) => a.code !== cleanCode),
      {
        code: cleanCode,
        name: cleanName,
        station: 'kitchen',
        printComanda: true,
        sortOrder: config.printAreas.length + 1,
        isSystem: false,
      },
    ];
    setConfig({
      ...config,
      printAreas: nextAreas,
      areaPrinters: {
        ...config.areaPrinters,
        [cleanCode]: {
          enabled: true,
          printerName: newAreaPrinter.trim() || cleanCode,
          host: '',
          port: 9100,
        },
      },
    });
    setNewAreaCode('');
    setNewAreaName('');
    setNewAreaPrinter('');
  };

  const handleRemoveCustomArea = (code: string) => {
    const nextAreas = config.printAreas.filter((a) => a.code !== code);
    const nextPrinters = { ...config.areaPrinters };
    delete nextPrinters[code];
    setConfig({
      ...config,
      printAreas: nextAreas,
      areaPrinters: nextPrinters,
    });
  };

  const handleTestPrint = async (targetAreaCode?: string) => {
    if (testing) return;
    setTesting(true);
    setTestNotice('');
    try {
      const saved = savePrinterConfig(config);
      setConfig(saved);
      const nowStr = new Date().toLocaleString('es-MX');
      const sampleTicket: TicketPrintData = {
        folio: 'SUC04-000003',
        orderNumber: 3,
        createdAt: nowStr,
        customerName: 'MIGUEL GONZALEZ',
        serviceTypeLabel: branchName ? `SUCURSAL ${branchName.toUpperCase()}` : 'CONSUMIR AQUI',
        lines: [
          {
            quantity: 1,
            productName: 'ENSALADA DE ARANDANO',
            categoryName: 'ENSALADAS',
            printArea: 'salads',
            totalCents: 13000,
            modifiers: ['ADEREZO RANCH'],
          },
          {
            quantity: 1,
            productName: 'SANDWICH INTEGRAL POLLO BBQ',
            categoryName: 'BAGUETTES',
            printArea: 'baguettes',
            totalCents: 11500,
            modifiers: ['ADEREZO DE CHIPOTLE CHI', 'MANCHEGUITO'],
          },
          {
            quantity: 1,
            productName: 'CUERNITO BBQ',
            categoryName: 'BAGUETTES',
            printArea: 'baguettes',
            totalCents: 10500,
            modifiers: ['ADEREZO DE CHIPOTLE CHI'],
          },
          {
            quantity: 1,
            productName: 'AGUA DE FRESA LIMON CHICA',
            categoryName: 'AGUAS',
            printArea: 'drinks',
            totalCents: 3500,
          },
        ],
        subtotalCents: 33190,
        taxCents: 5310,
        totalCents: 38500,
        cashTender: {
          receivedCents: 40000,
          changeCents: 1500,
        },
      };
      const sampleKitchen: KitchenPrintData = {
        folio: 'SUC04-000003',
        orderNumber: 3,
        createdAt: nowStr,
        serviceTypeLabel: branchName ? `SUCURSAL ${branchName.toUpperCase()}` : 'CONSUMIR AQUI',
        customerName: 'MIGUEL GONZALEZ',
        lines: sampleTicket.lines,
        orderNotes: 'COMANDA DE PRUEBA SEPARADA POR AREA DE IMPRESION',
      };

      const result = await dispatchPosPrintJob({
        ticketData: sampleTicket,
        kitchenData: sampleKitchen,
        copies: targetAreaCode ? 'kitchen' : saved.autoPrintCopies,
        targetAreaCode: targetAreaCode || null,
        kickDrawer: false,
        config: saved,
      });
      setTestNotice(result.ok ? `✓ ${result.message}` : result.message);
    } finally {
      setTesting(false);
    }
  };

  const downloadFile = (filename: string, content: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const suggestedPrinters = Array.from(
    new Set(['caja', 'ensaladas', 'barra', 'bebidas', ...osPrinters])
  );

  const getStationBadgeClass = (code: string) => {
    if (code === 'salads') return 'psp-badge-salads';
    if (code === 'baguettes') return 'psp-badge-baguettes';
    if (code === 'kitchen') return 'psp-badge-kitchen';
    if (code === 'drinks') return 'psp-badge-drinks';
    return 'psp-badge-packing';
  };

  return (
    <div className="psp-container">
      <datalist id="kiwi-os-printers-list">
        {suggestedPrinters.map((pName) => (
          <option key={pName} value={pName} />
        ))}
      </datalist>

      {/* Encabezado */}
      <header className="psp-header">
        <div>
          <h2 className="psp-title">
            <Printer size={26} color="#10b981" />
            Configuración de Impresoras y Comandas
            {branchName ? ` (${branchName})` : ''}
          </h2>
          <p className="psp-subtitle">
            Asigna las impresoras físicas de esta computadora a la <strong>Nota de Venta (Caja)</strong> y a cada <strong>Área de Preparación</strong> (Ensaladas, Baguettes, Barra, Bebidas).
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button
            type="button"
            className="psp-btn psp-btn-secondary"
            onClick={() => void handleTestPrint()}
            disabled={testing}
          >
            <Printer size={15} />
            {testing ? 'Probando…' : 'Probar Pedido Completo'}
          </button>
          <button
            type="button"
            className="psp-btn psp-btn-primary"
            onClick={() => void handleSave()}
          >
            <CheckCircle2 size={16} />
            Guardar Cambios
          </button>
        </div>
      </header>

      {/* Avisos de confirmación */}
      {savedNotice && (
        <div
          role="status"
          style={{
            background: '#ecfdf5',
            border: '1px solid #10b981',
            color: '#065f46',
            padding: '12px 16px',
            borderRadius: 10,
            fontWeight: 700,
            fontSize: '0.92rem',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Check size={18} />
          {savedNotice}
        </div>
      )}

      {testNotice && (
        <div
          role="status"
          style={{
            background: '#eff6ff',
            border: '1px solid #93c5fd',
            color: '#1e3a8a',
            padding: '12px 16px',
            borderRadius: 10,
            fontWeight: 600,
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <AlertCircle size={18} />
          {testNotice}
        </div>
      )}

      {/* TARJETA 1: ESTADO DEL PUENTE Y AUTOMATIZACIÓN (El corazón de la solución) */}
      <section className="psp-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <h3 className="psp-card-title">
              <Laptop size={20} color={bridgeStatus.online ? '#10b981' : '#f59e0b'} />
              1. Conexión con las Impresoras de esta Computadora (Puente Kiwi)
            </h3>
            <p className="psp-card-desc">
              Permite que las notas salgan solas en automático en sus impresoras sin que Chrome abra la ventana de diálogo cada vez.
            </p>
          </div>

          <button
            type="button"
            className="psp-btn psp-btn-secondary psp-btn-sm"
            onClick={() => void verifyBridge(config.bridgeUrl)}
            disabled={bridgeStatus.checking}
          >
            <RefreshCw size={14} className={bridgeStatus.checking ? 'spin' : ''} />
            {bridgeStatus.checking ? 'Verificando…' : 'Detectar Impresoras PC'}
          </button>
        </div>

        {/* Banner de estado */}
        <div className={`psp-status-banner ${bridgeStatus.online ? 'online' : 'offline'}`}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Wifi size={20} />
            <span style={{ fontWeight: 600 }}>{bridgeStatus.detail}</span>
          </div>
        </div>

        {/* Si no está conectado, mostrar pasos de instalación rápida */}
        {!bridgeStatus.online && (
          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 12, padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ fontWeight: 700, fontSize: '0.92rem', color: '#0f172a' }}>
              ¿Por qué sale la ventana de impresión cada vez que mandas a imprimir?
            </div>
            <p style={{ margin: 0, fontSize: '0.86rem', color: '#475569', lineHeight: 1.5 }}>
              Por seguridad, los navegadores (Chrome / Edge) no pueden mandar a imprimir directamente a una impresora física sin preguntar, <strong>a menos que esté corriendo el Puente Kiwi</strong> en la computadora de caja.
            </p>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <button
                type="button"
                className="psp-btn psp-btn-primary"
                onClick={() =>
                  downloadFile(
                    'Iniciar-Impresora-Kiwi-POS.bat',
                    buildWindowsPrintBridgeBat(config),
                    'application/x-bat;charset=utf-8'
                  )
                }
              >
                <Download size={16} />
                Descargar Puente para Windows (.bat)
              </button>

              <button
                type="button"
                className="psp-btn psp-btn-secondary psp-btn-sm"
                onClick={() =>
                  downloadFile(
                    'kiwi_print_bridge.py',
                    buildPythonPrintBridgeScript(config),
                    'text/x-python;charset=utf-8'
                  )
                }
              >
                <Download size={14} />
                Descargar para Mac / Linux (.py)
              </button>
            </div>

            <ul className="psp-steps-list" style={{ marginTop: 6 }}>
              <li className="psp-step-item">
                <span className="psp-step-num">1</span>
                <span>
                  Haz clic en el botón verde arriba para descargar <strong>Iniciar-Impresora-Kiwi-POS.bat</strong> en esta PC.
                </span>
              </li>
              <li className="psp-step-item">
                <span className="psp-step-num">2</span>
                <span>
                  Haz <strong>doble clic</strong> sobre el archivo descargado. Se iniciará y se configurará para arrancar solo cada vez que prendas la PC.
                </span>
              </li>
              <li className="psp-step-item">
                <span className="psp-step-num">3</span>
                <span>
                  Pulsa <strong>"Detectar Impresoras PC"</strong> y listo: tus comandas de ensaladas, baguettes y ticket de cliente saldrán solas y en silencio.
                </span>
              </li>
            </ul>
          </div>
        )}

        {/* Impresoras detectadas */}
        {osPrinters.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: '0.84rem', fontWeight: 600, color: '#334155' }}>
              Impresoras instaladas en Windows (Panel de Control de esta PC):
            </span>
            <div className="psp-pills-container">
              {osPrinters.map((p) => (
                <span key={p} className="psp-pill active">
                  <Check size={13} />
                  {p}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* TARJETA 2: IMPRESORA DE CAJA (Ticket del Cliente) */}
      <section className="psp-caja-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.08rem', fontWeight: 800, color: '#0f172a' }}>
              2. Nota del Cliente (Ticket de Venta en Caja)
            </h3>
            <p style={{ margin: '2px 0 0', fontSize: '0.86rem', color: '#475569' }}>
              Aquí se imprime la cuenta completa para el cliente con subtotal, IVA y totales.
            </p>
          </div>

          <button
            type="button"
            className="psp-btn psp-btn-secondary psp-btn-sm"
            disabled={testing}
            onClick={() => void handleTestPrint('ticket')}
          >
            <Printer size={14} />
            Probar Ticket de Caja
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14 }}>
          <div className="psp-field">
            <label className="psp-label">Nombre exacto de la Impresora en Windows (PC)</label>
            <input
              type="text"
              list="kiwi-os-printers-list"
              className="psp-input"
              value={config.ticketPrinterName}
              onChange={(e) => setConfig({ ...config, ticketPrinterName: e.target.value })}
              placeholder="caja"
              autoComplete="off"
            />
            <span className="psp-hint">Nombre en Windows (Panel de Control &gt; Dispositivos e Impresoras).</span>
            {osPrinters.length > 0 && (
              <div className="psp-pills-container">
                {osPrinters.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={`psp-pill ${config.ticketPrinterName.toLowerCase() === p.toLowerCase() ? 'active' : ''}`}
                    onClick={() => setConfig({ ...config, ticketPrinterName: p })}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="psp-field">
            <label className="psp-label">IP de Red Ethernet (Opcional)</label>
            <input
              type="text"
              className="psp-input"
              value={config.ticketPrinterHost}
              onChange={(e) => setConfig({ ...config, ticketPrinterHost: e.target.value })}
              placeholder="ej. 192.168.1.200"
              autoComplete="off"
            />
            <span className="psp-hint">Déjalo vacío si está conectada por cable USB a esta computadora.</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
          <label className="psp-switch">
            <input
              type="checkbox"
              checked={config.kickDrawerOnCash}
              onChange={(e) => setConfig({ ...config, kickDrawerOnCash: e.target.checked })}
            />
            <span className="psp-switch-slider" />
          </label>
          <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#334155' }}>
            Abrir cajón de dinero automáticamente al cobrar en efectivo
          </span>
        </div>
      </section>

      {/* TARJETA 3: ESTACIONES Y ÁREAS DE COMANDA */}
      <section className="psp-card">
        <div>
          <h3 className="psp-card-title">
            <Printer size={20} color="#047857" />
            3. Áreas de Impresión de Comandas (Cocina y Barra)
          </h3>
          <p className="psp-card-desc">
            Cada estación recibe únicamente sus productos asignados (por ejemplo: ensaladas van a la impresora <code>ensaladas</code>, baguettes van a la impresora <code>barra</code>).
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {config.printAreas
            .filter((area) => area.code !== 'none')
            .map((area) => {
              const target = config.areaPrinters[area.code] || {
                enabled: area.printComanda,
                printerName: area.code,
                host: '',
                port: 9100,
              };
              return (
                <div
                  key={area.code}
                  className={`psp-area-item ${!target.enabled || !area.printComanda ? 'disabled' : ''}`}
                >
                  <div className="psp-area-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <label className="psp-switch">
                        <input
                          type="checkbox"
                          checked={target.enabled && area.printComanda}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            setConfig({
                              ...config,
                              printAreas: config.printAreas.map((a) =>
                                a.code === area.code ? { ...a, printComanda: checked } : a
                              ),
                              areaPrinters: {
                                ...config.areaPrinters,
                                [area.code]: { ...target, enabled: checked },
                              },
                            });
                          }}
                        />
                        <span className="psp-switch-slider" />
                      </label>

                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontWeight: 800, fontSize: '0.98rem', color: '#0f172a' }}>
                            {area.name}
                          </span>
                          <span className={`psp-badge ${getStationBadgeClass(area.code)}`}>
                            {area.code.toUpperCase()}
                          </span>
                        </div>
                        <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                          {target.enabled && area.printComanda
                            ? `Imprime comanda separada en la impresora "${target.printerName || area.code}"`
                            : 'Comanda desactivada para esta área'}
                        </span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      {target.enabled && area.printComanda && (
                        <button
                          type="button"
                          className="psp-btn psp-btn-secondary psp-btn-sm"
                          disabled={testing}
                          onClick={() => void handleTestPrint(area.code)}
                        >
                          <Printer size={13} />
                          Probar
                        </button>
                      )}

                      {!area.isSystem && (
                        <button
                          type="button"
                          className="psp-btn psp-btn-danger psp-btn-sm"
                          onClick={() => handleRemoveCustomArea(area.code)}
                          title="Eliminar área"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  </div>

                  {target.enabled && area.printComanda && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, paddingTop: 4 }}>
                      <div className="psp-field">
                        <label className="psp-label">Impresora en Windows (PC)</label>
                        <input
                          type="text"
                          list="kiwi-os-printers-list"
                          className="psp-input"
                          value={target.printerName}
                          onChange={(e) =>
                            setConfig({
                              ...config,
                              areaPrinters: {
                                ...config.areaPrinters,
                                [area.code]: { ...target, printerName: e.target.value },
                              },
                            })
                          }
                          placeholder={area.code === 'salads' ? 'ensaladas' : 'barra'}
                        />
                        {osPrinters.length > 0 && (
                          <div className="psp-pills-container">
                            {osPrinters.map((p) => (
                              <button
                                key={p}
                                type="button"
                                className={`psp-pill ${target.printerName.toLowerCase() === p.toLowerCase() ? 'active' : ''}`}
                                onClick={() =>
                                  setConfig({
                                    ...config,
                                    areaPrinters: {
                                      ...config.areaPrinters,
                                      [area.code]: { ...target, printerName: p },
                                    },
                                  })
                                }
                              >
                                {p}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="psp-field">
                        <label className="psp-label">IP de Red Ethernet (Opcional)</label>
                        <input
                          type="text"
                          className="psp-input"
                          value={target.host}
                          onChange={(e) =>
                            setConfig({
                              ...config,
                              areaPrinters: {
                                ...config.areaPrinters,
                                [area.code]: { ...target, host: e.target.value },
                              },
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

        {/* Agregar nueva área */}
        <div style={{ borderTop: '2px dashed #e2e8f0', paddingTop: 14, marginTop: 4 }}>
          <h4 style={{ margin: '0 0 10px', fontSize: '0.92rem', fontWeight: 700, color: '#0f172a' }}>
            + Agregar Nueva Área de Comanda (ej. Postres, Plancha, Bebidas 2)
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr)) auto', gap: 10, alignItems: 'flex-end' }}>
            <div className="psp-field">
              <label className="psp-label">Código único</label>
              <input
                type="text"
                className="psp-input"
                value={newAreaCode}
                onChange={(e) => setNewAreaCode(e.target.value)}
                placeholder="ej. postres"
              />
            </div>
            <div className="psp-field">
              <label className="psp-label">Nombre en Comanda</label>
              <input
                type="text"
                className="psp-input"
                value={newAreaName}
                onChange={(e) => setNewAreaName(e.target.value)}
                placeholder="ej. REPOSTERIA"
              />
            </div>
            <div className="psp-field">
              <label className="psp-label">Impresora PC</label>
              <input
                type="text"
                list="kiwi-os-printers-list"
                className="psp-input"
                value={newAreaPrinter}
                onChange={(e) => setNewAreaPrinter(e.target.value)}
                placeholder="ej. barra"
              />
            </div>
            <button
              type="button"
              className="psp-btn psp-btn-primary"
              onClick={handleAddCustomArea}
            >
              <Plus size={16} />
              Agregar
            </button>
          </div>
        </div>
      </section>

      {/* TARJETA 4: REGLAS Y PREFERENCIAS */}
      <section className="psp-card">
        <h3 className="psp-card-title">
          4. Reglas de Impresión en Punto de Venta
        </h3>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <label className="psp-switch">
            <input
              type="checkbox"
              checked={config.autoPrintOnConfirm}
              onChange={(e) => setConfig({ ...config, autoPrintOnConfirm: e.target.checked })}
            />
            <span className="psp-switch-slider" />
          </label>
          <span style={{ fontSize: '0.92rem', fontWeight: 700, color: '#0f172a' }}>
            Imprimir automáticamente al confirmar o cobrar un pedido en caja
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14, marginTop: 4 }}>
          <div className="psp-field">
            <label className="psp-label">Documentos a imprimir en automático</label>
            <select
              className="psp-select"
              value={config.autoPrintCopies}
              onChange={(e) =>
                setConfig({ ...config, autoPrintCopies: e.target.value as AutoPrintCopies })
              }
            >
              <option value="both">Ticket en Caja + Comandas separadas por Área (Recomendado)</option>
              <option value="ticket">Sólo Ticket de Venta en Caja</option>
              <option value="kitchen">Sólo Comandas de Cocina por Área</option>
            </select>
          </div>

          <div className="psp-field">
            <label className="psp-label">Ancho de rollo térmico</label>
            <select
              className="psp-select"
              value={config.paperWidthMm}
              onChange={(e) =>
                setConfig({ ...config, paperWidthMm: Number(e.target.value) === 58 ? 58 : 80 })
              }
            >
              <option value={80}>80 mm (Estándar 42 columnas sin desfase)</option>
              <option value={58}>58 mm (Compacto 32 columnas)</option>
            </select>
          </div>
        </div>
      </section>

      {/* Botones finales */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', paddingBottom: 24 }}>
        <button
          type="button"
          className="psp-btn psp-btn-primary"
          style={{ height: 46, padding: '0 24px', fontSize: '0.95rem', fontWeight: 700 }}
          onClick={() => void handleSave()}
        >
          <CheckCircle2 size={18} />
          Guardar Configuración de Impresoras
        </button>

        <button
          type="button"
          className="psp-btn psp-btn-secondary"
          style={{ height: 46, padding: '0 20px', fontSize: '0.92rem' }}
          onClick={() => void handleTestPrint()}
          disabled={testing}
        >
          <Printer size={16} />
          {testing ? 'Enviando prueba…' : 'Probar Pedido Completo (Ticket Caja + Comandas)'}
        </button>
      </div>
    </div>
  );
}
