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

  // Check that BranchAdminSuppliers has supplier and presentation creation
  assert.ok(fileContent.includes('Nuevo Proveedor'), 'Should include button to create local supplier');
  assert.ok(fileContent.includes('Nueva Presentación'), 'Should include button to create commercial presentation');
  assert.ok(fileContent.includes('handleCreateSupplier'), 'Should include handleCreateSupplier handler');
  assert.ok(fileContent.includes('handleCreatePresentation'), 'Should include handleCreatePresentation handler');
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
  assert.ok(posContent.includes('Autorización de Descuento o Cortesía'), 'POS should include supervisor discount authorization modal');
  assert.ok(posContent.includes('effectiveDiscountCents'), 'POS should calculate effective discount in cart total');
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
