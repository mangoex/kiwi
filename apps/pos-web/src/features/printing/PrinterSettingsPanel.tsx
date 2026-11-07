import React, { useEffect, useState } from 'react';
import { Button } from '@restaurantos/ui';
import { CheckCircle2, Download, Printer, RefreshCw, Wifi } from 'lucide-react';
import {
  buildPythonPrintBridgeScript,
  buildWindowsPrintBridgeBat,
  checkPrintBridgeHealth,
  dispatchPosPrintJob,
  loadPrinterConfig,
  savePrinterConfig,
  type AutoPrintCopies,
  type PosPrinterConfig,
  type PrinterConnectionMode,
} from './printerService';
import type { TicketPrintData, KitchenPrintData } from './receiptFormatter';

export function PrinterSettingsPanel({ branchName }: { branchName?: string }) {
  const [config, setConfig] = useState<PosPrinterConfig>(() => loadPrinterConfig());
  const [savedNotice, setSavedNotice] = useState('');
  const [testNotice, setTestNotice] = useState('');
  const [testing, setTesting] = useState(false);
  const [bridgeStatus, setBridgeStatus] = useState<{
    checking: boolean;
    online: boolean;
    detail: string;
  }>({ checking: false, online: false, detail: 'Sin verificar' });

  const verifyBridge = async (urlToUse?: string) => {
    const targetUrl = urlToUse ?? config.bridgeUrl;
    setBridgeStatus({ checking: true, online: false, detail: 'Verificando puente local…' });
    const res = await checkPrintBridgeHealth(targetUrl);
    if (res.online) {
      setBridgeStatus({
        checking: false,
        online: true,
        detail: `Conectado (${res.service || '127.0.0.1:9123'}) — Impresión directa IP:9100 sin diálogo activa`,
      });
    } else {
      setBridgeStatus({
        checking: false,
        online: false,
        detail:
          'Puente local no detectado en este equipo. Si aún no lo inicias, puedes descargarlo abajo o usar impresión térmica 80mm.',
      });
    }
  };

  useEffect(() => {
    void verifyBridge(config.bridgeUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = () => {
    const saved = savePrinterConfig(config);
    setConfig(saved);
    setSavedNotice('Configuración de impresora guardada en esta terminal.');
    void verifyBridge(saved.bridgeUrl);
    setTimeout(() => setSavedNotice(''), 4000);
  };

  const handleTestPrint = async () => {
    if (testing) return;
    setTesting(true);
    setTestNotice('');
    try {
      const saved = savePrinterConfig(config);
      setConfig(saved);
      const nowStr = new Date().toLocaleString('es-MX');
      const sampleTicket: TicketPrintData = {
        folio: 'PRUEBA-001',
        orderNumber: 1,
        createdAt: nowStr,
        customerName: 'PRUEBA DE IMPRESORA KIWI',
        serviceTypeLabel: branchName ? `SUCURSAL ${branchName.toUpperCase()}` : 'MOSTRADOR',
        lines: [
          {
            quantity: 1,
            productName: 'ENSALADA DE ARANDANO',
            totalCents: 13000,
            modifiers: ['POLLO EXTRA'],
            lineNotes: 'Prueba de impresion automatica',
          },
          {
            quantity: 1,
            productName: 'AGUA MINERAL',
            totalCents: 3000,
          },
        ],
        subtotalCents: 13793,
        taxCents: 2207,
        totalCents: 16000,
        cashTender: {
          receivedCents: 20000,
          changeCents: 4000,
        },
      };
      const sampleKitchen: KitchenPrintData = {
        folio: 'PRUEBA-001',
        orderNumber: 1,
        createdAt: nowStr,
        serviceTypeLabel: branchName ? `SUCURSAL ${branchName.toUpperCase()}` : 'MOSTRADOR',
        customerName: 'PRUEBA DE IMPRESORA KIWI',
        lines: sampleTicket.lines,
        orderNotes: 'COMANDA DE PRUEBA - VERIFICACION TERMICA 80MM',
      };

      const result = await dispatchPosPrintJob({
        ticketData: sampleTicket,
        kitchenData: sampleKitchen,
        copies: saved.autoPrintCopies,
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 740 }}>
      <div>
        <h2>Configuración de Impresoras Térmicas (Red IP:9100 y Auto-Impresión)</h2>
        <p style={{ color: '#475569', marginTop: 4 }}>
          Configura la impresión automática de <strong>Ticket de Venta</strong> y{' '}
          <strong>Comanda de Cocina</strong> al confirmar o cobrar pedidos en esta terminal
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
              <option value="both">Ticket de Venta + Comanda de Cocina (Recomendado)</option>
              <option value="ticket">Sólo Ticket de Venta / Cliente</option>
              <option value="kitchen">Sólo Comanda de Cocina</option>
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
              <option value={80}>80 mm (Estándar 42 columnas)</option>
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

      {/* 2. Conexión por Red Local IP:9100 */}
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
          2. Impresora por Red Local (Ethernet / Wi-Fi — Puerto 9100)
        </h3>

        <label className="settings-field">
          <span>Modo de envío a impresora</span>
          <select
            value={config.connectionMode}
            onChange={(e) =>
              setConfig({ ...config, connectionMode: e.target.value as PrinterConnectionMode })
            }
          >
            <option value="network_bridge">
              Directo por Red IP:9100 (ESC/POS sin ventana de diálogo, con respaldo 80mm)
            </option>
            <option value="browser_silent">
              Impresión Térmica Aislada 80mm del Navegador (compatible con Chrome --kiosk-printing)
            </option>
          </select>
        </label>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
          <label className="settings-field">
            <span>IP de Impresora Principal (Caja / Ticket)</span>
            <input
              type="text"
              value={config.ticketPrinterHost}
              onChange={(e) => setConfig({ ...config, ticketPrinterHost: e.target.value })}
              placeholder="Ej. 192.168.1.200"
              autoComplete="off"
            />
          </label>
          <label className="settings-field">
            <span>Puerto TCP (Caja)</span>
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

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
          <label className="settings-field">
            <span>IP de Impresora Cocina (Opcional — vacío usa la misma de Caja)</span>
            <input
              type="text"
              value={config.kitchenPrinterHost}
              onChange={(e) => setConfig({ ...config, kitchenPrinterHost: e.target.value })}
              placeholder="Dejar vacío para usar la impresora principal"
              autoComplete="off"
            />
          </label>
          <label className="settings-field">
            <span>Puerto TCP (Cocina)</span>
            <input
              type="number"
              value={config.kitchenPrinterPort}
              onChange={(e) =>
                setConfig({ ...config, kitchenPrinterPort: Number(e.target.value) || 9100 })
              }
              placeholder="9100"
            />
          </label>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <label className="settings-field" style={{ flex: 1, minWidth: 240 }}>
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
            {bridgeStatus.checking ? 'Verificando…' : 'Verificar puente'}
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
      </section>

      {/* 3. Descarga de Puente Local TCP 9100 */}
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
        <h3 style={{ margin: 0, fontSize: '0.96rem', color: '#1e3a8a' }}>
          ¿Cómo imprimir directo por IP:9100 en automático sin abrir diálogo del navegador?
        </h3>
        <p style={{ margin: 0, fontSize: '0.86rem', color: '#1e40af', lineHeight: 1.45 }}>
          Por seguridad de los navegadores web, una página en internet (HTTPS) no puede abrir un
          socket TCP crudo al puerto <strong>9100</strong> de tu red local sin un puente en la PC de
          caja. Descarga y ejecuta con doble clic el <strong>Puente Ligero Kiwi</strong> en la
          computadora del POS (ya incluye la IP que escribiste arriba y no requiere instalar nada):
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
        <Button type="button" variant="primary" onClick={handleSave}>
          <CheckCircle2 size={16} />
          Guardar configuración de impresoras
        </Button>

        <Button
          type="button"
          variant="secondary"
          onClick={() => void handleTestPrint()}
          disabled={testing}
        >
          <Printer size={16} />
          {testing ? 'Enviando prueba…' : 'Probar Impresión Ahora (Ticket + Comanda)'}
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
