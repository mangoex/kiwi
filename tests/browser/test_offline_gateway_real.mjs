import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, rm, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, resolve, sep } from 'node:path';
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';

const root = process.cwd();
const metadata = join(tmpdir(), `restaurantos-offline-gateway-e2e-${process.pid}.json`);
const { chromium } = await import(process.env.OFFLINE_PLAYWRIGHT_IMPORT || 'playwright');

function server() {
  return createServer(async (req, res) => {
    const url = new URL(req.url || '/', 'http://127.0.0.1:4177');
    const prefix = url.pathname.startsWith('/kds/') ? 'kds-web' : 'pos-web';
    const relative = url.pathname.replace(/^\/(pos|kds)\/?/, '') || 'index.html';
    const directory = resolve(root, 'apps', prefix, 'dist');
    const file = resolve(directory, relative);
    if (!file.startsWith(`${directory}${sep}`) || !existsSync(file)) { res.writeHead(404); return res.end(); }
    const body = await readFile(file);
    res.writeHead(200, { 'Content-Type': file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html', 'Vary': 'Origin' });
    res.end(body);
  });
}

await rm(metadata, { force: true });
const fixture = spawn('python', ['tests/e2e/offline_gateway_fixture.py', '--port', '8767', '--metadata', metadata], { cwd: root, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let fixtureOutput = '';
fixture.stdout.on('data', (chunk) => { fixtureOutput += chunk.toString(); });
fixture.stderr.on('data', (chunk) => { fixtureOutput += chunk.toString(); });
let fixtureExit = null;
fixture.once('exit', (code) => { fixtureExit = code; });
const staticServer = server();
let browser;
await new Promise((resolve) => staticServer.listen(4177, '127.0.0.1', resolve));
try {
  for (let i = 0; i < 600 && !existsSync(metadata); i += 1) await new Promise((resolve) => setTimeout(resolve, 100));
  assert.ok(existsSync(metadata), `gateway fixture metadata must be ready; exit=${fixtureExit}; cwd=${root}; python=${process.env.PYTHON || 'python'}; ${fixtureOutput.replace(/[A-Za-z0-9_-]{100,}/g, '[redacted]')}`);
  const config = JSON.parse(await readFile(metadata, 'utf8'));
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  await context.addInitScript((state) => {
    localStorage.setItem('auth_token', 'synthetic-local-only');
    localStorage.setItem('pos_register_id', 'CAJA-01');
    localStorage.setItem('pos_operational_orders_enabled', 'true');
    localStorage.setItem('pos_operational_orders_branch_id', state.branch_id);
    localStorage.setItem('pos_operational_orders_device_id', state.device_id);
    localStorage.setItem('pos_operational_orders_gateway_url', state.gateway_url);
    sessionStorage.setItem('pos_offline_order_grant_v3', state.grant);
    sessionStorage.setItem('pos_offline_order_grant_v3_expires_at', new Date(Date.now() + 1_000_000).toISOString());
    sessionStorage.setItem('pos_offline_order_grant_v3_branch_id', state.branch_id);
    sessionStorage.setItem('pos_offline_order_grant_v3_device_id', state.device_id);
    sessionStorage.setItem('pos_offline_order_grant_v3_gateway_url', state.gateway_url);
  }, config);
  await page.goto('http://127.0.0.1:4177/pos/', { waitUntil: 'networkidle' });
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload({ waitUntil: 'networkidle' });
  const kitchen = await context.newPage();
  await kitchen.goto('http://127.0.0.1:4177/kds/', { waitUntil: 'networkidle' });
  await kitchen.evaluate(() => navigator.serviceWorker.ready);
  await kitchen.reload({ waitUntil: 'networkidle' });
  await new Promise((resolve) => staticServer.close(resolve));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByPlaceholder('Buscar producto…').waitFor();
  await kitchen.reload({ waitUntil: 'domcontentloaded' });
  await kitchen.getByText('Sistema KDS de Cocina').waitFor();
  await mkdir('output/playwright', { recursive: true });
  await page.screenshot({ path: 'output/playwright/offline-gateway-pos-reload.png', fullPage: true });
  await page.getByRole('button', { name: 'Combos', exact: true }).click();
  await page.locator('.pos-sale-product-card-select').filter({ hasText: 'Combo fijo' }).click();
  await page.locator('.pos-sale-pay').click();
  await page.getByRole('button', { name: /Efectivo/ }).click();
  const createdPromise = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/order-api/orders'));
  const paidPromise = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/payments'));
  await page.getByRole('button', { name: /Confirmar cobro/ }).click();
  const created = await createdPromise;
  assert.equal(created.status(), 200, await created.text());
  const order = await created.json();
  assert.equal(order.total_cents, 15900);
  const paid = await paidPromise;
  assert.equal(paid.status(), 200, await paid.text());
  assert.equal((await paid.json())._offline.status, 'PENDING_SYNC');
  await page.getByRole('button', { name: /Confirmar cobro/ }).waitFor({ state: 'hidden' });
  await page.screenshot({ path: 'output/playwright/offline-gateway-payment.png', fullPage: true });
  await kitchen.reload({ waitUntil: 'domcontentloaded' });
  for (const task of order.production_tasks) {
    const card = kitchen.locator('.kds-order-card').filter({ hasText: task.product_name });
    for (const label of ['Iniciar Preparación', 'Marcar Listo']) {
      const responsePromise = kitchen.waitForResponse(response => response.request().method() === 'POST' && response.url().includes(`/kds/tasks/${task.id}/`));
      await card.getByRole('button', { name: label }).click();
      const response = await responsePromise;
      assert.equal(response.status(), 200, await response.text());
      await card.getByRole('button', { name: label }).waitFor({ state: 'hidden' });
    }
  }
  const detailResponse = await context.request.get(`${config.gateway_url}/api/v1/local/order-api/orders/${order.id}`, { headers: { Authorization: `Offline ${config.grant}` } });
  assert.equal(detailResponse.status(), 200);
  const detail = await detailResponse.json();
  assert.equal(detail.payments.length, 1);
  assert.equal(detail.payments[0].amount_cents, 15900);
  assert.equal(detail.production_tasks.length, 2);
  assert.ok(detail.production_tasks.every(task => task.status === 'COMPLETED'));
  await kitchen.screenshot({ path: 'output/playwright/offline-gateway-kds.png', fullPage: true });
  await context.close(); await browser.close();
  console.log('Offline gateway POS payment and KDS E2E passed');
} finally {
  await browser?.close();
  if (staticServer.listening) await new Promise((resolve) => staticServer.close(resolve));
  fixture.kill('SIGTERM');
  await rm(metadata, { force: true });
}
