import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-thermal-receipt-'));
const require = createRequire(import.meta.url);

try {
  // Transpilar archivos TypeScript de impresión a CommonJS para Node
  execFileSync(
    process.execPath,
    [
      join(root, 'node_modules/typescript/bin/tsc'),
      '--target', 'ES2022',
      '--module', 'CommonJS',
      '--moduleResolution', 'node',
      '--esModuleInterop',
      '--outDir', temporaryDirectory,
      join(root, 'apps/pos-web/src/features/printing/numberToWordsMxn.ts'),
      join(root, 'apps/pos-web/src/features/printing/receiptFormatter.ts'),
      join(root, 'apps/pos-web/src/features/printing/buildReceiptData.ts'),
      join(root, 'apps/pos-web/src/features/printing/printerService.ts'),
    ],
    { cwd: root, stdio: 'pipe' }
  );

  const numModule = require(join(temporaryDirectory, 'numberToWordsMxn.js'));
  const { numberToWordsMxn, enteroALetras } = numModule;

  const fmtModule = require(join(temporaryDirectory, 'receiptFormatter.js'));
  const {
    formatTicketText,
    formatKitchenText,
    generateEscPosTicket,
    generateEscPosKitchen,
    ESCPOS,
  } = fmtModule;

  const buildModule = require(join(temporaryDirectory, 'buildReceiptData.js'));
  const { buildTicketPrintData, buildKitchenPrintData } = buildModule;

  const printerServiceModule = require(join(temporaryDirectory, 'printerService.js'));
  const {
    DEFAULT_PRINTER_CONFIG,
    loadPrinterConfig,
    savePrinterConfig,
    buildThermalPrintHtml,
    buildWindowsPrintBridgeBat,
    buildPythonPrintBridgeScript,
    uint8ToBase64,
  } = printerServiceModule;

  console.log('1. Probando conversión de número a letras en MXN...');
  assert.equal(enteroALetras(0), 'CERO');
  assert.equal(enteroALetras(1), 'UN');
  assert.equal(enteroALetras(21), 'VEINTIUN');
  assert.equal(enteroALetras(100), 'CIEN');
  assert.equal(enteroALetras(360), 'TRESCIENTOS SESENTA');
  assert.equal(enteroALetras(1000), 'UN MIL');
  assert.equal(enteroALetras(2500), 'DOS MIL QUINIENTOS');

  assert.equal(numberToWordsMxn(0), 'SON: CERO PESOS 00/100 M.N.');
  assert.equal(numberToWordsMxn(100), 'SON: UN PESO 00/100 M.N.');
  assert.equal(numberToWordsMxn(36000), 'SON: TRESCIENTOS SESENTA PESOS 00/100 M.N.');
  assert.equal(numberToWordsMxn(31034), 'SON: TRESCIENTOS DIEZ PESOS 34/100 M.N.');
  assert.equal(numberToWordsMxn(152450), 'SON: UN MIL QUINIENTOS VEINTICUATRO PESOS 50/100 M.N.');

  console.log('2. Probando formateo de Ticket térmico con el diseño idéntico al de Kiwi Soft Restaurant...');
  const ticketData = {
    folio: '102778',
    orderNumber: 68,
    createdAt: '06/11/2026 02:06:04 PM',
    customerName: 'VERONICA COTA',
    customerPhone: '6673030384',
    colonia: 'KIWI PASAN POR EL',
    zone: 'PASA POR EL',
    serviceTypeLabel: 'PASA POR EL',
    lines: [
      { quantity: 1, productName: 'AGUA MINERAL', totalCents: 3000 },
      { quantity: 1, productName: 'CHILE JALAPEÑO EXTR', totalCents: 2800 },
      { quantity: 1, productName: 'ENSALADA DE ARANDAN', totalCents: 13000 },
      { quantity: 1, productName: 'ENSALADA DE ARANDAN', totalCents: 13000 },
      { quantity: 1, productName: 'POLLO EXTRA', totalCents: 4200 },
    ],
    subtotalCents: 31034,
    taxCents: 4966,
    totalCents: 36000,
    cashTender: {
      receivedCents: 36000,
      changeCents: 0,
    },
  };

  const formattedTicket = formatTicketText(ticketData, 42);
  assert.ok(formattedTicket.includes('KIWI COMIDA NATURAL'), 'Debe incluir el nombre comercial Kiwi');
  assert.ok(formattedTicket.includes('ELISA AMAYRANI INZUNZA DOMINGUEZ'), 'Debe incluir la razón social');
  assert.ok(formattedTicket.includes('RFC:IUDE931111KM2'), 'Debe incluir el RFC oficial');
  assert.ok(formattedTicket.includes('FOLIO:102778'), 'Debe incluir el folio');
  assert.ok(formattedTicket.includes('ORDEN:68'), 'Debe incluir el número de orden diaria');
  assert.ok(formattedTicket.includes('CLIENTE:VERONICA COTA'), 'Debe incluir nombre del cliente');
  assert.ok(formattedTicket.includes('TEL.:6673030384'), 'Debe incluir teléfono del cliente');
  assert.ok(formattedTicket.includes('AGUA MINERAL') && formattedTicket.includes('$30.00'), 'Debe listar productos con precio');
  assert.ok(formattedTicket.includes('ENSALADA DE ARANDAN') && formattedTicket.includes('$130.00'));
  assert.ok(formattedTicket.includes('POLLO EXTRA') && formattedTicket.includes('$42.00'));
  assert.ok(formattedTicket.includes('SUBTOTAL:') && formattedTicket.includes('$310.34'), 'Debe incluir subtotal exacto');
  assert.ok(formattedTicket.includes('IVA:') && formattedTicket.includes('$49.66'), 'Debe incluir desglose de IVA');
  assert.ok(formattedTicket.includes('TOTAL:') && formattedTicket.includes('$360.00'), 'Debe incluir total exacto');
  assert.ok(formattedTicket.includes('SON: TRESCIENTOS SESENTA PESOS 00/100 M.N.'), 'Debe incluir importe en letras oficial');
  assert.ok(formattedTicket.includes('CANTIDAD A RECIBIR:') && formattedTicket.includes('$360.00'), 'Debe incluir importe recibido');
  assert.ok(formattedTicket.includes('CAMBIO REPARTIDOR:') && formattedTicket.includes('$0.00'), 'Debe incluir cambio');
  assert.ok(formattedTicket.includes('GRACIAS POR SU PREFERENCIA'), 'Debe incluir agradecimiento');
  assert.ok(formattedTicket.includes('ESTE NO ES UN COMPROBANTE FISCAL'), 'Debe incluir leyenda fiscal');

  console.log('3. Probando formateo de Comanda de Cocina...');
  const kitchenData = {
    folio: '102778',
    orderNumber: 68,
    createdAt: '06/11/2026 02:06:04 PM',
    serviceTypeLabel: 'PASA POR EL',
    customerName: 'VERONICA COTA',
    lines: [
      {
        quantity: 1,
        productName: 'ENSALADA DE ARANDAN',
        modifiers: ['POLLO EXTRA'],
        lineNotes: 'Aderezo aparte',
        totalCents: 17200,
      },
      { quantity: 1, productName: 'AGUA MINERAL', totalCents: 3000 },
    ],
  };

  const formattedKitchen = formatKitchenText(kitchenData, 42);
  assert.ok(formattedKitchen.includes('*** COMANDA DE COCINA ***'));
  assert.ok(formattedKitchen.includes('ORDEN:#68'));
  assert.ok(formattedKitchen.includes('FOLIO:102778'));
  assert.ok(formattedKitchen.includes('[ 1 ] ENSALADA DE ARANDAN'));
  assert.ok(formattedKitchen.includes('>> POLLO EXTRA'));
  assert.ok(formattedKitchen.includes('* NOTA: ADEREZO APARTE'));
  assert.ok(!formattedKitchen.includes('$'), 'La comanda de cocina no debe incluir signos de precio');

  console.log('4. Probando comandos binarios ESC/POS...');
  const ticketEscPos = generateEscPosTicket(ticketData, true);
  assert.equal(ticketEscPos[0], ESCPOS.INIT[0]);
  assert.equal(ticketEscPos[1], ESCPOS.INIT[1]);
  // Debe contener la secuencia de apertura de cajón
  const escPosStr = Array.from(ticketEscPos).map((b) => b.toString(16).padStart(2, '0')).join('');
  assert.ok(escPosStr.includes('1b700019fa'), 'Debe incluir comando ESC p para abrir cajón de dinero');
  assert.ok(escPosStr.includes('1d5642'), 'Debe incluir comando GS V para corte de papel');

  console.log('5. Probando servicio de configuración de impresoras (IP:9100 y 80mm aislado)...');
  assert.equal(DEFAULT_PRINTER_CONFIG.autoPrintOnConfirm, true, 'Auto-impresión activa por defecto');
  assert.equal(DEFAULT_PRINTER_CONFIG.autoPrintCopies, 'both', 'Ticket + Comanda por defecto');
  assert.equal(DEFAULT_PRINTER_CONFIG.ticketPrinterPort, 9100, 'Puerto 9100 por defecto');

  const fakeStorageMap = new Map();
  const fakeStorage = {
    getItem: (k) => fakeStorageMap.get(k) ?? null,
    setItem: (k, v) => fakeStorageMap.set(k, v),
  };
  savePrinterConfig(
    {
      ...DEFAULT_PRINTER_CONFIG,
      ticketPrinterHost: ' 192.168.1.250 ',
      ticketPrinterPort: 9100,
      autoPrintCopies: 'both',
    },
    fakeStorage
  );
  const loadedCfg = loadPrinterConfig(fakeStorage);
  assert.equal(loadedCfg.ticketPrinterHost, '192.168.1.250');
  assert.equal(loadedCfg.ticketPrinterPort, 9100);

  const printHtml = buildThermalPrintHtml([formattedTicket, formattedKitchen], 80);
  assert.ok(printHtml.includes('size: 80mm auto;'), 'Debe configurar hoja térmica de 80mm');
  assert.ok(printHtml.includes('page-break-after: always;'), 'Debe separar Ticket y Comanda con corte de página');
  assert.ok(printHtml.includes('KIWI COMIDA NATURAL') && printHtml.includes('COMANDA DE COCINA'));

  const winBat = buildWindowsPrintBridgeBat(loadedCfg);
  assert.ok(winBat.includes('192.168.1.250'), 'El script .bat debe incluir la IP configurada');
  assert.ok(winBat.includes('Access-Control-Allow-Private-Network: true'), 'El puente debe soportar Private Network Access de Chrome');

  const pyScript = buildPythonPrintBridgeScript(loadedCfg);
  assert.ok(pyScript.includes('DEFAULT_PRINTER_HOST = "192.168.1.250"'));
  assert.ok(uint8ToBase64(new Uint8Array([0x1b, 0x40])).length > 0);

  console.log('6. Probando integración de auto-impresión en PointOfSale.tsx, CashierPaymentDialog.tsx, History.tsx y Settings.tsx...');
  const historyContent = readFileSync(join(root, 'apps/pos-web/src/features/history/History.tsx'), 'utf8');
  assert.ok(historyContent.includes('ThermalReceiptModal'), 'History.tsx debe importar ThermalReceiptModal');
  assert.ok(historyContent.includes('Imprimir comanda'), 'History.tsx debe ofrecer botón para imprimir comanda');
  assert.ok(historyContent.includes('buildTicketPrintData'), 'History.tsx debe construir datos de impresión');

  const dialogContent = readFileSync(join(root, 'apps/pos-web/src/features/pos/CashierPaymentDialog.tsx'), 'utf8');
  assert.ok(dialogContent.includes('ThermalReceiptModal'), 'CashierPaymentDialog.tsx debe importar ThermalReceiptModal');
  assert.ok(dialogContent.includes('dispatchPosPrintJob'), 'CashierPaymentDialog.tsx debe disparar auto-impresión al cobrar');
  assert.ok(dialogContent.includes('Imprimir Ticket / Comanda'), 'CashierPaymentDialog.tsx debe ofrecer impresión tras el pago');

  const posContent = readFileSync(join(root, 'apps/pos-web/src/features/pos/PointOfSale.tsx'), 'utf8');
  assert.ok(posContent.includes('dispatchPosPrintJob'), 'PointOfSale.tsx debe disparar impresión automática al confirmar pedido');
  assert.ok(posContent.includes('ThermalReceiptModal'), 'PointOfSale.tsx debe incluir modal de impresión térmica');

  const settingsContent = readFileSync(join(root, 'apps/pos-web/src/features/settings/Settings.tsx'), 'utf8');
  assert.ok(settingsContent.includes('PrinterSettingsPanel'), 'Settings.tsx debe renderizar PrinterSettingsPanel en la pestaña Impresoras');

  console.log('Todas las pruebas de impresión térmica y comanda pasaron exitosamente!');
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
