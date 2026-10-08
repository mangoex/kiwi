// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-compound-product-browser-v1
import assert from 'node:assert/strict';
import { corporateAdminSession } from '../fixtures/admin_session_fixture.mjs';

const playwrightImport = process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright';
const { chromium } = await import(playwrightImport);
const baseUrl = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
const screenshotPath = process.env.COMPOUND_PRODUCT_SCREENSHOT;
const branchId = '018f6f73-2d0a-74f0-8f1c-000000000003';
const product = {
  id: '018f6f73-2d0a-74f0-8f1c-000000000111',
  name: 'Producto de prueba',
  sku: '1001',
  category_id: '018f6f73-2d0a-74f0-8f1c-000000000211',
  category_name: 'PRUEBAS',
  station: 'kitchen',
  price_cents: 1000,
  status: 'active',
  catalog_scope: 'organization',
  updated_at: '2026-10-07T00:00:00Z',
};
const category = {
  id: product.category_id,
  name: product.category_name,
  classification_code: 'food',
  status: 'active',
};
const adminUser = {
  id: 'compound-product-qa',
  display_name: 'Administradora QA',
  is_superadmin: true,
  assigned_branch_id: branchId,
  roles: ['Administrador'],
  permissions: ['catalog.manage', 'recipes.manage'],
};

const modifierRequests = [];
const browser = await chromium.launch({
  headless: true,
  ...(process.env.ADMINRETRO_CHROME_PATH
    ? { executablePath: process.env.ADMINRETRO_CHROME_PATH }
    : {}),
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(15_000);
  page.setDefaultNavigationTimeout(15_000);
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.addInitScript(({ branch, user }) => {
    localStorage.setItem('auth_token', 'synthetic-product-token');
    localStorage.setItem('admin_branch_id', branch);
    localStorage.setItem('user', JSON.stringify(user));
  }, { branch: branchId, user: adminUser });
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/v1', '');
    if (path.includes('modifier')) modifierRequests.push(path);
    if (path === '/auth/session') return route.fulfill({ json: corporateAdminSession(adminUser, branchId) });
    if (path === '/branches') return route.fulfill({ json: [{ id: branchId, name: 'Sucursal QA', status: 'active' }] });
    if (path === '/catalog/products') return route.fulfill({ json: [product] });
    if (path === '/categories') return route.fulfill({ json: [category] });
    return route.fulfill({ json: [] });
  });

  await page.goto(`${baseUrl}/products`, { waitUntil: 'domcontentloaded' });
  await page.locator('.productos-window-container').waitFor();
  await page.getByRole('cell', { name: product.name, exact: true }).waitFor();
  assert.equal(await page.getByRole('tab', { name: 'Modificadores / Producto compuesto' }).count(), 0);
  assert.equal(await page.getByText('Grupos y productos seleccionables', { exact: true }).count(), 0);
  await page.getByRole('tab', { name: 'Principal / Varios' }).press('End');
  assert.equal(
    await page.getByRole('tab', { name: 'Combo / Paquete fijo' }).getAttribute('aria-selected'),
    'true',
  );
  assert.deepEqual(modifierRequests, [], 'Productos no debe consultar APIs de modificadores');
  assert.deepEqual(errors, []);
  if (screenshotPath) await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log('Product modifier submenu removal browser QA passed');
} finally {
  await browser.close();
}
