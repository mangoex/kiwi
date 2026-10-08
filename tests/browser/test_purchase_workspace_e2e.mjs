// SR-WORKSPACE-001: real UI + isolated API. Manifest contains synthetic credentials only.
import assert from 'node:assert/strict';
import { readFileSync, mkdirSync } from 'node:fs';
const manifest = JSON.parse(readFileSync(process.env.SR_WORKSPACE_E2E_MANIFEST, 'utf8'));
assert.equal(manifest.synthetic_only, true);
const origin = process.env.SR_WORKSPACE_BASE_URL || 'http://127.0.0.1:8127';
assert.equal(new URL(origin).hostname, '127.0.0.1');
const { chromium } = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const browser = await chromium.launch({ headless: true, ...(process.env.ADMINRETRO_CHROME_PATH ? { executablePath: process.env.ADMINRETRO_CHROME_PATH } : {}) });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.setDefaultTimeout(20000);
const errors = [];
page.on('pageerror', error => errors.push(error.message));
mkdirSync('output/playwright', { recursive: true });
try {
  await page.goto(origin + '/admin/login');
  await page.getByLabel('Correo electrónico').fill(manifest.login.email);
  await page.getByLabel('Contraseña').fill(manifest.login.password);
  await page.getByRole('button', { name: 'Iniciar Sesión' }).click();
  await page.waitForURL(/\/admin\/?$/);
  await page.evaluate(branch => { localStorage.setItem('admin_branch_id', branch); localStorage.setItem('pos_branch_id', branch); localStorage.setItem('pos_register_id', 'CAJA-01'); }, manifest.branch_id);
  const token = await page.evaluate(() => localStorage.getItem('auth_token'));
  const headers = { Authorization: 'Bearer ' + token };
  async function post(path, data, extra = {}) {
    const response = await page.request.post(origin + '/api/v1' + path, { headers: { ...headers, ...extra }, data });
    assert.equal(response.ok(), true, await response.text());
    return response.json();
  }
  const suffix = Date.now();
  const supplier = await post('/suppliers', { branch_id: manifest.branch_id, code: 'SR-E2E-' + suffix, commercial_name: 'Proveedor SR E2E' });
  const supplier2 = await post('/suppliers', { branch_id: manifest.branch_id, code: 'SR-E2E-2-' + suffix, commercial_name: 'Proveedor alterno SR' });
  const presentations = [];
  for (const yieldValue of ['10', '5']) presentations.push(await post('/purchase-presentations', { branch_id: manifest.branch_id, supplier_id: supplier.id, item_id: manifest.item_id, code: 'SR-E2E-' + yieldValue + '-' + suffix, name: 'Paquete SR ' + yieldValue, commercial_unit_id: '018f6f73-2d0a-74f0-8f1c-000000000303', base_unit_id: manifest.unit_id, base_unit_yield: yieldValue, usable_content: yieldValue, last_net_price: '0', tax_rate: '0' }));
  const openedShift = await page.request.post(origin + '/api/v1/cash/shifts/open', { headers: { ...headers, 'Idempotency-Key': 'sr-e2e-shift-' + suffix }, data: { branch_id: manifest.branch_id, register_id: 'CAJA-01', opening_cash_cents: 200000 } });
  assert.ok(openedShift.ok() || (openedShift.status() === 409 && (await openedShift.json()).detail.code === 'cash_shift_already_open'));
  for (const [surface, url, button] of [['admin', '/admin/purchases', 'Nueva compra'], ['pos', '/pos/administration/purchases', 'Nueva compra']]) {
    await page.goto(origin + url);
    if (surface === 'pos') {
      await page.waitForURL(/\/admin\/purchases\?/);
      assert.equal(new URL(page.url()).searchParams.get('branch_id'), manifest.branch_id);
    }
    await page.getByRole('button', { name: button, exact: true }).click();
    const workspace = page.locator('.purchase-workspace');
    await workspace.getByLabel(/^Proveedor/).selectOption(supplier.id);
    await workspace.getByLabel('Folio', { exact: true }).fill('SR-' + surface + '-' + suffix);
    await workspace.getByLabel('Fecha del comprobante').fill('2026-09-30');
    await workspace.getByLabel('Pagada con efectivo de caja').check();
    await workspace.getByRole('button', { name: 'Agregar renglón' }).click();
    await workspace.getByRole('button', { name: 'Agregar renglón' }).click();
    const amounts = [['2', '250', '1', '40'], ['1', '19.99', '0.29', '3.15'], ['0.5', '0.29', '0', '0.02']];
    for (let index = 0; index < 3; index++) {
      const row = workspace.locator('.purchase-line').nth(index);
      await row.locator('select').selectOption(presentations[index === 1 ? 1 : 0].id);
      for (let field = 0; field < 4; field++) await row.locator('input').nth(field).fill(amounts[index][field]);
    }
    await workspace.locator('.purchase-summary').getByText('Total: $562.015000', { exact: true }).waitFor();
    let delayedStarted;
    const oldPreviewStarted = new Promise(resolve => { delayedStarted = resolve; });
    const delayPreview = async route => {
      if (route.request().postDataJSON().lines[0].quantity !== '7') return route.continue();
      const oldResponse = await route.fetch();
      delayedStarted();
      await new Promise(resolve => setTimeout(resolve, 500));
      await route.fulfill({ response: oldResponse }).catch(() => {});
    };
    await page.route('**/api/v1/purchases/preview', delayPreview);
    await workspace.locator('.purchase-line').first().getByLabel('Cantidad', { exact: true }).fill('7');
    await oldPreviewStarted;
    await workspace.locator('.purchase-line').first().getByLabel('Cantidad', { exact: true }).fill('2');
    await workspace.locator('.purchase-summary').getByText('Total: $562.015000', { exact: true }).waitFor();
    await page.waitForTimeout(650);
    assert.match(await workspace.locator('.purchase-summary').innerText(), /562.015000/);
    await page.unroute('**/api/v1/purchases/preview', delayPreview);
    await workspace.getByLabel(/^Proveedor/).selectOption(supplier2.id);
    assert.equal(await workspace.locator('.purchase-line').count(), 3);
    assert.equal(await workspace.getByRole('button', { name: 'Guardar borrador' }).isDisabled(), true);
    await workspace.getByLabel(/^Proveedor/).selectOption(supplier.id);
    await workspace.locator('.purchase-summary').getByText('Total: $562.015000', { exact: true }).waitFor();
    await workspace.getByRole('button', { name: 'Registrar presentación sin perder la nota' }).click();
    await page.getByRole('button', { name: 'Volver a la nota', exact: true }).click();
    assert.equal(await workspace.locator('.purchase-line').count(), 3);
    if (surface === 'admin') {
      const beforeCosts = await (await page.request.get(origin + '/api/v1/inventory/costs?branch_id=' + manifest.branch_id, { headers })).json();
      await workspace.getByRole('button', { name: 'Registrar presentación sin perder la nota' }).click();
      const contextual = page.getByRole('region', { name: 'Alta contextual de presentación' });
      await contextual.getByLabel(/^Insumo base/).selectOption(manifest.item_id);
      await contextual.getByLabel(/^Unidad comercial/).selectOption('018f6f73-2d0a-74f0-8f1c-000000000303');
      await contextual.getByLabel('Nombre', { exact: true }).fill('Contextual SR ' + suffix);
      await contextual.getByLabel('Código (opcional)', { exact: true }).fill('SR-CONTEXT-' + suffix);
      await contextual.getByLabel('Entrada por presentación en unidad base').fill('10');
      await contextual.getByLabel('Contenido útil en unidad base').fill('10');
      await contextual.getByRole('button', { name: 'Registrar presentación', exact: true }).click();
      await contextual.waitFor({ state: 'hidden' });
      assert.equal(await workspace.locator('.purchase-line').count(), 3);
      assert.equal(await workspace.getByLabel('Folio', { exact: true }).inputValue(), 'SR-' + surface + '-' + suffix);
      assert.deepEqual(await (await page.request.get(origin + '/api/v1/inventory/costs?branch_id=' + manifest.branch_id, { headers })).json(), beforeCosts);
    }
    await page.screenshot({ path: 'output/playwright/sr-workspace-' + surface + '.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await workspace.locator('.purchase-line').count(), 3);
    assert.ok(await workspace.evaluate(element => element.scrollWidth <= element.clientWidth + 1), 'Purchase editor must fit the narrow viewport');
    await workspace.locator('.purchase-summary').scrollIntoViewIfNeeded();
    await page.screenshot({ path: 'output/playwright/sr-workspace-' + surface + '-390.png', fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    if (surface === 'admin') {
      await workspace.getByRole('button', { name: 'Cerrar captura' }).click();
      page.once('dialog', dialog => dialog.dismiss());
      await page.getByRole('button', { name: 'Inventario y Almacén', exact: true }).click();
      assert.equal(new URL(page.url()).pathname, '/admin/purchases', 'Declining abandonment must keep scope and draft');
      await page.getByRole('button', { name: button, exact: true }).click();
      assert.equal(await workspace.getByLabel('Folio', { exact: true }).inputValue(), 'SR-' + surface + '-' + suffix);
    }
    let lost = false;
    let expired = false;
    const intents = [];
    const handler = async route => {
      if (route.request().method() !== 'POST') return route.continue();
      intents.push({ key: route.request().headers()['idempotency-key'], body: route.request().postData(), preview: route.request().headers()['if-purchase-preview'] });
      if (!lost) { lost = true; const result = await route.fetch(); assert.equal(result.ok(), true, await result.text()); return route.abort('failed'); }
      if (surface === 'admin' && !expired) { expired = true; return route.fulfill({ status: 401, json: { detail: { code: 'token_invalid', message: 'Session invalidated by test' } } }); }
      return route.continue();
    };
    await page.route('**/api/v1/purchases', handler);
    await workspace.getByRole('button', { name: 'Guardar borrador' }).click();
    await workspace.getByRole('button', { name: 'Recuperar nota registrada' }).waitFor();
    assert.equal(await workspace.getByLabel('Folio', { exact: true }).isDisabled(), true);
    await workspace.getByRole('button', { name: 'Recuperar nota registrada' }).click();
    if (surface === 'admin') {
      await page.waitForURL(/\/admin\/login/);
      await page.getByLabel('Correo electrónico').fill(manifest.login.email);
      await page.getByLabel('Contraseña').fill(manifest.login.password);
      await page.getByRole('button', { name: 'Iniciar Sesión' }).click();
      await page.waitForURL(/\/admin\/?$/);
      headers.Authorization = 'Bearer ' + await page.evaluate(() => localStorage.getItem('auth_token'));
      await page.getByRole('button', { name: 'Compras y Proveedores', exact: true }).click();
      await page.getByText('Compras directas', { exact: true }).click();
      await page.getByRole('button', { name: button, exact: true }).click();
      await workspace.getByRole('button', { name: 'Recuperar nota registrada' }).waitFor();
      assert.equal(await workspace.getByLabel('Folio', { exact: true }).inputValue(), 'SR-' + surface + '-' + suffix);
      await workspace.getByRole('button', { name: 'Recuperar nota registrada' }).click();
    }
    await page.getByText('SR-' + surface + '-' + suffix, { exact: true }).waitFor();
    await page.unroute('**/api/v1/purchases', handler);
    assert.equal(intents.length, surface === 'admin' ? 3 : 2);
    for (const intent of intents) assert.deepEqual(intents[0], intent);
    const purchases = await (await page.request.get(origin + '/api/v1/purchases?branch_id=' + manifest.branch_id, { headers })).json();
    const purchase = purchases.find(row => row.folio === 'SR-' + surface + '-' + suffix);
    assert.equal(purchases.filter(row => row.folio === purchase.folio).length, 1);
    assert.equal(purchase.lines.length, 3);
    assert.equal(String(purchase.total), '562.015000');
    const tableRow = page.locator('tr').filter({ hasText: purchase.folio });
    await tableRow.getByRole('button', { name: 'Confirmar', exact: true }).click();
    const review = page.getByRole('heading', { name: 'Revisar nota registrada' });
    await review.waitFor();
    await page.getByRole('button', { name: 'Confirmar recepción de esta nota' }).click();
    await review.waitFor({ state: 'hidden' });
    const confirmed = (await (await page.request.get(origin + '/api/v1/purchases?branch_id=' + manifest.branch_id, { headers })).json()).find(row => row.id === purchase.id);
    assert.equal(confirmed.inventory_movements.length, 3);
    assert.equal(confirmed.cash_movements.length, 1);
    assert.equal(confirmed.cash_movements[0].amount_cents, 56202);
    await post('/purchases/' + purchase.id + '/cancel', { reason: 'Cierre de fixture SR E2E' });
    const cancelled = (await (await page.request.get(origin + '/api/v1/purchases?branch_id=' + manifest.branch_id, { headers })).json()).find(row => row.id === purchase.id);
    assert.equal(cancelled.inventory_movements.length, 6);
    assert.equal(cancelled.cash_movements.length, 2);
    console.log(surface + ': 3 lines, supplier review, contextual cancel, lost response/replay, persisted review, receipt/cash and compensation passed');
  }
  assert.deepEqual(errors, []);
} catch (error) { await page.screenshot({ path: 'output/playwright/sr-workspace-error.png', fullPage: true }); console.error((await page.locator('body').innerText()).slice(-5000), errors); throw error; } finally { await browser.close(); }
