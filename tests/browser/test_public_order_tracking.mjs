// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-tracking-password-browser-v1
// Password literals are synthetic fixtures; this test requires the loopback-only API.
import assert from 'node:assert/strict';
import { mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';

const base = process.env.TRACKING_BASE_URL || 'http://127.0.0.1:8149';
assert.equal(new URL(base).hostname, '127.0.0.1', 'This test writes only to a local synthetic API');
const manifest = JSON.parse(readFileSync(process.env.TRACKING_MANIFEST, 'utf8'));
assert.equal(manifest.synthetic_only, true);
const { chromium } = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const browser = await chromium.launch({ headless: true,
  ...(process.env.TRACKING_CHROME_PATH ? { executablePath: process.env.TRACKING_CHROME_PATH } : {}),
});
const output = process.env.TRACKING_SCREENSHOT_DIR || 'output/playwright/public-tracking';
mkdirSync(output, { recursive: true });
async function authenticateCustomer(context) {
  const mobile = `/api/v1/mobile/branches/${manifest.public_key}`;
  const customerRequest = async (path, data, method = 'post') => {
    const response = await context.request[method](base + mobile + path, {
      headers: { 'X-Mobile-Request': '1' }, data,
    });
    assert.ok(response.ok(), await response.text()); return response.json();
  };
  const credentials = { phone: '6141234567', password: 'Seguimiento de pedidos seguro 2026!' };
  if (!authenticateCustomer.registered) {
    await customerRequest('/access/register', credentials); authenticateCustomer.registered = true;
  } else await customerRequest('/access/login', credentials);
  await customerRequest('/profile', { name: 'Seguimiento QA', birthday_day: 1, birthday_month: 1 }, 'put');
}

try {
  for (const [width, service] of [[390, 'takeout'], [1280, 'takeout'], [390, 'delivery']]) {
    const suffix = service === 'delivery' ? `delivery-${width}` : width;
    const context = await browser.newContext({ viewport: { width, height: 900 }, permissions: [] });
    const page = await context.newPage();
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const post = async (path, body, authenticated = false) => {
      const response = await context.request.post(base + '/api/v1' + path, {
        headers: { 'Idempotency-Key': randomUUID(), ...(authenticated ? { Authorization: `Bearer ${manifest.token}` } : {}) }, data: body,
      });
      assert.ok(response.ok(), await response.text()); return response.json();
    };
    await authenticateCustomer(context);
    const intent = await post(`/public/branches/${manifest.public_key}/order-intents`, {
      customer_name: 'Seguimiento QA', customer_phone: '+526141234567', order_type: service,
      ...(service === 'delivery' ? { delivery_address: { address_text: 'Calle de prueba 123' } } : {}),
      lines: [{ product_id: manifest.product_id, quantity: 1 }],
    });
    // Start from the same browser capability that successful public checkout persists.
    await context.addInitScript(({ branch, reference }) => {
      if (!localStorage.getItem('kiwi_selected_branch_id')) localStorage.setItem('kiwi_selected_branch_id', branch);
      if (!localStorage.getItem('kiwi_public_tracking_v1')) localStorage.setItem('kiwi_public_tracking_v1', JSON.stringify({ version: 1,
        references: [{ public_reference: reference, branch_id: branch }] }));
    }, { branch: manifest.branch_id, reference: intent.public_reference });
    await page.goto(base + '/menu/');
    const tracker = page.getByRole('region', { name: 'Seguimiento de tu pedido' });
    await tracker.getByRole('heading', { name: 'Esperando confirmación' }).waitFor();
    assert.equal(await tracker.locator('[aria-current="step"]').count(), 0);
    await page.screenshot({ path: join(output, `pending-${suffix}.png`) });
    const accounts = await (await context.request.get(base + '/api/v1/orders/accounts?branch_id=' + manifest.branch_id,
      { headers: { Authorization: `Bearer ${manifest.token}` } })).json();
    const pending = accounts.items.find(item => item.public_reference === intent.public_reference);
    assert.ok(pending);
    const order = await post(`/order-intents/${pending.id}/accept`, { expected_version: 1 }, true);
    await tracker.getByRole('heading', { name: 'Pedido confirmado' }).waitFor({ timeout: 15000 });
    assert.equal(await tracker.locator('[aria-current="step"]').innerText(), 'Confirmado');
    const detail = await (await context.request.get(base + '/api/v1/orders/' + order.id,
      { headers: { Authorization: `Bearer ${manifest.token}` } })).json();
    const tasks = detail.production_tasks;
    assert.ok(Array.isArray(tasks) && tasks.length);
    for (const task of tasks) {
      await post(`/kds/tasks/${task.id}/transition`, { status: 'IN_PROGRESS', branch_id: manifest.branch_id }, true);
    }
    await tracker.getByRole('heading', { name: 'En preparación' }).waitFor({ timeout: 15000 });
    await page.screenshot({ path: join(output, `preparing-${suffix}.png`) });
    for (const task of tasks) await post(`/kds/tasks/${task.id}/transition`, { status: 'COMPLETED', branch_id: manifest.branch_id }, true);
    await tracker.getByRole('heading', { name: service === 'delivery' ? 'Listo para salir' : 'Listo para recoger' }).waitFor({ timeout: 15000 });
    await tracker.getByRole('button', { name: /Ver detalle/ }).click();
    await page.screenshot({ path: join(output, `ready-${suffix}.png`) });
    if (service === 'delivery') {
      await post(`/orders/${order.id}/fulfillment/start_delivery`, {}, true);
      await tracker.getByRole('heading', { name: 'En camino' }).waitFor({ timeout: 15000 });
      await page.screenshot({ path: join(output, `in-delivery-${width}.png`) });
    }
    await post(`/orders/${order.id}/fulfillment/deliver`, {}, true);
    await tracker.getByRole('heading', { name: 'Pedido entregado' }).waitFor({ timeout: 15000 });
    await page.reload();
    await tracker.getByRole('heading', { name: 'Pedido entregado' }).waitFor();
    assert.equal(await tracker.getByText('En camino', { exact: true }).count(), service === 'delivery' ? 1 : 0);
    await page.screenshot({ path: join(output, `delivered-${suffix}.png`) });
    await page.getByRole('button', { name: 'Cambiar sucursal' }).click();
    await page.getByRole('dialog', { name: 'Seleccionar sucursal' }).getByRole('button', { name: /Norte/ }).click();
    assert.equal(await tracker.count(), 0);
    await page.getByRole('button', { name: 'Cambiar sucursal' }).click();
    await page.getByRole('dialog', { name: 'Seleccionar sucursal' }).getByRole('button', { name: /Sucursal Piloto/ }).click();
    await tracker.getByRole('heading', { name: 'Pedido entregado' }).waitFor();
    await page.getByRole('button', { name: 'Ocultar seguimiento en este navegador' }).click();
    assert.equal(await tracker.count(), 0);
    assert.deepEqual(errors, []);
    await context.close();
  }
  // Exercise successful public checkout with persistent and unavailable tracking storage.
  for (const blockTrackingStorage of [false, true]) {
  const memoryContext = await browser.newContext({ viewport: { width: 390, height: 900 } });
  await memoryContext.addInitScript(({ branch, blocked }) => {
    localStorage.setItem('kiwi_selected_branch_id', branch);
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (blocked && key === 'kiwi_public_tracking_v1') throw new DOMException('Storage quota', 'QuotaExceededError');
      return original.call(this, key, value);
    };
  }, { branch: manifest.branch_id, blocked: blockTrackingStorage });
  const memoryPage = await memoryContext.newPage();
  const memoryErrors = []; memoryPage.on('pageerror', error => memoryErrors.push(error.message));
  await authenticateCustomer(memoryContext);
  await memoryPage.goto(base + '/menu/');
  const catalogue = await (await memoryContext.request.get(base + `/api/v1/public/branches/${manifest.public_key}/catalog`)).json();
  const product = catalogue.items.find(item => item.id === manifest.product_id);
  await memoryPage.getByRole('button', { name: `Agregar ${product.name} al pedido`, exact: true }).click();
  await memoryPage.getByRole('button', { name: 'Abrir carrito de compras' }).click();
  assert.equal(await memoryPage.getByPlaceholder('Tu nombre completo *').inputValue(), 'Seguimiento QA');
  assert.equal(await memoryPage.getByPlaceholder('Teléfono Celular *').inputValue(), '+526141234567');
  const sent = memoryPage.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/order-intents'));
  await memoryPage.getByRole('button', { name: /Enviar Pedido/ }).click();
  const memoryIntent = await (await sent).json();
  const memoryTracker = memoryPage.getByRole('region', { name: 'Seguimiento de tu pedido' }).last();
  await memoryTracker.getByRole('heading', { name: 'Esperando confirmación' }).waitFor();
  if (blockTrackingStorage) await memoryTracker.getByText(/El navegador no pudo guardarlo/).waitFor();
  const accountResponse = await memoryContext.request.get(base + '/api/v1/orders/accounts?branch_id=' + manifest.branch_id,
    { headers: { Authorization: `Bearer ${manifest.token}` } });
  const memoryAccount = (await accountResponse.json()).items.find(item => item.public_reference === memoryIntent.public_reference);
  assert.ok(memoryAccount);
  const memoryAccepted = await memoryContext.request.post(base + `/api/v1/order-intents/${memoryAccount.id}/accept`, {
    headers: { Authorization: `Bearer ${manifest.token}`, 'Idempotency-Key': randomUUID() }, data: { expected_version: 1 },
  });
  assert.ok(memoryAccepted.ok(), await memoryAccepted.text());
  await memoryTracker.getByRole('heading', { name: 'Pedido confirmado' }).waitFor({ timeout: 15000 });
  assert.equal(await memoryPage.getByText('Pendiente de revisión', { exact: true }).count(), 0);
  await memoryPage.screenshot({ path: join(output, blockTrackingStorage ? 'storage-unavailable-390.png' : 'checkout-confirmed-390.png') });
  await memoryPage.getByRole('button', { name: 'Cerrar', exact: true }).click();
  await memoryPage.getByRole('region', { name: 'Seguimiento de tu pedido' }).getByRole('heading', { name: 'Pedido confirmado' }).waitFor();
  if (!blockTrackingStorage) {
    await memoryPage.reload();
    await memoryPage.getByRole('region', { name: 'Seguimiento de tu pedido' }).getByRole('heading', { name: 'Pedido confirmado' }).waitFor();
  }
  await memoryPage.evaluate(() => { Storage.prototype.setItem = () => { throw new DOMException('Blocked storage'); }; });
  await memoryPage.getByRole('button', { name: 'Agregar a favoritos', exact: true }).first().click();
  await memoryPage.getByRole('button', { name: 'Cambiar sucursal' }).click();
  await memoryPage.getByRole('dialog', { name: 'Seleccionar sucursal' }).getByRole('button', { name: /Norte/ }).click();
  assert.equal(await memoryPage.getByRole('region', { name: 'Seguimiento de tu pedido' }).count(), 0);
  assert.deepEqual(memoryErrors, []);
  await memoryContext.close();
  }
  console.log('Public tracking: real API lifecycle, refresh, dismissal, checkout, storage fallback and responsive UI passed');
} finally { await browser.close(); }
