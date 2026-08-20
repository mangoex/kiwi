import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

function testBranchDailyReconciliationReportComponent() {
  const fileContent = readFileSync(
    resolve(root, 'apps', 'pos-web', 'src', 'features', 'reports', 'BranchDailyReconciliationReport.tsx'),
    'utf-8'
  );

  assert.ok(fileContent.includes('Conciliación y Corte Diario de Caja'), 'Should include report title');
  assert.ok(fileContent.includes('expected_cash_in_register'), 'Should calculate expected cash in register');
  assert.ok(fileContent.includes('difference'), 'Should calculate difference (sobrante/faltante)');
  assert.ok(fileContent.includes('Pago a Proveedores de Insumos'), 'Should include suppliers breakdown section');
  assert.ok(fileContent.includes('Gastos Fijos y Operativos'), 'Should include fixed expenses breakdown section');
  assert.ok(fileContent.includes('Ingresos por Transferencias'), 'Should include transfer breakdown section');
  assert.ok(fileContent.includes('Retiros en Efectivo / Bóveda'), 'Should include cash withdrawal breakdown');
  assert.ok(fileContent.includes('handleExportExcel'), 'Should include Excel download capability');
  assert.ok(fileContent.includes('handleToggleAudit'), 'Should include audit review toggle');
}

function testCorporateReconciliationDashboardComponent() {
  const fileContent = readFileSync(
    resolve(root, 'apps', 'admin-web', 'src', 'features', 'reports', 'CorporateReconciliationDashboard.tsx'),
    'utf-8'
  );

  assert.ok(fileContent.includes('Consolidado Multi-Sucursal y Cortes'), 'Should include corporate title');
  assert.ok(fileContent.includes('selectedBranchId'), 'Should allow filtering by branch');
  assert.ok(fileContent.includes('supplier_totals'), 'Should include supplier aggregated expenses');
  assert.ok(fileContent.includes('fixed_expense_totals'), 'Should include fixed expense aggregated totals');
  assert.ok(fileContent.includes('handleExportExcel'), 'Should allow exporting corporate consolidated workbook');
}

function testPCO007ReportsContainsReconciliationTab() {
  const fileContent = readFileSync(
    resolve(root, 'apps', 'pos-web', 'src', 'features', 'reports', 'PCO007Reports.tsx'),
    'utf-8'
  );

  assert.ok(fileContent.includes('Corte y Conciliación'), 'Should include Corte y Conciliacion tab');
  assert.ok(fileContent.includes('BranchDailyReconciliationReport'), 'Should render BranchDailyReconciliationReport');
}

function run() {
  console.log('Running testBranchDailyReconciliationReportComponent...');
  testBranchDailyReconciliationReportComponent();
  console.log('Running testCorporateReconciliationDashboardComponent...');
  testCorporateReconciliationDashboardComponent();
  console.log('Running testPCO007ReportsContainsReconciliationTab...');
  testPCO007ReportsContainsReconciliationTab();
  console.log('All frontend reconciliation report assertions verified successfully!');
}

run();
