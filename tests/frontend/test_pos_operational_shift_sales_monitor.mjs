import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const output = mkdtempSync(join(tmpdir(), 'restaurantos-pco004-frontend-'));

try {
  const sources = [
    join(root, 'apps/pos-web/src/features/settings/shiftOperations.ts'),
    join(root, 'apps/pos-web/src/features/reports/salesMonitorState.ts'),
  ];
  const tscBin = process.env.RESTAURANTOS_TSC || join(root, 'node_modules/.bin', process.platform === 'win32' ? 'tsc.cmd' : 'tsc');
  execSync(`"${tscBin}" --target ES2022 --module NodeNext --moduleResolution NodeNext --outDir "${output}" ${sources.map(s => `"${s}"`).join(' ')}`, { cwd: root, stdio: 'pipe' });

  const shift = await import(pathToFileURL(join(output, 'settings/shiftOperations.js')).href);
  assert.equal(shift.parseExactCents('0'), 0);
  assert.equal(shift.parseExactCents('20'), 2000);
  assert.equal(shift.parseExactCents('20.5'), 2050);
  assert.equal(shift.parseExactCents('20.50'), 2050);
  for (const value of ['', '-1', '1.001', 'NaN', '90071992547409.92']) {
    assert.equal(shift.parseExactCents(value), null);
  }
  const closeIntent = shift.createCloseIntent('shift-1', 'key-1');
  assert.deepEqual(closeIntent, { shiftId: 'shift-1', key: 'key-1', payload: {} });
  assert.equal(Object.isFrozen(closeIntent), true);
  assert.equal(shift.keepIntentAfterFailure(closeIntent, 'network'), closeIntent);
  assert.equal(shift.keepIntentAfterFailure(closeIntent, 'idempotency_conflict'), null);
  assert.deepEqual(shift.parseCurrentShiftResponse({ cash_shift: null, closure: null }), {
    cash_shift: null, closure: null,
  });
  assert.throws(() => shift.parseCurrentShiftResponse({ cash_shift: null }), /actual de turno/i);
  assert.throws(() => shift.parseOpenShiftResponse({ id: 'shift-1' }), /turno de caja/i);
  const cashShiftResponse = {
    id: 'shift-1', organization_id: 'org-1', branch_id: 'branch-1', register_code: 'register-1',
    status: 'OPEN', opening_cash_cents: 0, opened_at: '2026-08-12T10:00:00Z',
    closed_at: null, created_at: '2026-08-12T10:00:00Z',
  };
  assert.equal(shift.parseOpenShiftResponse(cashShiftResponse).id, 'shift-1');
  assert.throws(() => shift.parseOpenShiftResponse({ ...cashShiftResponse, counted_cash_cents: 0 }), /propiedades no permitidas/i);
  assert.equal(shift.normalizeRegisterId('  CAJA-QA-02  '), 'CAJA-QA-02');
  assert.equal(shift.isPersistedCashConfiguration(
    'branch-1', 'branch-1', ' CAJA-QA-02 ', 'CAJA-QA-02', 'branch-1',
  ), true);
  assert.equal(shift.isPersistedCashConfiguration(
    'branch-1', 'branch-1', 'CAJA-NUEVA', 'CAJA-QA-02', 'branch-1',
  ), false);
  assert.equal(shift.isPersistedCashConfiguration(
    'branch-2', 'branch-1', 'CAJA-QA-02', 'CAJA-QA-02', 'branch-1',
  ), false);

  const monitor = await import(pathToFileURL(join(output, 'reports/salesMonitorState.js')).href);
  const period = monitor.localDayUtcBounds('2026-08-12', 'UTC');
  assert.deepEqual(period, {
    fromUtc: '2026-08-12T00:00:00.000Z',
    toUtc: '2026-08-13T00:00:00.000Z',
  });
  assert.deepEqual(monitor.localDayUtcBounds('2026-08-12', 'America/Mazatlan'), {
    fromUtc: '2026-08-12T07:00:00.000Z', toUtc: '2026-08-13T07:00:00.000Z',
  });
  assert.deepEqual(monitor.localDayUtcBounds('2026-03-08', 'America/New_York'), {
    fromUtc: '2026-03-08T05:00:00.000Z', toUtc: '2026-03-09T04:00:00.000Z',
  });
  const twoTimezoneBranches = [
    { id: 'branch-mzt', timezone: 'America/Mazatlan' },
    { id: 'branch-ny', timezone: 'America/New_York' },
  ];
  assert.equal(monitor.resolveBranchTimeZone('', twoTimezoneBranches), null);
  assert.equal(monitor.resolveBranchTimeZone('branch-mzt', twoTimezoneBranches), 'America/Mazatlan');
  assert.equal(monitor.resolveBranchTimeZone('branch-ny', twoTimezoneBranches), 'America/New_York');
  assert.equal(monitor.resolveBranchTimeZone('branch-unknown', twoTimezoneBranches), null);
  assert.equal(monitor.formatKnownMoney({ known_cents: 12345, unknown_operation_count: 0 }), '$123.45');
  assert.match(monitor.formatKnownMoney({ known_cents: 12345, unknown_operation_count: 2 }), /2 sin dato/);
  assert.throws(() => monitor.parseSalesMonitorResponse({ summary: {} }), /sales monitor/i);
  const indicator = { known_cents: 0, unknown_operation_count: 0 };
  const applied_filters = {
    from_utc: '2026-08-12T00:00:00Z', to_utc: '2026-08-13T00:00:00Z',
    branch_id: 'branch-1', register_id: null, cash_shift_id: null, family_id: null,
    service_type: null,
  };
  const drillItem = {
    payment_id: 'payment-1', order_id: 'order-1', folio: 'F-1', branch_id: 'branch-1',
    cash_shift_id: 'shift-1', register_id: 'register-1', service_type: 'dine-in',
    confirmed_at: '2026-08-12T12:00:00Z', quality_status: 'captured',
    gross: indicator, net: indicator, tax: indicator, discount: indicator, courtesy: indicator,
    order_count: 1, line_count: 1, item_quantity: 2,
  };
  const breakdown = {
    id: 'family-1', label: 'Familia 1', gross: indicator, net: indicator, tax: indicator,
    discount: indicator, courtesy: indicator, order_count: 1, line_count: 1, item_quantity: 2,
  };
  const summaryResponse = {
    applied_filters,
    summary: { gross: indicator, net: indicator, tax: indicator, discount: indicator,
      courtesy: indicator, order_count: 1, line_count: 1, item_quantity: 2,
      legacy_backfilled_line_count: 0 },
    breakdowns: { families: [breakdown], services: [] },
    facets: { cash_shifts: [{ id: 'shift-1', label: 'Caja 1' }],
      families: [{ id: 'family-1', label: 'Familia 1' }], service_types: [] },
    data_quality: { incomplete_operation_count: 0 },
  };
  assert.equal(monitor.parseSalesMonitorResponse(summaryResponse).summary.order_count, 1);
  assert.throws(() => monitor.parseSalesMonitorResponse({ ...summaryResponse, client_name: 'No permitido' }), /propiedades no permitidas/i);
  assert.equal(monitor.parseSalesDrillDownResponse({
    applied_filters, metric: 'gross', items: [drillItem], next_cursor: null,
  }).items[0].order_count, 1);
  const { order_count: omittedOrderCount, ...missingOrderCount } = drillItem;
  assert.equal(omittedOrderCount, 1);
  assert.throws(() => monitor.parseSalesDrillDownResponse({
    applied_filters, metric: 'gross', items: [missingOrderCount], next_cursor: null,
  }), /operación incompleta/i);
  assert.throws(() => monitor.parseSalesDrillDownResponse({
    applied_filters, metric: 'gross', items: [{ ...drillItem, client_name: 'No permitido' }], next_cursor: null,
  }), /propiedades no permitidas/i);

  const pointOfSale = readFileSync(join(root, 'apps/pos-web/src/features/pos/PointOfSale.tsx'), 'utf8');
  const history = readFileSync(join(root, 'apps/pos-web/src/features/history/History.tsx'), 'utf8');
  const settings = readFileSync(join(root, 'apps/pos-web/src/features/settings/Settings.tsx'), 'utf8');
  const salesMonitor = readFileSync(join(root, 'apps/pos-web/src/features/reports/SalesMonitor.tsx'), 'utf8');
  const salesMonitorState = readFileSync(join(root, 'apps/pos-web/src/features/reports/salesMonitorState.ts'), 'utf8');
  const app = readFileSync(join(root, 'apps/pos-web/src/App.tsx'), 'utf8');
  const adminHub = readFileSync(join(root, 'apps/pos-web/src/features/admin/AdminHub.tsx'), 'utf8');
  const adminLayout = readFileSync(join(root, 'apps/admin-web/src/components/AdminLayout.tsx'), 'utf8');

  assert.doesNotMatch(pointOfSale, /CAJA-01/);
  assert.match(pointOfSale, /register_id:\s*registerId/);
  assert.match(pointOfSale, /No hay una caja configurada/);
  assert.doesNotMatch(history, /register_id:\s*localStorage\.getItem\('pos_register_id'\)\s*\|\|\s*''/);
  assert.match(history, /Configura la caja/);
  assert.match(settings, /Cerrar operativamente/);
  assert.match(settings, /El corte final queda pendiente/);
  assert.doesNotMatch(settings, /Cerrar Turno \(Corte de Caja\)/);
  assert.match(settings, /closeIntentRef/);
  assert.match(settings, /submitLockRef/);
  assert.match(settings, /persistedRegisterId/);
  assert.match(settings, /configurationSaved/);
  assert.match(settings, /branchId === activeBranchId/);
  assert.match(settings, /await selectBranch\(branchId\)/);
  assert.match(settings, /register_id=\$\{encodeURIComponent\(persistedRegisterId\)\}/);
  assert.match(settings, /register_id: persistedRegisterId/);
  assert.match(settings, /disabled=\{viewState !== 'closed' \|\| !configurationSaved\}/);
  assert.match(settings, /AbortController/);
  assert.match(salesMonitor, /parseSalesMonitorResponse/);
  assert.match(salesMonitorState, /unknown_operation_count/);
  assert.match(salesMonitor, /AbortController/);
  assert.match(salesMonitor, /resolveBranchTimeZone/);
  assert.match(salesMonitor, /interface BranchOption \{ id: string; name: string; timezone: string/);
  assert.match(salesMonitor, /timeZone: selectedTimeZone/);
  assert.match(salesMonitor, /Selecciona una sucursal con zona horaria válida/);
  assert.doesNotMatch(salesMonitor, /Todas las autorizadas/);
  assert.match(app, /path="sales-monitor"/);
  assert.match(app, /PermissionRoute permission="reports\.sales\.read"/);
  assert.match(adminHub, /Monitor de ventas/);
  assert.match(adminHub, /reports\.sales\.read/);
  assert.match(adminLayout, /\/sales-monitor/);
  assert.doesNotMatch(salesMonitor, /\.reduce\(/);
  assert.doesNotMatch(salesMonitor, /parseFloat/);
} finally {
  rmSync(output, { recursive: true, force: true });
}
