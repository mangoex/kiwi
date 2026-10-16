import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { corporateAdminSession } from '../fixtures/admin_session_fixture.mjs';

const { chromium } = await import(process.env.DRIVER_CASH_PLAYWRIGHT_IMPORT || 'playwright');
const pos = process.env.DRIVER_CASH_POS_URL || 'http://127.0.0.1:3001/pos';
const output = process.env.DRIVER_CASH_SCREENSHOT_DIR || 'output/playwright/driver-cash-settlement';
const id = value => `018f6f73-2d0a-74f0-8f1c-${String(value).padStart(12, '0')}`;
const branchId = id(3);
const driverId = id(90);
const orderIds = [id(501), id(502), id(503)];
const profile = corporateAdminSession(
  { id: id(6), display_name: 'Dueño QA', email: 'driver-cash@example.invalid' },
  branchId,
);
profile.permissions.push('payments.confirm');
profile.admin_capabilities['payments.confirm'] = true;
profile.organization_id = id(1);
profile.scope.authorization_version = 1;
profile.active_branch = { ...profile.active_branch, timezone: 'America/Mazatlan' };
profile.pos_modules = {};

mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  ...(process.env.DRIVER_CASH_CHROME_PATH
    ? { executablePath: process.env.DRIVER_CASH_CHROME_PATH }
    : {}),
});
try {
  for (const width of [1440, 390]) {
    let settled = false;
    const writes = [];
    const errors = [];
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'driver-cash-synthetic-session');
      localStorage.setItem('pos_register_id', 'CAJA-QA');
    });
    await page.route('**/api/v1/**', async route => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace('/api/v1', '');
      if (path === '/auth/session') return route.fulfill({ json: profile });
      if (path === '/orders/pending-count') return route.fulfill({ json: { count: 0 } });
      if (path === '/driver-cash-settlements/drivers') {
        return route.fulfill({ json: [{
          id: driverId,
          name: 'Repartidor QA',
          status: 'active',
          eligible_order_count: settled ? 0 : 2,
          eligible_total_cents: settled ? 0 : 30000,
        }] });
      }
      if (path === '/orders/accounts') {
        const common = {
          branch_id: branchId,
          cash_shift_id: id(80),
          register_code: 'CAJA-QA',
          status: 'ACCEPTED',
          service_type: 'delivery',
          currency: 'MXN',
          created_at: '2026-10-15T18:00:00Z',
          customer_label: 'Cliente QA',
          driver_id: driverId,
          driver_name: 'Repartidor QA',
          production_summary: { task_count: 1, started: true },
          reopen_eligible: false,
          active_reopen_request_status: null,
        };
        return route.fulfill({ json: {
          items: [
            { ...common, id: orderIds[0], folio: 'QA-0501', total_cents: 10000,
              payment_status: settled ? 'CONFIRMED' : 'PENDING', payment_method_intent: 'cash',
              settlement_eligible: !settled },
            { ...common, id: orderIds[1], folio: 'QA-0502', total_cents: 20000,
              payment_status: settled ? 'CONFIRMED' : 'PENDING', payment_method_intent: 'cash',
              settlement_eligible: !settled },
            { ...common, id: orderIds[2], folio: 'QA-0503', total_cents: 15000,
              payment_status: 'PENDING', payment_method_intent: 'debit_card',
              settlement_eligible: false },
          ],
          next_cursor: null,
        } });
      }
      if (path === '/driver-cash-settlements' && request.method() === 'POST') {
        const body = request.postDataJSON();
        writes.push({ body, key: request.headers()['idempotency-key'] });
        settled = true;
        return route.fulfill({ json: {
          id: id(700),
          driver_id: driverId,
          status: 'CONFIRMED',
          order_count: 2,
          total_cents: 30000,
        } });
      }
      return route.fulfill({ json: [] });
    });

    await page.goto(`${pos}/history`, { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Servicio').selectOption('delivery');
    const driver = page.getByLabel('Repartidor');
    await driver.selectOption(driverId);
    const eligible = page.locator('tbody input[type="checkbox"]:not(:disabled)');
    const ineligible = page.locator('tbody input[type="checkbox"]:disabled');
    await eligible.first().waitFor({ state: 'attached' });
    assert.equal(await eligible.count(), 2);
    assert.equal(await ineligible.count(), 1);
    await page.getByLabel('Seleccionar todos los pedidos elegibles cargados').check();
    await page.getByText('2 pedido(s) · $300.00', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Recibir efectivo del repartidor' }).click();
    await page.getByText('Efectivo esperado').waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(output, `confirm-${width}.png`), fullPage: true });
    await page.getByRole('button', { name: /Confirmar.*300\.00/ }).click();
    await page.getByText('Liquidación confirmada', { exact: true }).waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(output, `success-${width}.png`), fullPage: true });

    assert.equal(writes.length, 1);
    assert.deepEqual(writes[0].body, {
      branch_id: branchId,
      driver_id: driverId,
      register_id: 'CAJA-QA',
      order_ids: orderIds.slice(0, 2),
    });
    assert.ok(writes[0].key.length >= 12);
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`Driver cash settlement browser flow passed at ${width}px`);
  }
} finally {
  await browser.close();
}
