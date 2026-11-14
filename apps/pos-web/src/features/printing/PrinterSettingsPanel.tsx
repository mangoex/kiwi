import React, { useEffect, useState } from 'react';
import { Button } from '@restaurantos/ui';
import { CheckCircle2, Download, Plus, Printer, RefreshCw, Trash2, Wifi } from 'lucide-react';
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
    setBridgeStatus({ checking: true, online: false, detail: 'Verificando puente local e impresoras de la PC…' });
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
        detail: `Conectado (${res.service || '127.0.0.1:9123'}) · ${
          printerCount > 0
            ? `${printerCount} impresoras detectadas en la PC (${printersRes.printers.join(', ')})`
            : 'Listo para enviar a impresoras de Windows (caja, ensaladas, barra) o IP:9100'
        }`,
      });
    } else {
      setBridgeStatus({
        checking: false,
        online: false,
        detail:
          'Puente local no detectado en este equipo. Descárgalo abajo para imprimir directo en las impresoras del Panel de Control (caja, ensaladas, barra) o usa impresión térmica 80mm.',
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
      // Continúa con persistencia local si el backend está offline
    }
    setSavedNotice('Configuración de áreas e impresoras guardada en esta terminal y sincronizada.');
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 860 }}>
      <datalist id="kiwi-os-printers-list">
        {suggestedPrinters.map((pName) => (
          <option key={pName} value={pName} />
        ))}
      </datalist>

      <div>
        <h2>Configuración de Impresoras y Áreas de Impresión (Caja, Ensaladas, Barra, Bebidas)</h2>
        <p style={{ color: '#475569', marginTop: 4 }}>
          Asigna la impresora del Panel de Control de la computadora (ej. <code>caja</code>,{' '}
          <code>ensaladas</code>, <code>barra</code>) o IP:9100 a la <strong>Nota del Cliente</strong>{' '}
          y a cada <strong>Área de Impresión de Comandas</strong>
          {branchName ? ` (${branchName})` : ''}.
        </p>
      </div>

      {/* 1. Reglas de Impresión Automática */}
      <section
        style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: 10,
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <h3 style={{ margin: 0, fontSize: '1rem' }}>1. Impresión Automática en Punto de Venta</h3>

        <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontWeight: 600 }}>
          <input
            type="checkbox"
            checked={config.autoPrintOnConfirm}
            onChange={(e) => setConfig({ ...config, autoPrintOnConfirm: e.target.checked })}
          />
          <span>Imprimir automáticamente al confirmar o cobrar pedido en el POS</span>
        </label>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
          <label className="settings-field">
            <span>Documentos a imprimir en automático</span>
            <select
              value={config.autoPrintCopies}
              onChange={(e) =>
                setConfig({ ...config, autoPrintCopies: e.target.value as AutoPrintCopies })
              }
            >
              <option value="both">Ticket en Caja + Comandas separadas por Área (Recomendado)</option>
              <option value="ticket">Sólo Ticket de Venta en Caja</option>
              <option value="kitchen">Sólo Comandas de Cocina por Área</option>
            </select>
          </label>

          <label className="settings-field">
            <span>Ancho de rollo térmico</span>
            <select
              value={config.paperWidthMm}
              onChange={(e) =>
                setConfig({ ...config, paperWidthMm: Number(e.target.value) === 58 ? 58 : 80 })
              }
            >
              <option value={80}>80 mm (Estándar 42 columnas sin salto a la línea 34)</option>
              <option value={58}>58 mm (Compacto 32 columnas)</option>
            </select>
          </label>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={config.kickDrawerOnCash}
            onChange={(e) => setConfig({ ...config, kickDrawerOnCash: e.target.checked })}
          />
          <span>Enviar pulso de apertura al cajón de dinero al cobrar en efectivo (ESC/POS)</span>
        </label>
      </section>

      {/* 2. Impresora de Caja (Ticket del Cliente) */}
      <section
        style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: 10,
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <h3 style={{ margin: 0, fontSize: '1rem' }}>
          2. Impresora de Caja (Nota de Venta del Cliente)
        </h3>

        <label className="settings-field">
          <span>Modo de envío a impresoras</span>
          <select
            value={config.connectionMode}
            onChange={(e) =>
              setConfig({ ...config, connectionMode: e.target.value as PrinterConnectionMode })
            }
          >
            <option value="network_bridge">
              Puente Local Kiwi (Envía a impresoras de Windows: caja, ensaladas, barra o Red IP:9100)
            </option>
            <option value="browser_silent">
              Impresión Térmica Aislada 80mm del Navegador (compatible con Chrome --kiosk-printing)
            </option>
          </select>
        </label>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 2fr 1fr', gap: 12 }}>
          <label className="settings-field">
            <span>Nombre de Impresora en Windows / PC (Caja)</span>
            <input
              type="text"
              list="kiwi-os-printers-list"
              value={config.ticketPrinterName}
              onChange={(e) => setConfig({ ...config, ticketPrinterName: e.target.value })}
              placeholder="Ej. caja"
              autoComplete="off"
            />
          </label>
          <label className="settings-field">
            <span>IP de Impresora Caja (Opcional si usa Red TCP)</span>
            <input
              type="text"
              value={config.ticketPrinterHost}
              onChange={(e) => setConfig({ ...config, ticketPrinterHost: e.target.value })}
              placeholder="Ej. 192.168.1.200"
              autoComplete="off"
            />
          </label>
          <label className="settings-field">
            <span>Puerto TCP</span>
            <input
              type="number"
              value={config.ticketPrinterPort}
              onChange={(e) =>
                setConfig({ ...config, ticketPrinterPort: Number(e.target.value) || 9100 })
              }
              placeholder="9100"
            />
          </label>
        </div>
      </section>

      {/* 3. Áreas de Impresión de Comandas y Asignación de Impresora por Área */}
      <section
        style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: 10,
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem' }}>
            3. Áreas de Impresión de Comandas y Asignación de Impresora por Área
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: '0.84rem', color: '#475569' }}>
            Cada producto o grupo se envía únicamente a la impresora asignada a su área (por ejemplo:{' '}
            <strong>ENSALADAS</strong> a la impresora <code>ensaladas</code>, y{' '}
            <strong>BAGUETTES(RAPIDO)</strong> / <strong>BARRA</strong> a la impresora{' '}
            <code>barra</code>).
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
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
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1.6fr 1.5fr 1.3fr auto',
                    gap: 10,
                    alignItems: 'center',
                    background: '#ffffff',
                    border: '1px solid #cbd5e1',
                    borderRadius: 8,
                    padding: '10px 12px',
                  }}
                >
                  <div>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: '0.88rem' }}>
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
                      <span>{area.name}</span>
                    </label>
                    <div style={{ fontSize: '0.75rem', color: '#64748b', marginLeft: 24 }}>
                      Código: <code>{area.code}</code> · KDS: <code>{area.station}</code>
                    </div>
                  </div>

                  <label className="settings-field" style={{ margin: 0 }}>
                    <span style={{ fontSize: '0.75rem' }}>Impresora en Panel de Control (PC)</span>
                    <input
                      type="text"
                      list="kiwi-os-printers-list"
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
                      placeholder={`Ej. ${area.code === 'salads' ? 'ensaladas' : 'barra'}`}
                    />
                  </label>

                  <label className="settings-field" style={{ margin: 0 }}>
                    <span style={{ fontSize: '0.75rem' }}>IP de Red (Opcional)</span>
                    <input
                      type="text"
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
                      placeholder="Ej. 192.168.1.201"
                    />
                  </label>

                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={testing}
                      onClick={() => void handleTestPrint(area.code)}
                      title={`Imprimir comanda de prueba en ${area.name}`}
                    >
                      <Printer size={14} />
                      Probar
                    </Button>
                    {!area.isSystem && (
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => handleRemoveCustomArea(area.code)}
                        title="Eliminar área personalizada"
                      >
                        <Trash2 size={14} />
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
        </div>

        {/* Agregar nueva Área de Impresión */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1.4fr 1.2fr auto',
            gap: 8,
            alignItems: 'flex-end',
            paddingTop: 8,
            borderTop: '1px dashed #cbd5e1',
          }}
        >
          <label className="settings-field" style={{ margin: 0 }}>
            <span style={{ fontSize: '0.76rem' }}>Nuevo código de área</span>
            <input
              type="text"
              value={newAreaCode}
              onChange={(e) => setNewAreaCode(e.target.value)}
              placeholder="Ej. postres"
            />
          </label>
          <label className="settings-field" style={{ margin: 0 }}>
            <span style={{ fontSize: '0.76rem' }}>Nombre en Comanda</span>
            <input
              type="text"
              value={newAreaName}
              onChange={(e) => setNewAreaName(e.target.value)}
              placeholder="Ej. REPOSTERIA / POSTRES"
            />
          </label>
          <label className="settings-field" style={{ margin: 0 }}>
            <span style={{ fontSize: '0.76rem' }}>Impresora asignada</span>
            <input
              type="text"
              list="kiwi-os-printers-list"
              value={newAreaPrinter}
              onChange={(e) => setNewAreaPrinter(e.target.value)}
              placeholder="Ej. barra"
            />
          </label>
          <Button type="button" variant="secondary" onClick={handleAddCustomArea}>
            <Plus size={15} />
            Agregar área
          </Button>
        </div>
      </section>

      {/* 4. Puente Local y Detección de Impresoras del Sistema */}
      <section
        style={{
          background: '#eff6ff',
          border: '1px solid #bfdbfe',
          borderRadius: 10,
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
      >
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <label className="settings-field" style={{ flex: 1, minWidth: 240, margin: 0 }}>
            <span>Puente Local de Impresión en esta PC</span>
            <input
              type="text"
              value={config.bridgeUrl}
              onChange={(e) => setConfig({ ...config, bridgeUrl: e.target.value })}
              placeholder="http://127.0.0.1:9123"
              autoComplete="off"
            />
          </label>
          <Button
            type="button"
            variant="secondary"
            onClick={() => void verifyBridge(config.bridgeUrl)}
            disabled={bridgeStatus.checking}
          >
            <RefreshCw size={16} />
            {bridgeStatus.checking ? 'Detectando…' : 'Detectar impresoras de la PC'}
          </Button>
        </div>

        <p
          role="status"
          style={{
            margin: 0,
            fontSize: '0.86rem',
            fontWeight: 600,
            color: bridgeStatus.online ? '#059669' : '#b45309',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <Wifi size={16} />
          {bridgeStatus.detail}
        </p>

        <h3 style={{ margin: '4px 0 0', fontSize: '0.95rem', color: '#1e3a8a' }}>
          Descargar Puente Local Kiwi (Conecta el navegador con las impresoras de Windows / Mac / Linux)
        </h3>
        <p style={{ margin: 0, fontSize: '0.84rem', color: '#1e40af', lineHeight: 1.45 }}>
          Ejecuta este puente ligero en la computadora de caja para que el sistema detecte las
          impresoras del Panel de Control (<code>caja</code>, <code>ensaladas</code>,{' '}
          <code>barra</code>) y envíe cada comanda automáticamente a su impresora sin abrir ventanas
          de diálogo:
        </p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
          <Button
            type="button"
            variant="secondary"
            onClick={() =>
              downloadFile(
                'Iniciar-Impresora-Kiwi-POS.bat',
                buildWindowsPrintBridgeBat(config),
                'application/x-bat;charset=utf-8'
              )
            }
          >
            <Download size={16} />
            Descargar Puente Automático para Windows (.bat)
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() =>
              downloadFile(
                'kiwi_print_bridge.py',
                buildPythonPrintBridgeScript(config),
                'text/x-python;charset=utf-8'
              )
            }
          >
            <Download size={16} />
            Descargar Puente para Mac / Linux (.py)
          </Button>
        </div>
      </section>

      {/* Botones principales de Guardado y Prueba */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button type="button" variant="primary" onClick={() => void handleSave()}>
          <CheckCircle2 size={16} />
          Guardar configuración de áreas e impresoras
        </Button>

        <Button
          type="button"
          variant="secondary"
          onClick={() => void handleTestPrint()}
          disabled={testing}
        >
          <Printer size={16} />
          {testing ? 'Enviando prueba…' : 'Probar Pedido Completo (Ticket Caja + Comandas por Área)'}
        </Button>
      </div>

      {savedNotice && (
        <p role="status" style={{ margin: 0, color: '#059669', fontWeight: 600 }}>
          ✓ {savedNotice}
        </p>
      )}
      {testNotice && (
        <p role="status" style={{ margin: 0, color: '#0f172a', fontWeight: 600 }}>
          {testNotice}
        </p>
      )}
    </div>
  );
}
