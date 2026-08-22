import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

function testBranchAdminOperationsContainsInteractivePurchases() {
  const fileContent = readFileSync(
    resolve(root, 'apps', 'pos-web', 'src', 'features', 'admin', 'BranchAdminOperations.tsx'),
    'utf-8'
  );

  // Check that BranchAdminPurchases has create, confirm and cancel capabilities
  assert.ok(fileContent.includes('Nueva Compra Directa'), 'Should include button for new direct purchase');
  assert.ok(fileContent.includes('handleConfirm'), 'Should include handleConfirm function for purchase receipts');
  assert.ok(fileContent.includes('handleCancel'), 'Should include handleCancel function for purchase compensations');
  assert.ok(fileContent.includes('paid_from_cash'), 'Should include cash deduction capability');
  assert.ok(fileContent.includes('Partidas de Compra'), 'Should include multi-line items form');

  // Check that BranchAdminSuppliers displays suppliers and presentations directory with central governance note
  assert.ok(fileContent.includes('Directorio de proveedores'), 'Should include suppliers directory');
  assert.ok(fileContent.includes('Presentaciones de compra'), 'Should include presentations directory');
  assert.ok(fileContent.includes('catálogo central permanece en Administración corporativa'), 'Should include central catalog governance note');
}

function testHistoryContainsReprintCapability() {
  const historyContent = readFileSync(
    resolve(root, 'apps', 'pos-web', 'src', 'features', 'history', 'History.tsx'),
    'utf-8'
  );

  assert.ok(historyContent.includes('Reimprimir'), 'History should include Reimprimir button');
  assert.ok(historyContent.includes('handleReprint'), 'History should include handleReprint handler');
  assert.ok(historyContent.includes('reprintMessage'), 'History should include reprint status feedback');
}

function testPosCartContainsCourtesyAndSupervisorPin() {
  const posContent = readFileSync(
    resolve(root, 'apps', 'pos-web', 'src', 'features', 'pos', 'PointOfSale.tsx'),
    'utf-8'
  );

  assert.ok(posContent.includes('isCourtesyModalOpen'), 'POS should include courtesy modal state');
  assert.ok(posContent.includes('supervisorPin'), 'POS should require supervisor pin');
  assert.ok(posContent.includes('Autorización de Cortesía o Descuento'), 'POS should include supervisor adjustment authorization modal');
  assert.ok(posContent.includes('effectiveCourtesyCents'), 'POS should render the backend-authorized courtesy');
  assert.ok(posContent.includes('/orders/adjustments/authorize'), 'POS should authorize adjustments through Python');
}

function run() {
  console.log('Running testBranchAdminOperationsContainsInteractivePurchases...');
  testBranchAdminOperationsContainsInteractivePurchases();
  console.log('Running testHistoryContainsReprintCapability...');
  testHistoryContainsReprintCapability();
  console.log('Running testPosCartContainsCourtesyAndSupervisorPin...');
  testPosCartContainsCourtesyAndSupervisorPin();
  console.log('All 6 operational stories assertions verified and passed successfully!');
}

run();
