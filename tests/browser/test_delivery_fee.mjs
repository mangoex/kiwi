import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdtempSync, mkdirSync, existsSync, cpSync } from 'node:fs';
import { rm } from 'node:fs/promises';
import { resolve, join, delimiter } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const { chromium } = await import(process.env.DELIVERY_FEE_PLAYWRIGHT_IMPORT || 'playwright');
const root = resolve(import.meta.dirname, '../..');
const temporaryRoot = join(root, 'output', 'delivery-fee-fixtures');
mkdirSync(temporaryRoot, { recursive: true });
const fixture = mkdtempSync(join(temporaryRoot, 'restaurantos-delivery-browser-'));
const database = join(fixture, 'delivery_fee_browser.sqlite');
for (const name of ['admin-web', 'pos-web']) cpSync(join(root, `apps/${name}/dist`), join(fixture, 'static', name), { recursive: true });
const python = process.env.DELIVERY_FEE_PYTHON || (existsSync(join(root, '.venv/Scripts/python.exe')) ? join(root, '.venv/Scripts/python.exe') : 'python');
const environment = { ...process.env, PYTHONPATH: [join(root, 'apps/api'), join(root, 'apps/api/tests')].join(delimiter),
  STATIC_DIR: join(fixture, 'static'), RESTAURANTOS_ENVIRONMENT: 'local', RESTAURANTOS_SECRET_KEY: randomBytes(32).toString('hex'),
  RESTAURANTOS_DATABASE_URL: `sqlite:///${database.replaceAll('\\', '/')}`, RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED: 'false' };
