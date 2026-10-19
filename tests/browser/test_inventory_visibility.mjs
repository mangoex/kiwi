import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { delimiter } from 'node:path';

const { chromium } = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const base = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
const port = process.env.INV_VIEW_FIXTURE_PORT || '39993';
const api = `http://127.0.0.1:${port}`;
const server = spawn(process.env.INV_VIEW_PYTHON || 'python', ['tests/browser/inventory_fixture_server.py'], {
  env: { ...process.env, PYTHONPATH: ['apps/api', 'apps/api/tests'].join(delimiter) }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
});
let serverOutput = '';
server.stdout.on('data', chunk => { serverOutput += chunk; });
server.stderr.on('data', chunk => { serverOutput += chunk; });
const output = 'output/playwright/inventory-visibility';
mkdirSync(output, { recursive: true });
let browser;
let activePage;
try {
  let fixture;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { fixture = await fetch(`${api}/__inventory_fixture`).then(response => response.json()); break; }
    catch { await new Promise(resolve => setTimeout(resolve, 300)); }
  }
  assert.ok(fixture, `Real API fixture did not start: ${serverOutput}`);
  browser = await chromium.launch({ headless: true, ...(process.env.ADMINRETRO_CHROME_PATH ? { executablePath: process.env.ADMINRETRO_CHROME_PATH } : {}) });
  for (const width of [1440, 1024, 390]) {
    console.log(`Inventory real API flow: ${width}px`);
    const context = await browser.newContext({ viewport: { width, height: 950 } });
    const page = await context.newPage();
    activePage = page;
    page.setDefaultTimeout(15000);
    const writes = [], errors = [];
    let overviewError = false, mutationConflict = false, revoked = false;
    let holdBranch = null, releaseHeld, heldDone;
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(token => { localStorage.setItem('auth_token', token); localStorage.setItem('pos_register_id', 'INV-QA-01'); }, fixture.token);
    await page.route('**/api/v1/**', async route => {
      const request = route.request();
      const url = new URL(request.url());
      if (request.method() !== 'GET') writes.push({ path: url.pathname, url: request.url(), body: request.postDataJSON() });
      if (revoked && url.pathname.endsWith('/auth/session')) {
        const response = await route.fetch({ url: api + url.pathname + url.search });
        const profile = await response.json();
        profile.admin_capabilities['inventory.read'] = false;
        profile.inventory_query_capabilities = { organization_read: false, branches: [] };
        profile.scope.authorization_version = (profile.scope.authorization_version || 1) + 1;
        return route.fulfill({ json: profile });
      }
      if (overviewError && url.pathname.endsWith('/inventory/overview')) return route.fulfill({ status: 503, json: { detail: { code: 'inventory_overview_unavailable', message: 'Consulta temporalmente no disponible.' } } });
      if (mutationConflict && request.method() === 'PUT' && url.pathname.includes('/stock-thresholds/')) return route.fulfill({ status: 409, json: { detail: { code: 'stock_threshold_version_conflict', message: 'Conflicto de versión.' } } });
      if (holdBranch && url.pathname.endsWith('/inventory/overview') && url.searchParams.get('branch_id') === holdBranch) {
        const response = await route.fetch({ url: api + url.pathname + url.search });
        await new Promise(resolve => { releaseHeld = resolve; });
        await route.fulfill({ response }).catch(() => {});
        heldDone(); return;
      }
      const response = await route.fetch({ url: api + new URL(request.url()).pathname + new URL(request.url()).search });
      await route.fulfill({ response });
    });
    const authHeaders = { Authorization: `Bearer ${fixture.token}` };
    const before = await fetch(`${api}/api/v1/auth/session`, { headers: authHeaders }).then(response => response.json());
    assert.notEqual(before.active_branch.id, fixture.north_id, 'The query destination must differ from the active POS branch');
    await page.goto(`${base}/inventory/stock`);
    await page.getByRole('heading', { name: 'Existencias', exact: true }).waitFor();
    const selector = page.getByLabel('Consulta de inventario', { exact: true });
    await selector.selectOption(fixture.north_id);
    const itemRow = page.locator('tbody tr').filter({ has: page.locator(`a[href*="item_id=${fixture.item_id}"]`) });
    try { await itemRow.waitFor(); }
    catch (error) {
      await page.screenshot({ path: `${output}/failure-${width}.png`, fullPage: true });
      console.error(await page.locator('body').innerText()); throw error;
    }
    assert.match(await itemRow.innerText(), /10\.00/);
    assert.match(await itemRow.innerText(), /3\.00/);
    assert.match(await itemRow.innerText(), /7\.00/);
    await page.screenshot({ path: `${output}/stock-${width}.png`, fullPage: true, animations: 'disabled' });
    assert.equal(await page.locator('.admin-active-branch-label').count(), 0);
    await itemRow.getByRole('link', { name: 'Ver umbrales' }).click();
    await page.getByRole('button', { name: /^Editar umbrales de/ }).click();
    const dialog = page.getByRole('dialog');
    assert.match(await dialog.innerText(), /Norte/);
    assert.equal(await page.getByLabel('Mínimo', { exact: true }).evaluate(element => element === document.activeElement), true);
    await dialog.getByRole('button', { name: 'Cerrar', exact: true }).focus();
    await page.keyboard.press('Shift+Tab');
    assert.equal(await page.getByRole('button', { name: 'Guardar umbrales', exact: true }).evaluate(element => element === document.activeElement), true);
    assert.equal(await page.getByLabel('Mínimo', { exact: true }).inputValue(), '12.35');
    await page.getByLabel('Máximo', { exact: true }).fill('25.345');
    assert.equal(await page.getByRole('button', { name: 'Guardar umbrales', exact: true }).isDisabled(), true);
    await page.getByLabel('Máximo', { exact: true }).fill('25.50');
    await page.screenshot({ path: `${output}/threshold-modal-${width}.png`, fullPage: true, animations: 'disabled' });
    await page.getByRole('button', { name: 'Guardar umbrales', exact: true }).click();
    await dialog.waitFor({ state: 'hidden' });
    assert.equal(await page.getByRole('button', { name: /^Editar umbrales de/ }).evaluate(element => element === document.activeElement), true);
    const mutation = writes.findLast(row => row.path.includes('/stock-thresholds/'));
    assert.equal(String(mutation.body.minimum_quantity), '12.345678');
    assert.equal(mutation.body.maximum_quantity, '25.50');
    assert.equal(writes.some(row => /branch-selections|branch-context-reissues/.test(row.path)), false);
    const after = await fetch(`${api}/api/v1/auth/session`, { headers: authHeaders }).then(response => response.json());
    assert.deepEqual(after.active_branch, before.active_branch);
    assert.equal(await page.evaluate(() => localStorage.getItem('pos_register_id')), 'INV-QA-01');
    if (width === 1440) {
      await page.getByRole('link', { name: 'Volver a Existencias' }).click();
      const center = before.active_branch.id;
      holdBranch = center;
      const finished = new Promise(resolve => { heldDone = resolve; });
      await Promise.all([
        page.waitForRequest(request => request.url().includes('/inventory/overview') && new URL(request.url()).searchParams.get('branch_id') === center),
        page.getByLabel('Consulta de inventario', { exact: true }).selectOption(center),
      ]);
      await page.getByLabel('Consulta de inventario', { exact: true }).selectOption(fixture.north_id);
      await page.getByRole('cell', { name: '10.00 g', exact: true }).waitFor();
      while (!releaseHeld) await new Promise(resolve => setTimeout(resolve, 10));
      holdBranch = null; releaseHeld(); await finished;
      assert.equal(await page.getByLabel('Consulta de inventario', { exact: true }).inputValue(), fixture.north_id);
      assert.equal(await page.getByRole('cell', { name: before.active_branch.name, exact: true }).count(), 0);
      await page.locator(`a[href*="item_id=${fixture.item_id}"]`).click();
      await page.getByRole('button', { name: /^Editar umbrales de/ }).click();
      await page.getByLabel('Consulta de inventario', { exact: true }).selectOption(center);
      await page.getByLabel('Máximo', { exact: true }).fill('27.00');
      await page.getByRole('button', { name: 'Guardar umbrales', exact: true }).click();
      await page.getByRole('dialog').waitFor({ state: 'hidden' });
      assert.equal(new URL(writes.findLast(row => row.path.includes('/stock-thresholds/')).url).searchParams.get('branch_id'), fixture.north_id);
      await page.getByLabel('Consulta de inventario', { exact: true }).selectOption(fixture.north_id);
      await page.getByRole('button', { name: /^Editar umbrales de/ }).click();
      mutationConflict = true;
      await page.getByRole('button', { name: 'Guardar umbrales', exact: true }).click();
      await page.getByText('Los umbrales cambiaron.', { exact: false }).waitFor();
      assert.equal(await page.getByRole('button', { name: 'Guardar umbrales', exact: true }).isDisabled(), true);
      await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
      mutationConflict = false;
      await page.getByRole('link', { name: 'Volver a Existencias' }).click();
      await page.getByLabel('Buscar insumo o SKU').fill('no-such-inventory-item');
      await page.getByText('No hay artículos que coincidan con esta consulta.').waitFor();
      await page.getByLabel('Buscar insumo o SKU').fill('');
      await page.getByRole('table').waitFor();
      overviewError = true;
      await page.getByRole('button', { name: 'Actualizar', exact: true }).click();
      await page.getByText('Consulta temporalmente no disponible.').waitFor();
      assert.equal(await page.getByRole('table').count(), 0);
      overviewError = false;
      await page.getByRole('button', { name: 'Actualizar', exact: true }).click();
      await page.getByRole('table').waitFor();
      await context.setOffline(true);
      await page.getByText('Sin conexión.', { exact: false }).waitFor();
      assert.equal(await page.getByRole('table').count(), 0);
      await context.setOffline(false);
      await page.getByRole('table').waitFor();
      await page.getByLabel('Consulta de inventario', { exact: true }).selectOption('');
      await page.getByRole('table').waitFor();
      await page.evaluate(token => { localStorage.setItem('auth_token', token); window.dispatchEvent(new StorageEvent('storage', { key: 'auth_token' })); }, fixture.local_token);
      await page.getByLabel('Consulta de inventario', { exact: true }).waitFor();
      assert.equal(await page.getByLabel('Consulta de inventario', { exact: true }).inputValue(), fixture.north_id);
      assert.equal(await page.getByRole('option', { name: 'Todas las sucursales' }).count(), 0);
      revoked = true;
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));
      await page.getByRole('heading', { name: 'Acceso no autorizado' }).waitFor();
      assert.equal(await page.getByRole('table').count(), 0);
      console.log('Delayed response, frozen destination, conflict, empty/error/offline and account/revocation isolation passed');
    }
    assert.deepEqual(errors, []);
    await context.close();
  }
  console.log('Real API inventory/threshold flow passed at 1440, 1024 and 390px');
} catch (error) {
  if (activePage && !activePage.isClosed()) await activePage.screenshot({ path: `${output}/failure.png`, fullPage: true });
  throw error;
} finally {
  if (browser) await browser.close();
  await fetch(`${api}/__inventory_shutdown`, { method: 'POST' }).catch(() => {});
  server.kill();
  server.stdout.destroy(); server.stderr.destroy();
}
