// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-shared-modifier-browser-v1
import assert from 'node:assert/strict';
import { corporateAdminSession } from '../fixtures/admin_session_fixture.mjs';

const { chromium } = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const baseUrl = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
const screenshotPath = process.env.SHARED_MODIFIER_SCREENSHOT;
const creationScreenshotPath = process.env.SHARED_MODIFIER_CREATION_SCREENSHOT;
const editorScreenshotPath = process.env.SHARED_MODIFIER_EDITOR_SCREENSHOT;
const branchId = '018f6f73-2d0a-74f0-8f1c-000000000003';
const category = { id: 'category-salads', name: 'Ensaladas', status: 'active', display_order: 1 };
const burger = {
  id: 'product-salad-1', name: 'Ensalada Kiwi', sku: '1001', category_id: category.id,
  station: 'kitchen', status: 'active', catalog_scope: 'organization',
};
const fries = {
  id: 'product-salad-2', name: 'Ensalada César', sku: '1002', category_id: category.id,
  station: 'kitchen', status: 'active', catalog_scope: 'organization',
};
const user = { id: 'shared-modifier-qa', display_name: 'Administradora QA', permissions: ['catalog.manage'] };
const inventoryItem = { id: 'inventory-ranch', name: 'Aderezo ranch', sku: 'INS-001', unit_code: 'LITRO' };
const state = {
  version: 1,
  productIds: [burger.id],
  scopeRequests: [],
  createRequests: [],
  createdSet: null,
  configurationRequest: null,
};
const group = {
  id: 'shared-group-1', name: 'Tipo de aderezo', is_required: false,
  minimum_selections: 0, maximum_selections: 1, included_selections: 0,
  station: 'kitchen', options: [{
    id: 'shared-option-1', name: 'Ranch', effect_type: 'add',
    price_delta_cents: 500, affected_item_id: inventoryItem.id, replacement_item_id: null,
    remove_quantity: '0', add_quantity: '0.025000', inventory_effect: false,
    kitchen_text: 'AGREGAR RANCH', station: 'kitchen',
  }],
};
const products = [burger, fries];
const setView = () => ({
  id: 'shared-set-1', name: 'Aderezos', version: state.version, station: 'kitchen',
  group_count: 1, products: products.filter((product) => state.productIds.includes(product.id)),
});

