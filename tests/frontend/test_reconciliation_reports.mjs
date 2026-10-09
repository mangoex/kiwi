import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

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

// Execute the component's real guard against the existing command's permission alternatives.
const posSource = readFileSync(resolve(root, 'apps/pos-web/src/features/reports/BranchDailyReconciliationReport.tsx'), 'utf8');
const guard = posSource.match(/const canAudit = ([^;]+);/)[1];
const canAudit = new Function('hasPermission', `return ${guard};`);
for (const permission of ['audit.read', 'branch.admin.access', 'admin.manage']) {
  assert.equal(canAudit(candidate => candidate === permission), true, permission);
}
assert.equal(canAudit(candidate => candidate === 'cash.shift.close'), false);
assert.equal(canAudit(() => false), false);

const compile = source => ts.transpileModule(source, {
  compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext},
}).outputText;
const contract = await import('data:text/javascript;base64,' + Buffer.from(compile(
  readFileSync(resolve(root, 'packages/api-client/src/reconciliationV2.ts'), 'utf8')
)).toString('base64'));
const fixtures = JSON.parse(readFileSync(resolve(root, 'packages/test-fixtures/reconciliation-v2.json'), 'utf8'));
const missingPopulation = structuredClone(fixtures.pending_daily);
delete missingPopulation.population.timezone;
assert.throws(() => contract.parseDailyReconciliation(missingPopulation), /incompatible/);
const badDescription = structuredClone(fixtures.pending_daily);
badDescription.fixed_expenses_breakdown = [{no: 1, expense_type: 'Sintético', amount: 'not-money', observations: ''}];
assert.throws(() => contract.parseDailyReconciliation(badDescription), /incompatible/);
for (const [name, fixture] of Object.entries(fixtures)) {
  const parse = name.endsWith('_daily') ? contract.parseDailyReconciliation : contract.parseConsolidatedReconciliation;
  const parsed = parse(fixture);
  const balance = name.endsWith('_daily') ? parsed.balance : parsed.summary;
  if (name.startsWith('pending')) {
    assert.equal(balance.physical_cash_count, null);
    assert.equal(balance.difference, null);
    assert.equal(contract.physicalCountLabel(parsed.physical_count), 'Pendiente de arqueo');
  } else {
    assert.equal(balance.physical_cash_count, '0.00');
    assert.equal(balance.difference, '-2000.00');
    assert.equal(contract.physicalCountLabel(parsed.physical_count), 'Conteo completo');
  }
  const wrong = structuredClone(fixture);
  const wrongBalance = name.endsWith('_daily') ? wrong.balance : wrong.summary;
  wrongBalance.physical_cash_count = name.startsWith('pending') ? 0 : null;
  assert.throws(() => parse(wrong), /incompatible/);
  const incomplete = structuredClone(fixture);
  incomplete.physical_count.pending_shift_ids = [];
  incomplete.physical_count.counted_shift_ids = [];
  assert.throws(() => parse(incomplete), /incompatible/);
  const mixed = structuredClone(fixture); mixed.activity.kind = 'shifts_opened';
  assert.throws(() => parse(mixed), /incompatible/);
}

const clientSource = readFileSync(resolve(root, 'packages/api-client/src/index.ts'), 'utf8')
  .replace(/^import .*;\r?\n/gm, '')
  .replace(/^export \* from .*;\r?\n/gm, '')
  .replace('subscribeToOperationalUnauthorized(clearCashierLocalCapture);', 'const clearCashierLocalCapture = () => {};');
const client = await import('data:text/javascript;base64,' + Buffer.from(compile(clientSource)).toString('base64'));
globalThis.localStorage = {getItem: () => 'synthetic-report-token'};
globalThis.sessionStorage = {getItem: () => null};
const calls = [];
globalThis.fetch = async (url, options) => {
  calls.push({url, options});
  return new Response(url.includes('export?') ? new Blob(['synthetic-workbook']) : JSON.stringify(fixtures.pending_daily), {status: 200});
};
const daily = await client.fetchApi('/reports/branch-reconciliation/daily?branch_id=synthetic&date=2026-08-12', {}, 'v2');
assert.equal(daily.balance.physical_cash_count, null);
assert.ok(calls[0].url.startsWith('/api/v2/'));
assert.equal(calls[0].options.headers.Authorization, 'Bearer synthetic-report-token');
let clicked = false;
globalThis.document = {createElement: () => ({click() {clicked = true;}, remove() {}}), body: {append() {}}};
await client.downloadReconciliationWorkbook('synthetic', 8, 2026);
assert.equal(clicked, true);
assert.ok(calls[1].url.startsWith('/api/v2/reports/branch-reconciliation/export?'));
assert.equal(calls[1].options.headers.Authorization, 'Bearer synthetic-report-token');
assert.ok(!calls[1].url.includes('token'));
globalThis.fetch = async () => new Response(JSON.stringify({detail: {code: 'reconciliation_integrity_conflict', message: 'Población inconsistente'}}), {status: 409});
await assert.rejects(() => client.downloadReconciliationWorkbook('synthetic', 8, 2026), error => error.status === 409 && error.code === 'reconciliation_integrity_conflict');
console.log('Reconciliation v2 runtime contracts, null/zero and authenticated downloads verified.');

assert.equal(contract.sumReportMoney(['0.10','0.20']), '0.30');
assert.equal(contract.sumReportMoney(['9007199254740993.99','0.01']), '9007199254740994.00');
assert.equal(contract.formatReportMoney('-0.01'), '-$0.01');
assert.equal(contract.formatReportMoney('9007199254740993.99'), '$9,007,199,254,740,993.99');
assert.throws(() => contract.reportMoneyCents('1.005'), /incompatible/);
