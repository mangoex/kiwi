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
  await page.getByRole('cell', { name: 'Estándar', exact: true }).waitFor();
  const output = process.env.DELIVERY_FEE_SCREENSHOT_DIR || join(root, 'output/playwright/delivery-fee');
  mkdirSync(output, { recursive: true });
  for (const width of [390, 1024, 1440]) {
    await page.setViewportSize({ width, height: 960 });
    await page.screenshot({ path: join(output, `catalog-${width}.png`), fullPage: true });
  }
  await page.goto(`${base}/pos/?branch_id=${branch}`);
  await page.getByRole('button', { name: 'Domicilio', exact: true }).click();
  await page.getByPlaceholder('Buscar producto…').fill('Hamburguesa');
  await page.locator('.pos-sale-product-card-select').filter({ hasText: 'Hamburguesa Kiwi' }).click();
  const service = page.getByRole('group', { name: 'Servicio de domicilio' });
  await service.getByText('$28.00 · IVA 16% incluido', { exact: true }).waitFor();
  await page.getByLabel('Tarifa de envío').selectOption(other.id);
  await service.getByText('$42.00 · IVA 16% incluido', { exact: true }).waitFor();
  await service.getByRole('button', { name: 'Quitar envío' }).click();
  await service.getByText('Envío retirado manualmente', { exact: true }).waitFor();
  // Reload must recover explicit removal, rather than silently re-add the default.
  await delay(700);
  await page.reload();
  await service.getByText('Envío retirado manualmente', { exact: true }).waitFor();
  await service.getByRole('button', { name: 'Restaurar envío' }).click();
  await service.getByText('$28.00 · IVA 16% incluido', { exact: true }).waitFor();
  for (let count = 0; count < 5; count++) await page.getByRole('button', { name: 'Sumar Hamburguesa Kiwi', exact: true }).click();
  await service.getByText(/Envío gratis por monto/).waitFor();
  for (const width of [390, 1024, 1440]) {
    await page.setViewportSize({ width, height: 960 });
    await service.scrollIntoViewIfNeeded();
    await page.screenshot({ path: join(output, `order-${width}.png`), fullPage: true });
  }
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
  console.log('Delivery catalog, POS selection/removal/reload/restore/threshold, API order/payment and visible report passed');
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