const browser = await chromium.launch({
  headless: true,
  ...(process.env.ADMINRETRO_CHROME_PATH
    ? { executablePath: process.env.ADMINRETRO_CHROME_PATH }
    : {}),
});
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.stack || error.message));
  await page.addInitScript(({ branch, actor }) => {
    localStorage.setItem('auth_token', 'synthetic-shared-modifier-token');
    localStorage.setItem('admin_branch_id', branch);
    localStorage.setItem('user', JSON.stringify(actor));
  }, { branch: branchId, actor: user });
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/v1', '');
    if (path === '/auth/session') return route.fulfill({ json: corporateAdminSession(user, branchId) });
    if (path === '/auth/login') return route.fulfill({ json: { token: 'synthetic-shared-modifier-renewed', user } });
    if (path === '/catalog/products') return route.fulfill({ json: products });
    if (path === '/categories') return route.fulfill({ json: [category] });
    if (path === '/catalog/modifier-sets') {
      if (route.request().method() === 'POST') {
        state.createRequests.push({
          body: route.request().postDataJSON(),
          key: route.request().headers()['idempotency-key'],
        });
        if (state.createRequests.length === 1) {
          return route.fulfill({ status: 401, json: { detail: { code: 'token_invalid', message: 'Sesión vencida' } } });
        }
        state.createdSet = {
          id: 'shared-set-created', name: state.createRequests[1].body.name,
          version: 1, station: 'kitchen', group_count: 0,
          products: products.filter((product) => state.createRequests[1].body.product_ids.includes(product.id)),
        };
        return route.fulfill({ json: { ...state.createdSet, result: 'applied' } });
      }
      return route.fulfill({ json: [setView(), ...(state.createdSet ? [state.createdSet] : [])] });
    }
    if (path === '/catalog/modifier-sets/shared-set-1/products') {
      const scopeRequest = {
        body: route.request().postDataJSON(),
        key: route.request().headers()['idempotency-key'],
      };
      state.scopeRequests.push(scopeRequest);
      if (state.scopeRequests.length === 1) {
        return route.fulfill({ status: 401, json: { detail: { code: 'token_invalid', message: 'Sesión vencida' } } });
      }
      state.productIds = scopeRequest.body.product_ids;
      state.version += 1;
      return route.fulfill({ json: { id: 'shared-set-1', version: state.version, products: setView().products, result: 'applied' } });
    }
    if (path === '/catalog/modifier-sets/shared-set-1/configuration') {
      if (route.request().method() === 'PUT') {
        state.configurationRequest = {
          body: route.request().postDataJSON(),
          key: route.request().headers()['idempotency-key'],
        };
        state.version += 1;
        group.options[0].price_delta_cents = state.configurationRequest.body.groups[0].options[0].price_delta_cents;
        return route.fulfill({ json: { version: state.version, groups: state.configurationRequest.body.groups, result: 'applied' } });
      }
      return route.fulfill({ json: {
        product: { id: 'shared-set-1', name: 'Aderezos', sku: 'COMPARTIDO', station: 'kitchen' },
        expected_version: state.version,
        groups: [group],
        component_candidates: [],
        inventory_candidates: [inventoryItem],
        products: setView().products,
      } });
    }
    if (path === '/catalog/modifier-sets/shared-set-created/configuration') {
      return route.fulfill({ json: {
        product: { id: 'shared-set-created', name: state.createdSet.name, sku: 'COMPARTIDO', station: 'kitchen' },
        expected_version: 1,
        groups: [],
        component_candidates: [],
        inventory_candidates: [],
        products: state.createdSet.products,
      } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto(`${baseUrl}/modifiers`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Modificadores', exact: true }).waitFor();
  await page.getByRole('button', { name: /Ensaladas/ }).click();
  const categoryCheckbox = page.getByRole('checkbox', { name: 'Seleccionar productos de Ensaladas' });
  assert.equal(await categoryCheckbox.getAttribute('aria-checked'), 'mixed');
  await page.getByRole('checkbox', { name: /Ensalada César/ }).check();
  await page.getByRole('button', { name: 'Guardar productos' }).click();
  await page.waitForURL(/\/admin\/login/);
  await page.getByLabel('Correo electrónico').fill('modifier-qa@example.invalid');
  await page.getByLabel('Contraseña').fill('synthetic-browser-input');
  await page.getByRole('button', { name: 'Iniciar Sesión' }).click();
  await page.waitForURL(/\/admin\/modifiers$/);
  await page.getByText(/Recuperamos una operación pendiente/).waitFor();
  await page.getByRole('button', { name: 'Guardar productos' }).click();
  await page.getByText(/Productos relacionados actualizados/).waitFor();
  assert.deepEqual(new Set(state.scopeRequests[1].body.product_ids), new Set([burger.id, fries.id]));
  assert.equal(state.scopeRequests[1].body.expected_version, 1);
  assert.ok(state.scopeRequests[1].key);
  assert.equal(state.scopeRequests[0].key, state.scopeRequests[1].key);
  assert.deepEqual(state.scopeRequests[0].body, state.scopeRequests[1].body);

  const editor = page.getByRole('region', { name: /Modificadores compartidos Aderezos/ });
  await editor.getByLabel('Precio extra MXN').fill('7.50');
  const typeOptions = await editor.getByLabel('Tipo').locator('option').allTextContents();
  assert.equal(typeOptions.some((label) => label.includes('Producto componente')), false);
  assert.equal(await editor.getByLabel('Insumo', { exact: true }).inputValue(), inventoryItem.id);
  const quantity = editor.getByLabel('Cantidad a agregar');
  await quantity.fill('1000000000000');
  assert.equal(await editor.getByRole('button', { name: 'Guardar configuración' }).isDisabled(), true);
  await quantity.fill('-0.050000');
  assert.equal(await editor.getByRole('button', { name: 'Guardar configuración' }).isDisabled(), true);
  await quantity.fill('0.050000');
  const modifierGroup = editor.locator('article.modifier-group-card').first();
  await modifierGroup.getByRole('checkbox', { name: 'Grupo obligatorio' }).check();
  assert.equal(await modifierGroup.getByLabel('Mínimo').inputValue(), '1');
  await modifierGroup.getByLabel('Mínimo').fill('0');
  assert.equal(await modifierGroup.getByRole('checkbox', { name: 'Grupo obligatorio' }).isChecked(), false);
  await editor.getByRole('button', { name: 'Guardar configuración' }).click();
  await page.getByText(/Configuración guardada como versión 3/).waitFor();
  assert.equal(state.configurationRequest.body.expected_version, 2);
  assert.equal(state.configurationRequest.body.groups[0].options[0].price_delta_cents, 750);
  assert.equal(state.configurationRequest.body.groups[0].options[0].affected_item_id, inventoryItem.id);
  assert.equal(state.configurationRequest.body.groups[0].options[0].add_quantity, '0.050000');
  assert.equal(state.configurationRequest.body.groups[0].options[0].inventory_effect, false);
  assert.equal(state.configurationRequest.body.groups[0].options.some((option) => option.effect_type === 'product_component'), false);
  assert.ok(state.configurationRequest.key);
  if (editorScreenshotPath) {
    await page.locator('.shared-modifier-workspace').screenshot({ path: editorScreenshotPath });
  }

  await page.getByRole('button', { name: 'Nuevo set' }).click();
  const createPanel = page.getByRole('region', { name: 'Nueva configuración compartida' });
  const createButton = createPanel.getByRole('button', { name: 'Crear y configurar' });
  assert.equal(await createButton.isDisabled(), false);
  await createButton.click();
  await createPanel.getByText('Escribe un nombre para identificar la configuración.').waitFor();
  await createPanel.getByPlaceholder('Ej. Aderezos para ensaladas').fill('Toppings');
  await createPanel.getByRole('checkbox', { name: 'Seleccionar productos de Ensaladas' }).check();
  assert.equal(await createButton.isDisabled(), false);
  assert.equal(await createButton.getAttribute('disabled'), null);
  if (creationScreenshotPath) await page.screenshot({ path: creationScreenshotPath, fullPage: true });
  await createButton.click();
  await page.waitForURL(/\/admin\/login/);
  await page.getByLabel('Correo electrónico').fill('modifier-qa@example.invalid');
  await page.getByLabel('Contraseña').fill('synthetic-browser-input');
  await page.getByRole('button', { name: 'Iniciar Sesión' }).click();
  await page.waitForURL(/\/admin\/modifiers$/);
  await page.getByText(/Recuperamos una operación pendiente/).waitFor();
  const recoveredCreatePanel = page.getByRole('region', { name: 'Nueva configuración compartida' });
  await recoveredCreatePanel.getByRole('button', { name: 'Crear y configurar' }).click();
  await page.getByText(/Configuración compartida creada/).waitFor();
  assert.equal(state.createRequests[0].key, state.createRequests[1].key);
  assert.deepEqual(state.createRequests[0].body, state.createRequests[1].body);

  await page.setViewportSize({ width: 760, height: 900 });
  assert.equal(await page.locator('body').evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  if (screenshotPath) await page.screenshot({ path: screenshotPath, fullPage: true });
  assert.deepEqual(errors, []);
  console.log('shared modifier workspace browser checks passed');
} finally {
  await browser.close();
}
