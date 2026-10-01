// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-admin-session-browser-v1
import assert from 'node:assert/strict';
import { mkdirSync, readFileSync } from 'node:fs';

const { chromium } = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const baseUrl = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
const browser = await chromium.launch({ headless: true, ...(process.env.ADMINRETRO_CHROME_PATH ? { executablePath: process.env.ADMINRETRO_CHROME_PATH } : {}) });
mkdirSync('output/playwright', { recursive: true });
const branch = '018f6f73-2d0a-74f0-8f1c-000000000003';
const user = { id: 'session-qa', display_name: 'Session QA', permissions: ['catalog.manage', 'dashboard.read', 'admin.manage'], roles: ['Administrador corporativo'], is_superadmin: true };
try {
  for (const width of (process.env.ADMIN_SESSION_VIEWPORTS || '390,1440').split(',').map(Number)) {
    const page = await browser.newPage({ viewport: { width, height: 1000 } });
    page.setDefaultTimeout(7000);
    const invalidCalls = [];
    await page.route('**/api/v1/**', async route => {
      const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
      if (path === '/auth/login') return route.fulfill({ json: { token: 'session-qa-renewed', user } });
      if (path === '/branches') return route.fulfill({ json: [{ id: branch, name: 'Sucursal QA', status: 'active' }] });
      if (['/catalog/products', '/categories'].includes(path) && route.request().headers().authorization !== 'Bearer session-qa-renewed') {
        invalidCalls.push(path);
        return route.fulfill({ status: 401, json: { detail: { code: 'token_invalid', message: 'Invalid or expired' } } });
      }
      if (path === '/catalog/products') return route.fulfill({ json: [{ id: 'session-product', name: 'PRODUCTO RECUPERADO', sku: '9001', category_name: 'QA', station: 'kitchen', price_cents: 1000, status: 'active', catalog_scope: 'organization' }] });
      if (path === '/dashboard/overview') return route.fulfill({ json: { total_revenue_cents: 0, total_orders: 0, average_ticket_cents: 0, total_products: 1, order_types: {}, recent_transactions: [], activity_chart: [], recent_notifications: [], popular_categories: [] } });
      return route.fulfill({ json: [] });
    });
    await page.addInitScript(({ user, branch }) => {
      if (!localStorage.getItem('session-qa-initialized')) {
        localStorage.setItem('session-qa-initialized', 'yes');
        localStorage.setItem('auth_token', 'session-qa-rejected');
        localStorage.setItem('user', JSON.stringify(user));
        localStorage.setItem('admin_branch_id', branch);
      }
    }, { user, branch });
    await page.goto(baseUrl + '/products');
    await page.waitForURL(/\/admin\/login/);
    await page.getByText('Tu sesión venció o fue invalidada. Inicia sesión de nuevo.').waitFor();
    assert.deepEqual(await page.evaluate(() => [localStorage.getItem('auth_token'), sessionStorage.getItem('auth_token'), localStorage.getItem('user')]), [null, null, null]);
    const count = invalidCalls.length;
    await page.waitForTimeout(1200);
    assert.equal(invalidCalls.length, count, 'Protected 401 queries must stop after login redirect');
    await page.getByLabel('Correo electrónico').fill('session-qa@example.invalid');
    await page.getByLabel('Contraseña').fill('synthetic-browser-input');
    await page.getByRole('button', { name: 'Iniciar Sesión' }).click();
    await page.waitForURL(/\/admin\/?$/);
    const labels = await page.locator('#admin-sidebar-navigation button').evaluateAll(buttons => buttons.map(button => button.getAttribute('aria-label')));
    assert.equal(labels[0], 'Catálogo y Menú');
    assert.deepEqual(labels.slice(-3), ['Administración', 'Agentes', 'Punto de Venta POS']);
    assert.equal(labels.includes('Panel Principal'), false);
    await page.goto(baseUrl + '/products');
    await page.getByText('PRODUCTO RECUPERADO', { exact: true }).first().waitFor();
    await page.getByRole('button', { name: 'Contraer menú lateral' }).click();
    assert.equal(await page.locator('.admin-nav-item[aria-label="Agentes"]').count(), 1);
    if (width < 768) await page.getByRole('button', { name: 'Expandir menú lateral' }).click();
    await page.getByRole('button', { name: 'Agentes', exact: true }).waitFor();
    await page.screenshot({ path: 'output/playwright/admin-session-menu-' + width + '.png', fullPage: true });
    await page.getByRole('button', { name: 'Agentes', exact: true }).click();
    await page.waitForURL(/\/admin\/?$/);
    assert.equal(await page.evaluate(() => localStorage.getItem('auth_token')), 'session-qa-renewed');
    await page.close();
    console.log(`${width}px: 401/login/catalog recovery and accessible menu order passed`);
  }
  if (process.env.ADMIN_SESSION_REAL_MANIFEST) {
    const manifest = JSON.parse(readFileSync(process.env.ADMIN_SESSION_REAL_MANIFEST, 'utf8'));
    assert.equal(manifest.synthetic_only, true);
    assert.equal(new URL(baseUrl).hostname, '127.0.0.1');
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    await page.goto(baseUrl + '/login');
    await page.evaluate(branch => {
      localStorage.setItem('auth_token', 'invalid-synthetic-session');
      localStorage.setItem('user', JSON.stringify({ id: 'old-synthetic-profile' }));
      localStorage.setItem('admin_branch_id', branch);
    }, manifest.branch_id);
    await page.goto(baseUrl + '/products');
    await page.waitForURL(/\/admin\/login/);
    await page.getByRole('status').getByText('Tu sesión venció o fue invalidada. Inicia sesión de nuevo.').waitFor();
    await page.getByLabel('Correo electrónico').fill(manifest.login.email);
    await page.getByLabel('Contraseña').fill(manifest.login.password);
    await page.getByRole('button', { name: 'Iniciar Sesión' }).click();
    await page.waitForURL(/\/admin\/?$/);
    const productsResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/catalog/products' && response.status() === 200);
    await page.getByRole('button', { name: 'Catálogo y Menú', exact: true }).click();
    await page.getByRole('button', { name: 'Acceder a Productos', exact: true }).click();
    const products = await (await productsResponse).json();
    const product = products.find(item => manifest.product_ids.includes(item.id));
    assert.ok(product, 'Real authenticated catalog must contain the seeded product');
    await page.getByText(product.name, { exact: true }).first().waitFor();
    await page.close();
    console.log('Real API: invalid credential, reauthentication and products 200 passed');
  }
} finally {
  await browser.close();
}
