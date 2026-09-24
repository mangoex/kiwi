// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-compound-product-browser-v1
import assert from 'node:assert/strict';

const playwrightImport = process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright';
const { chromium } = await import(playwrightImport);
const baseUrl = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
const screenshotPath = process.env.COMPOUND_PRODUCT_SCREENSHOT;
const branchId = '018f6f73-2d0a-74f0-8f1c-000000000003';
const parent = {
  id: '018f6f73-2d0a-74f0-8f1c-000000000111',
  name: 'Producto compuesto QA',
  sku: 'COMP-QA',
  category_name: 'Pruebas',
  station: 'kitchen',
  price_cents: 1000,
  status: 'active',
  catalog_scope: 'organization',
};
const component = {
  id: '018f6f73-2d0a-74f0-8f1c-000000000112',
  name: 'Complemento simple QA',
  sku: 'SIMPLE-QA',
  category_name: 'Pruebas',
  station: 'kitchen',
  price_cents: 500,
  status: 'active',
  catalog_scope: 'organization',
};
const state = { saved: null };

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
  await page.addInitScript(({ branch }) => {
    localStorage.setItem('auth_token', 'synthetic-compound-product-token');
    localStorage.setItem('admin_branch_id', branch);
    localStorage.setItem('user', JSON.stringify({
      id: 'compound-product-qa',
      display_name: 'Administradora QA',
      is_superadmin: true,
      assigned_branch_id: branch,
      roles: ['Administrador'],
      permissions: ['catalog.manage', 'recipes.manage'],
    }));
  }, { branch: branchId });
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/v1', '');
    if (path === '/branches') {
      return route.fulfill({ json: [{ id: branchId, name: 'Sucursal QA', status: 'active' }] });
    }
    if (path === '/catalog/products') return route.fulfill({ json: [parent, component] });
    if (path === `/products/${parent.id}/modifier-configuration`) {
      if (route.request().method() === 'PUT') {
        state.saved = {
          body: route.request().postDataJSON(),
          idempotencyKey: route.request().headers()['idempotency-key'],
        };
        const group = state.saved.body.groups[0];
        return route.fulfill({ json: {
          version: 1,
          result: 'applied',
          groups: [{
            ...group,
            id: 'group-qa',
            options: group.options.map((option, index) => ({
              ...option,
              id: `option-qa-${index + 1}`,
            })),
          }],
        } });
      }
      return route.fulfill({ json: {
        product: { id: parent.id, name: parent.name, sku: parent.sku, station: parent.station },
        expected_version: 0,
        groups: [],
        component_candidates: [{ id: component.id, name: component.name, sku: component.sku }],
      } });
    }
    return route.fulfill({ json: [] });
  });

  console.log('Opening compound-product Admin fixture');
  await page.goto(`${baseUrl}/products`, { waitUntil: 'domcontentloaded' });
  console.log(`Compound-product fixture URL: ${page.url()}`);
  console.log(`Compound-product fixture text: ${(await page.locator('body').innerText()).slice(0, 240)}`);
  await page.locator('.productos-window-container').waitFor();
  console.log('Products workspace loaded');
  await page.getByLabel('Páginas de configuración').getByRole('button').last().click();
  await page.getByRole('tab', { name: 'Producto compuesto' }).click();
  await page.getByRole('heading', { name: 'Grupos y productos seleccionables' }).waitFor();
  console.log('Compound-product tab loaded');
  await page.getByRole('button', { name: 'Agregar grupo de selección' }).focus();
  await page.keyboard.press('Enter');
  await page.getByLabel('Nombre del grupo').fill('Acompañamientos');
  await page.getByRole('button', { name: 'Agregar producto u opción' }).click();
  const editor = page.getByRole('region', { name: /^Producto compuesto/ });
  await editor.getByRole('combobox').nth(1).selectOption(component.id);
  await page.getByLabel('Precio extra MXN').fill('12.50');
  const save = page.getByRole('button', { name: 'Guardar configuración' });
  assert.equal(await save.isDisabled(), false);
  await save.click();
  await page.getByText(/Configuración guardada como versión 1/).waitFor();
  console.log('Compound-product draft saved');

  assert.equal(state.saved.body.expected_version, 0);
  assert.equal(state.saved.body.groups[0].included_selections, 1);
  assert.equal(state.saved.body.groups[0].options[0].component_product_id, component.id);
  assert.equal(state.saved.body.groups[0].options[0].price_delta_cents, 1250);
  assert.ok(state.saved.idempotencyKey);
  assert.equal(
    await page.locator('html').evaluate((element) => element.scrollWidth <= element.clientWidth),
    true,
    'compound-product editor must not overflow the 1440px viewport',
  );
  assert.deepEqual(errors, []);
  if (screenshotPath) await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log('Compound-product Admin browser QA passed');
} finally {
  await browser.close();
}
