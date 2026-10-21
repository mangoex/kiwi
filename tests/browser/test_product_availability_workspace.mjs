// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-product-availability-workspace-v1
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { corporateAdminSession } from '../fixtures/admin_session_fixture.mjs';

const { chromium } = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const adminUrl = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
const output = resolve('output/playwright/product-availability-workspace');
mkdirSync(output, { recursive: true });

const branches = [
  { id: '018f6f73-2d0a-74f0-8f1c-000000000001', name: 'Centro', code: 'CENTRO', status: 'active' },
  { id: '018f6f73-2d0a-74f0-8f1c-000000000002', name: 'Norte', code: 'NORTE', status: 'active' },
];
const product = {
  id: '018f6f73-2d0a-74f0-8f1c-000000000111',
  name: 'AGUA DE FRESA LIMÓN CHICA',
  sku: '11001',
  status: 'active',
  effective_availability: true,
  show_in_digital_menu: true,
  has_digital_menu_override: false,
  applicable_branch_count: 2,
  available_branch_count: 2,
  digital_menu_visible_branch_count: 2,
  availability_summary: 'all',
  digital_menu_summary: 'all',
};

const browser = await chromium.launch({
  headless: true,
  ...(process.env.ADMINRETRO_CHROME_PATH ? { executablePath: process.env.ADMINRETRO_CHROME_PATH } : {}),
});

try {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    const label = viewport.width === 390 ? 'mobile' : 'desktop';
    console.log(`Validating availability ${label}`);
    const page = await browser.newPage({ viewport });
    const errors = [];
    const writes = [];
    let digitalVisible = true;
    page.on('pageerror', (error) => errors.push(error.message));
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'availability-qa-token');
      localStorage.setItem('user', JSON.stringify({ id: 'availability-qa', display_name: 'Disponibilidad QA' }));
    });
    await page.route('**/api/v1/**', async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace('/api/v1', '');
      if (path === '/auth/session') {
        return route.fulfill({
          json: corporateAdminSession(
            { id: 'availability-qa', display_name: 'Disponibilidad QA' },
            branches[0].id,
            branches,
          ),
        });
      }
      if (path === '/branch-administration/catalog/products/all-active-summary') {
        return route.fulfill({
          json: {
            scope: 'all_active',
            branches,
            items: [{
              ...product,
              show_in_digital_menu: digitalVisible,
              digital_menu_visible_branch_count: digitalVisible ? 2 : 0,
              digital_menu_summary: digitalVisible ? 'all' : 'none',
            }],
          },
        });
      }
      if (path.endsWith('/digital-menu-visibility/all-active') && request.method() === 'PUT') {
        const body = request.postDataJSON();
        writes.push(body);
        digitalVisible = body.visible;
        await new Promise((resolveDelay) => setTimeout(resolveDelay, 250));
        return route.fulfill({ json: { product_id: product.id, scope: 'all_active', affected_branch_count: 2 } });
      }
      if (path === '/catalog/products') return route.fulfill({ json: [product] });
      if (path === '/categories') return route.fulfill({ json: [] });
      return route.fulfill({ json: [] });
    });

    await page.goto(`${adminUrl}/catalog`, { waitUntil: 'domcontentloaded' });
    const availabilityCard = page.getByRole('button', { name: 'Acceder a Disponibilidad' });
    await availabilityCard.waitFor();
    await availabilityCard.click();
    await page.getByRole('heading', { name: 'Disponibilidad de productos' }).waitFor();

    const scope = page.getByLabel('Sucursal para disponibilidad');
    assert.equal(await scope.inputValue(), 'all-active');
    assert.equal(await scope.getByRole('option', { name: 'Todas las sucursales' }).count(), 1);
    await page.getByText('AGUA DE FRESA LIMÓN CHICA', { exact: true }).waitFor();
    const card = page.locator('.availability-product-card');
    const borderRadius = Number.parseFloat(await card.evaluate((element) => getComputedStyle(element).borderRadius));
    assert.ok(borderRadius >= 16, `Availability cards remain rounded at ${label}`);

    page.once('dialog', async (dialog) => dialog.accept());
    const visibility = page.getByLabel('Mostrar AGUA DE FRESA LIMÓN CHICA en menú digital en todas las sucursales actuales');
    await visibility.locator('xpath=..').click();
    await page.getByText('0 de 2 en menú digital', { exact: true }).waitFor();
    assert.deepEqual(writes, [{ visible: false }]);
    await page.getByText('El producto quedó oculto del menú digital; seguirá disponible en el POS.', { exact: true }).waitFor();

    await page.goto(`${adminUrl}/products`, { waitUntil: 'domcontentloaded' });
    assert.equal(await page.locator('.availability-workspace').count(), 0, 'Products no longer embeds availability');
    assert.deepEqual(errors, []);
    await page.goto(`${adminUrl}/availability`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: 'Disponibilidad de productos' }).waitFor();
    await page.screenshot({ path: `${output}/availability-${label}.png`, fullPage: true });
    console.log(`Availability ${label} passed`);
    await page.close();
  }
  console.log('Availability hub, corporate default, optimistic visibility and responsive cards passed.');
} finally {
  await browser.close();
}
