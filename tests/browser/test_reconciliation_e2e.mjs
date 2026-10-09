// TC-344: built Admin/POS + real API on an exclusively synthetic local fixture.
import assert from 'node:assert/strict';
import {readFileSync, mkdirSync} from 'node:fs';
const manifest = JSON.parse(readFileSync(process.env.RECONCILIATION_E2E_MANIFEST, 'utf8'));
assert.equal(manifest.synthetic_only, true);
assert.ok(manifest.database_url.endsWith('reconciliation.sqlite'));
const origin = process.env.RECONCILIATION_BASE_URL || 'http://127.0.0.1:8127';
assert.equal(new URL(origin).hostname, '127.0.0.1');
const {chromium} = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const browser = await chromium.launch({headless: true, ...(process.env.ADMINRETRO_CHROME_PATH ? {executablePath: process.env.ADMINRETRO_CHROME_PATH} : {})});
const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
const errors = [];
page.on('pageerror', error => errors.push(error.message));
mkdirSync('output/playwright', {recursive: true});
const dates = manifest.reconciliation_dates;
try {
  await page.goto(origin+'/admin/login');
  await page.getByLabel('Correo electrónico').fill(manifest.login.email);
  await page.getByLabel('Contraseña').fill(manifest.login.password);
  await page.getByRole('button', {name: 'Iniciar Sesión'}).click();
  await page.waitForURL(/\/admin\/?$/);
  // Reset only the explicitly synthetic review so repeated runs have the same starting state.
  const resetStatus = await page.evaluate(async ({branch, date}) => {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    const response = await fetch('/api/v1/reports/branch-reconciliation/audit', {
      method: 'POST', headers: {'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({branch_id: branch, date, reviewed: false, notes: ''}),
    });
    return response.status;
  }, {branch: manifest.branch_id, date: dates.pending});
  assert.equal(resetStatus, 200);
  await page.evaluate(branch => {localStorage.setItem('admin_branch_id', branch); localStorage.setItem('pos_branch_id', branch); localStorage.setItem('pos_register_id', 'CAJA-01');}, manifest.branch_id);
  await page.goto(origin+'/admin/reports');
  const exportButton = page.getByRole('button', {name: /Excel mensual de sucursal/});
  assert.equal(await exportButton.isDisabled(), true, 'All branches cannot silently export the first branch');
  await page.getByRole('combobox').nth(1).selectOption(manifest.branch_id);
  await page.getByLabel('Hasta:').fill(dates.pending);
  await page.getByLabel('Desde:').fill(dates.pending);
  const count = page.getByRole('region', {name: 'Arqueo consolidado'});
  await count.getByText('Pendiente de arqueo', {exact: true}).waitFor();
  assert.match(await count.innerText(), /Sin conteo completo equivalente.*Sin diferencia calculable/s);
  await page.getByRole('region', {name: 'Actividad calendario'}).waitFor();
  let exportAuth;
  const trackExport = request => {if (request.url().includes('/api/v2/reports/branch-reconciliation/export?')) exportAuth = request.headers().authorization;};
  page.on('request', trackExport);
  const downloadPromise = page.waitForEvent('download');
  await exportButton.click();
  const download = await downloadPromise;
  await download.saveAs('output/playwright/reconciliation-month.xlsx');
  assert.match(exportAuth, /^Bearer /);
  page.off('request', trackExport);
  await page.getByLabel('Hasta:').fill(dates.zero);
  await page.getByLabel('Desde:').fill(dates.zero);
  await count.getByText('Conteo completo', {exact: true}).waitFor();
  assert.match(await count.innerText(), /Contado: \$0\.00/);
  assert.match(await count.innerText(), /Diferencia: -\$1,700\.00/);
  await page.getByLabel('Hasta:').fill(dates.mixed);
  await page.getByLabel('Desde:').fill(dates.mixed);
  await count.getByText('Pendiente de arqueo', {exact: true}).waitFor();
  await page.setViewportSize({width: 390, height: 844});
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1), 'Admin report must fit 390px');
  await page.screenshot({path: 'output/playwright/reconciliation-admin-390.png', fullPage: true});

  await page.setViewportSize({width: 1440, height: 1000});
  await page.goto(origin+'/pos/historical-reports');
  await page.getByRole('heading', {name: 'Conciliación y Corte Diario de Caja'}).waitFor();
  const date = page.getByLabel('Fecha de conciliación');
  const physical = page.getByTestId('physical-count');
  await date.fill(dates.pending);
  await physical.getByText('Pendiente de arqueo', {exact: true}).waitFor();
  assert.equal(await physical.getByText('CAJA CUADRADA AL CENTAVO', {exact: true}).count(), 0);
  await date.fill(dates.zero);
  await physical.getByText('FALTANTE (-)', {exact: true}).waitFor();
  assert.match(await physical.innerText(), /Arqueo físico: \$0\.00/);
  assert.match(await physical.innerText(), /-\$1,700\.00/);
  await date.fill(dates.activity);
  await physical.getByText('Sin turnos', {exact: true}).waitFor();
  const activity = page.getByRole('region', {name: 'Actividad calendario'});
  await activity.getByRole('heading', {name: 'Actividad calendario del '+dates.activity}).waitFor();
  // Audit A finishes after B's report has started: A must not invalidate B.
  await date.fill(dates.pending);
  await physical.getByText('Pendiente de arqueo', {exact: true}).waitFor();
  let releaseAudit, auditStarted;
  const auditArrival = new Promise(resolve => {auditStarted = resolve;});
  const auditGate = new Promise(resolve => {releaseAudit = resolve;});
  const auditHandler = async route => {auditStarted(); await auditGate; await route.continue();};
  await page.route('**/api/v1/reports/branch-reconciliation/audit', auditHandler);
  let releaseDaily, dailyStarted;
  const dailyArrival = new Promise(resolve => {dailyStarted = resolve;});
  const dailyGate = new Promise(resolve => {releaseDaily = resolve;});
  const delayedDaily = async route => {
    if (new URL(route.request().url()).searchParams.get('date') !== dates.zero) return route.continue();
    dailyStarted(); await dailyGate; await route.continue();
  };
  await page.route('**/api/v2/reports/branch-reconciliation/daily?**', delayedDaily);
  await page.getByRole('button', {name: /Marcar como Revisado|Desmarcar revisión/}).click();
  await auditArrival;
  await date.fill(dates.zero);
  await dailyArrival;
  const auditFinished = page.waitForResponse(response => response.url().includes('/api/v1/reports/branch-reconciliation/audit') && response.request().method() === 'POST');
  releaseAudit(); await auditFinished;
  releaseDaily();
  await physical.getByText('FALTANTE (-)', {exact: true}).waitFor();
  assert.equal(await date.inputValue(), dates.zero);
  await page.unroute('**/api/v1/reports/branch-reconciliation/audit', auditHandler);
  await page.unroute('**/api/v2/reports/branch-reconciliation/daily?**', delayedDaily);
  // Reviewed operational closure remains pending; review never manufactures physical cash.
  await date.fill(dates.pending);
  await page.getByText('✓ REVISIÓN GERENCIAL REGISTRADA', {exact: true}).waitFor();
  await physical.getByText('Pendiente de arqueo', {exact: true}).waitFor();
  await page.setViewportSize({width: 390, height: 844});
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1), 'POS report must fit 390px');
  await page.screenshot({path: 'output/playwright/reconciliation-pos-390.png', fullPage: true});
  assert.deepEqual(errors, []);
  console.log('Admin/POS actual API: pending, zero physical, mixed registers, independent activity, authenticated XLSX and audit/date race passed at desktop/390px.');
} catch (error) {
  await page.screenshot({path: 'output/playwright/reconciliation-error.png', fullPage: true});
  console.error((await page.locator('body').innerText()).slice(-3000), errors);
  throw error;
} finally {await browser.close();}