delete environment.DATABASE_URL;
const seeded = JSON.parse(execFileSync(python, ['tests/browser/seed_delivery_fee.py', database], { cwd: root, env: environment, encoding: 'utf8' }));
const port = Number(process.env.DELIVERY_FEE_BROWSER_PORT || 8297);
const base = `http://127.0.0.1:${port}`;
const server = spawn(python, ['-m', 'uvicorn', 'restaurant_os.main:create_app', '--factory', '--host', '127.0.0.1', '--port', String(port)],
  { cwd: root, env: environment, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let serverOutput = '';
server.stdout.on('data', data => { serverOutput += data.toString(); });
server.stderr.on('data', data => { serverOutput += data.toString(); });
const branch = '018f6f73-2d0a-74f0-8f1c-000000000003';
let browser;
async function api(path, body) {
  const response = await fetch(`${base}/api/v1${path}`, { method: body ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${seeded.token}`, 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  assert.equal(response.ok, true, `${path}: ${await response.clone().text()}`);
  return response.json();
}
try {
  for (let tries = 0; tries < 100; tries++) {
    if (server.exitCode !== null) throw new Error(serverOutput.slice(-2000));
    try { if ((await fetch(`${base}/api/v1/health`)).status < 500) break; } catch { /* Wait for the isolated fixture server. */ }
    await delay(200);
  }
  const standard = await api('/delivery-tariffs', { code: 'STANDARD', name: 'Estándar', amount_cents: 2800 });
  const other = await api('/delivery-tariffs', { code: 'ZONE', name: 'Zona amplia', amount_cents: 4200 });
  await api('/delivery-policies', { branch_id: branch, expected_version: 0, enabled: true,
    eligible_tariff_ids: [standard.id, other.id], default_tariff_id: standard.id, free_threshold_cents: 50000 });
  await api('/cash-shifts/open', { branch_id: branch, register_id: 'CAJA-01', opening_cash_cents: 50000 });
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.addInitScript(({ token }) => {
    localStorage.setItem('auth_token', token); localStorage.setItem('pos_register_id', 'CAJA-01');
  }, { token: seeded.token });
  await page.goto(`${base}/admin/delivery-services`);
  await page.getByRole('heading', { name: 'Servicios de domicilio', exact: true }).waitFor();
  await page.getByText('Estándar', { exact: true }).first().waitFor();
  assert.equal(await page.locator('.admin-topbar').getByText('Administración corporativa', { exact: true }).count(), 1,
    'Corporate screens must not display the POS active branch as their configuration scope');
  const output = process.env.DELIVERY_FEE_SCREENSHOT_DIR || join(root, 'output/playwright/delivery-fee');
  mkdirSync(output, { recursive: true });
  const addTariff = page.getByRole('button', { name: 'Agregar tarifa', exact: true });
  assert.equal(await addTariff.count(), 1, 'Tariff creation must open a separate editor');
  await addTariff.click();
  const editor = page.getByRole('dialog', { name: 'Agregar tarifa', exact: true });
  await editor.waitFor();
  assert.equal(await editor.getByLabel('Código', { exact: true }).evaluate(node => node === document.activeElement), true);
  for (const width of [390, 1024, 1440]) {
    await page.setViewportSize({ width, height: 960 });
    assert.equal(await editor.evaluate(node => node.scrollWidth <= node.clientWidth + 1), true);
    await page.screenshot({ path: join(output, `tariff-editor-${width}.png`) });
  }
  for (let tab = 0; tab < 12; tab++) {
    await page.keyboard.press('Tab');
    assert.equal(await editor.evaluate(node => node.contains(document.activeElement)), true);
  }
  for (let tab = 0; tab < 12; tab++) {
    await page.keyboard.press('Shift+Tab');
    assert.equal(await editor.evaluate(node => node.contains(document.activeElement)), true);
  }
  await page.keyboard.press('Escape');
  await editor.waitFor({ state: 'hidden' });
  assert.equal(await addTariff.evaluate(node => node === document.activeElement), true);
  await addTariff.click();
  await editor.getByLabel('Código', { exact: true }).fill('SCHEDULED');
  await editor.getByLabel('Nombre', { exact: true }).fill('Entrega programada');
  await editor.getByLabel('Precio con IVA incluido', { exact: true }).fill('35.00');
  const createdReply = page.waitForResponse(response => response.url().endsWith('/api/v1/delivery-tariffs') && response.request().method() === 'POST');
  await editor.getByRole('button', { name: 'Guardar tarifa', exact: true }).click();
  const createdResponse = await createdReply;
  assert.equal(createdResponse.status(), 200, await createdResponse.text());
  const scheduled = await createdResponse.json();
  assert.equal(scheduled.amount_cents, 3500);
  await editor.waitFor({ state: 'hidden' });
  await page.getByRole('button', { name: 'Editar Entrega programada', exact: true }).click();
  const revisionEditor = page.getByRole('dialog', { name: 'Editar tarifa', exact: true });
  await revisionEditor.getByLabel('Precio con IVA incluido', { exact: true }).fill('36.00');
  const revisionReply = page.waitForResponse(response => response.url().endsWith(`/delivery-tariffs/${scheduled.id}/revisions`) && response.request().method() === 'POST');
  await revisionEditor.getByRole('button', { name: 'Guardar tarifa', exact: true }).click();
  const revisionResponse = await revisionReply;
  assert.equal(revisionResponse.status(), 200, await revisionResponse.text());
  const revised = await revisionResponse.json();
  assert.equal(revised.version, 2);
  assert.equal(revised.amount_cents, 3600);
  await revisionEditor.waitFor({ state: 'hidden' });
  const policyForm = page.getByRole('region', { name: 'Reglas de envío', exact: true });
  const operationalBranch = await page.evaluate(() => localStorage.getItem('admin_branch_id'));
  await policyForm.getByText('Las sucursales con reglas propias conservan su configuración.', { exact: true }).waitFor();
  async function loadBranchPolicy() {
    await page.getByLabel('Sucursal o configuración general', { exact: true }).selectOption(branch);
    await policyForm.getByText('Configuración propia de la sucursal', { exact: true }).waitFor();
  }
  async function saveAdminPolicy() {
    const reply = page.waitForResponse(response => response.url().endsWith('/api/v1/delivery-policies') && response.request().method() === 'POST');
    await policyForm.getByRole('button', { name: 'Guardar configuración', exact: true }).click();
    const response = await reply;
    assert.equal(response.status(), 200, await response.text());
    return response.json();
  }
  await loadBranchPolicy();
  assert.equal(await page.locator('.admin-topbar').getByText('Administración corporativa', { exact: true }).count(), 1);
  assert.equal(await page.evaluate(() => localStorage.getItem('admin_branch_id')), operationalBranch);
  const minimum = policyForm.getByLabel('Subtotal mínimo después de descuentos', { exact: true });
  assert.equal(await minimum.inputValue(), '500.00');
  await minimum.fill('300.00');
  await policyForm.getByText('Gratis desde $300.00', { exact: true }).waitFor();
  assert.equal((await saveAdminPolicy()).free_threshold_cents, 30000);
  await policyForm.getByRole('status').getByText('Configuración guardada para esta sucursal.', { exact: true }).waitFor();
  await minimum.fill('301.00');
  assert.equal(await policyForm.getByRole('status').count(), 0, 'Editing must clear the previous saved confirmation');
  await page.reload();
  await loadBranchPolicy();
  assert.equal(await minimum.inputValue(), '300.00');
  await policyForm.getByLabel('Envío gratis desde un monto', { exact: true }).uncheck();
  assert.equal((await saveAdminPolicy()).free_threshold_cents, null);
  await page.reload();
  await loadBranchPolicy();
  assert.equal(await policyForm.getByLabel('Envío gratis desde un monto', { exact: true }).isChecked(), false);
  await policyForm.getByLabel('Envío gratis desde un monto', { exact: true }).check();
  await minimum.fill('500.00');
  assert.equal((await saveAdminPolicy()).free_threshold_cents, 50000);
  for (const width of [390, 1024, 1440]) {
    await page.setViewportSize({ width, height: 960 });
    await page.getByRole('heading', { name: 'Servicios de domicilio', exact: true }).scrollIntoViewIfNeeded();
    assert.equal(await page.locator('.delivery-services').evaluate(node => node.scrollWidth <= node.clientWidth + 1), true);
    await page.screenshot({ path: join(output, `catalog-${width}.png`), fullPage: true });
    await policyForm.getByRole('button', { name: 'Guardar configuración', exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: join(output, `rules-${width}.png`) });
  }
  await page.goto(`${base}/pos/?branch_id=${branch}`);
  await page.getByRole('button', { name: 'Domicilio', exact: true }).click();
  await page.getByPlaceholder('Buscar producto…').fill('Hamburguesa');
  await page.locator('.pos-sale-product-card-select').filter({ hasText: 'Hamburguesa Kiwi' }).click();
  const service = page.getByRole('group', { name: 'Servicio de domicilio' });
  const shippingDetails = service.locator('details');
  assert.equal(await shippingDetails.count(), 1, 'Shipping must use a compact disclosure');
  assert.equal(await shippingDetails.getAttribute('open'), null, 'Shipping starts collapsed');
  await shippingDetails.locator('summary').focus();
  await page.keyboard.press('Enter');
  await service.getByText('$28.00 · IVA 16% incluido', { exact: true }).waitFor();
  await page.getByLabel('Tarifa de envío').selectOption(other.id);
  await service.getByText('$42.00 · IVA 16% incluido', { exact: true }).waitFor();
  await service.getByRole('button', { name: 'Quitar envío' }).click();
  await service.getByText('Envío retirado manualmente', { exact: true }).waitFor();
  // Reload must recover explicit removal, rather than silently re-add the default.
  await delay(700);
  await page.reload();
  await shippingDetails.locator('summary').click();
  await service.getByText('Envío retirado manualmente', { exact: true }).waitFor();
  await service.getByRole('button', { name: 'Restaurar envío' }).click();
  await service.getByText('$28.00 · IVA 16% incluido', { exact: true }).waitFor();
  for (let count = 0; count < 5; count++) await page.getByRole('button', { name: 'Sumar Hamburguesa Kiwi', exact: true }).click();
  await service.getByText(/Envío gratis por monto/).waitFor();
  assert.equal(await service.getByRole('status').textContent(), 'Envío gratis por monto mínimo');
  assert.equal(await service.getByText(/Base del envío:/).count(), 0);
  await shippingDetails.locator('summary').getByText('Gratis', { exact: true }).waitFor();
  assert.equal(await service.locator(`option[value="${other.id}"]`).textContent(), 'Zona amplia');
  await page.getByLabel('Tarifa de envío').selectOption(other.id);
  await service.getByText('Envío gratis por monto mínimo', { exact: true }).waitFor();
  assert.equal(await service.locator('option:checked').textContent(), 'Zona amplia');
  for (const width of [390, 1024, 1440]) {
    await page.setViewportSize({ width, height: 960 });
    await service.scrollIntoViewIfNeeded();
    await page.screenshot({ path: join(output, `order-${width}.png`), fullPage: true });
  }
  for (let count = 0; count < 5; count++) await page.getByRole('button', { name: 'Restar Hamburguesa Kiwi', exact: true }).click();
  await service.getByText('$42.00 · IVA 16% incluido', { exact: true }).waitFor();
  await service.getByText('Base del envío: $36.21 · IVA: $5.79', { exact: true }).waitFor();
  await shippingDetails.locator('summary').getByText('$42.00', { exact: true }).waitFor();
  assert.equal(await service.locator('option:checked').textContent(), 'Zona amplia · $42.00');
  await page.getByLabel('Tarifa de envío').selectOption('AUTO');
  await service.getByText('$28.00 · IVA 16% incluido', { exact: true }).waitFor();
  await service.getByText('Base del envío: $24.14 · IVA: $3.86', { exact: true }).waitFor();
  await shippingDetails.locator('summary').getByText('$28.00', { exact: true }).waitFor();
  assert.equal(await shippingDetails.locator('summary').getByText('Gratis', { exact: true }).count(), 0);
  await shippingDetails.locator('summary').click();
  for (const name of ['Papas', 'Refresco']) {
    await page.getByPlaceholder('Buscar producto…').fill(name);
    await page.locator('.pos-sale-product-card-select').filter({ hasText: name }).click();
  }
  await page.getByPlaceholder('Buscar producto…').fill('');
  await page.locator('.pos-sale-summary .total').getByText('$198.00', { exact: true }).waitFor();
  await page.waitForFunction(() => document.querySelector('.pos-sale-pay')?.disabled === false);
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport);
    const items = page.locator('.pos-sale-cart-items');
    const box = await items.boundingBox();
    await page.screenshot({ path: join(output, `order-compact-${viewport.width}.png`) });
    assert.ok(box && box.height >= 240, `Product list needs >=240px at ${viewport.width}x${viewport.height}: ${box?.height}`);
    assert.equal(await items.evaluate(node => getComputedStyle(node).overflowY), 'auto');
    const confirmation = await page.locator('.pos-sale-pay').boundingBox();
    assert.ok(confirmation && confirmation.y >= 0 && confirmation.y + confirmation.height <= viewport.height);
    if (viewport.height === 768) {
      assert.equal(await items.evaluate(node => node.scrollHeight > node.clientHeight), true);
      await page.getByRole('button', { name: 'Restar Refresco', exact: true }).scrollIntoViewIfNeeded();
      assert.equal(await items.evaluate(node => node.scrollTop > 0), true);
      await items.evaluate(node => { node.scrollTop = 0; });
    }
    const before = await items.boundingBox();
    await shippingDetails.locator('summary').focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.getByLabel('Tarifa de envío').isVisible(), true);
    const after = await items.boundingBox();
    assert.equal(after.height, before.height, 'Opening shipping must not shrink the product list');
    await page.screenshot({ path: join(output, `order-options-${viewport.width}.png`) });
    await shippingDetails.locator('summary').click();
    await page.locator('.pos-sale-cart-heading strong').click();
    await page.screenshot({ path: join(output, `order-compact-${viewport.width}.png`) });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('.pos-sale-cart').scrollIntoViewIfNeeded();
  assert.equal(await page.locator('.pos-sale-cart').evaluate(node => node.scrollWidth <= node.clientWidth + 1), true);
  await page.screenshot({ path: join(output, 'order-compact-390.png'), fullPage: true });
  await page.locator('.pos-sale-pay').scrollIntoViewIfNeeded();
  const mobileConfirmation = await page.locator('.pos-sale-pay').boundingBox();
  assert.ok(mobileConfirmation && mobileConfirmation.y >= 0 && mobileConfirmation.y + mobileConfirmation.height <= 844);
  await page.screenshot({ path: join(output, 'order-confirm-390.png') });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('button', { name: 'Nota de Hamburguesa Kiwi', exact: true }).click();
  await page.getByLabel('Nota para cocina', { exact: true }).fill('Sin cebolla. Empacar por separado.');
  await page.getByRole('button', { name: 'Aplicar cambios', exact: true }).click();
  await page.getByText('Nota: Sin cebolla. Empacar por separado.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Eliminar Refresco del pedido', exact: true }).click();
  assert.equal(await page.locator('.pos-sale-cart-item').count(), 2);
  const payload = { branch_id: branch, order_type: 'delivery', delivery_selection: { mode: 'AUTO' },
    lines: [{ product_id: '018f6f73-2d0a-74f0-8f1c-000000000111', quantity: 1 }] };
  assert.equal((await api('/orders/quote', payload)).total_cents, 12300);
  assert.equal((await api('/orders/quote', { ...payload, delivery_selection: { mode: 'SELECTED', tariff_id: other.id } })).total_cents, 13700);
  assert.equal((await api('/orders/quote', { ...payload, delivery_selection: { mode: 'REMOVED' } })).total_cents, 9500);
  const customer = await api('/customers', { branch_id: branch, name: 'Cliente sintético', phones: [{ number: '6691239876', is_primary: true }] });
  const address = await api(`/customers/${customer.id}/addresses`, { branch_id: branch, alias: 'Prueba', street: 'Prueba',
    exterior_number: '1', neighborhood: 'Centro', postal_code: '80000', city: 'Culiacán', municipality: 'Culiacán', state: 'Sinaloa', is_default: true });
  const priced = await api('/orders/quote', payload);
  const order = await api('/orders', { ...payload, register_id: 'CAJA-01', payment_method_intent: 'cash',
    customer_id: customer.id, delivery_address_id: address.id, delivery_quote_reference: priced.delivery_quote_reference });
  await api(`/orders/${order.id}/payments`, { amount_cents: 12300, method: 'cash', register_id: 'CAJA-01' });
  const params = new URLSearchParams({ branch_id: branch, start: new Date(Date.now() - 86400000).toISOString(), end: new Date(Date.now() + 86400000).toISOString() });
  assert.deepEqual((await api(`/reports/delivery-fees?${params}`)).summary, { entry_count: 1, gross_cents: 2800, net_cents: 2414, tax_cents: 386 });
  await page.goto(`${base}/pos/sales-monitor`);
  await page.getByRole('heading', { name: 'Cargos de domicilio', exact: true }).waitFor();
  await page.getByText(/IVA 16% incluido: \$3.86/).waitFor();
  await page.screenshot({ path: join(output, 'report-1440.png'), fullPage: true });
  console.log('Delivery Admin create/edit/policy persistence/keyboard; POS selection/removal/reload/restore/threshold; API order/payment and report passed');
} finally {
  await browser?.close();
  if (server.exitCode === null) {
    const closed = new Promise(resolve => server.once('close', resolve));
    server.kill();
    await closed;
  }
  assert.ok(resolve(fixture).startsWith(resolve(temporaryRoot) + '\\') || resolve(fixture).startsWith(resolve(temporaryRoot) + '/'));
  await rm(fixture, { recursive: true, force: true, maxRetries: 20, retryDelay: 100 });
}
