// RECIPES-UX-001 synthetic browser fixture; no production data or services.
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const playwrightImport = process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright';
const { chromium } = await import(playwrightImport);
const baseUrl = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
const screenshotDir = process.env.RECIPE_PRODUCT_SCREENSHOT_DIR || join(process.cwd(), 'output', 'playwright');
const chromePath = process.env.ADMINRETRO_CHROME_PATH;
const branchId = '018f6f73-2d0a-74f0-8f1c-000000000003';
const productId = '018f6f73-2d0a-74f0-8f1c-000000000111';
const itemId = '018f6f73-2d0a-74f0-8f1c-000000000222';
const unitId = 'unit-piece';

const initialRecipe = () => ({
  id: 'recipe-qa',
  version: 3,
  source: 'branch',
  yield_quantity: '1',
  yield_unit_id: unitId,
  components: [{
    item_id: itemId,
    unit_id: unitId,
    net_quantity: '1',
    waste_rate: '0.125',
    gross_quantity: '1.142857',
  }],
  latest_cost: { total_cost: '4.000000', cost_per_yield_unit: '4.000000' },
});

async function mockApi(page, state) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/v1', '');
    state.paths.push(`${route.request().method()} ${path}${url.search}`);
    if (path === '/catalog/products') {
      return route.fulfill({ json: [{
        id: productId,
        name: 'Producto de prueba',
        sku: '1001',
        category_id: 'category-qa',
        category_name: 'PRUEBAS',
        station: 'kitchen',
        price_cents: 1000,
        status: 'active',
        catalog_scope: 'organization',
        updated_at: '2026-09-24T12:00:00Z',
      }] });
    }
    if (path === '/categories') {
      return route.fulfill({ json: [{ id: 'category-qa', name: 'PRUEBAS', status: 'active' }] });
    }
    if (path === '/categories/category-qa/selection-group') {
      return route.fulfill({ json: { category_id: 'category-qa', group: null, values: [], products: [] } });
    }
    if (path === `/catalog/product-configurations/${productId}` && route.request().method() === 'PUT') {
      state.productSave = { body: route.request().postDataJSON(), idempotencyKey: route.request().headers()['idempotency-key'] };
      return route.fulfill({ json: {
        id: productId,
        name: 'PRODUCTO DE PRUEBA',
        sku: '1001',
        category_id: 'category-qa',
        category_name: 'PRUEBAS',
        price_cents: 1000,
        station: 'kitchen',
        status: 'active',
        image_url: null,
        subgroup: null,
        updated_at: '2026-09-24T13:00:00+00:00',
      } });
    }
    if (path === '/recipes/workspace') {
      assert.equal(url.searchParams.get('branch_id'), branchId);
      return route.fulfill({ json: {
        selected_branch_id: branchId,
        corporate_allowed: false,
        scopes: { branches: [{ id: branchId, name: 'Sucursal QA', code: 'QA' }] },
        products: [{ id: productId, name: 'Producto de prueba', sku: '1001', has_recipe: true }],
        items: [{ id: itemId, name: 'Harina de prueba', unit_id: unitId, unit_code: 'PZA', last_unit_cost: 3.5 }],
      } });
    }
    if (path === `/products/${productId}/recipe`) {
      if (route.request().method() === 'PUT') {
        if (state.conflictOnSave) {
          return route.fulfill({
            status: 409,
            json: { detail: { code: 'recipe_version_conflict', message: 'Active recipe changed' } },
          });
        }
        const payload = route.request().postDataJSON();
        state.save = { body: payload, idempotencyKey: route.request().headers()['idempotency-key'] };
        state.recipe = {
          ...initialRecipe(),
          id: 'recipe-saved',
          version: 4,
          yield_quantity: payload.yield_quantity,
          yield_unit_id: payload.yield_unit_id,
          components: payload.components.map((component) => ({ ...component, gross_quantity: '1.250000' })),
          latest_cost: { total_cost: '5.000000', cost_per_yield_unit: '5.000000' },
        };
      } else if (state.recipeReadFails) {
        return route.fulfill({
          status: 503,
          json: { detail: { code: 'recipe_read_unavailable', message: 'Recipe read unavailable' } },
        });
      }
      return route.fulfill({ json: state.recipe });
    }
    return route.fulfill({ json: [] });
  });
}

async function verifyViewport(browser, width) {
  const context = await browser.newContext({ viewport: { width, height: width === 390 ? 844 : 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(20_000);
  const state = {
    recipe: initialRecipe(),
    save: null,
    productSave: null,
    paths: [],
    recipeReadFails: width === 1440,
    conflictOnSave: false,
  };
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.addInitScript(({ userBranch }) => {
    localStorage.setItem('auth_token', 'recipe-ux-synthetic-token');
    localStorage.setItem('admin_branch_id', userBranch);
    localStorage.setItem('user', JSON.stringify({
      id: 'recipe-ux-user',
      display_name: 'Usuario QA',
      assigned_branch_id: userBranch,
      roles: ['Administrador'],
      permissions: ['catalog.manage', 'recipes.manage'],
    }));
  }, { userBranch: branchId });
  await mockApi(page, state);
  await page.goto(`${baseUrl}/products`, { waitUntil: 'domcontentloaded' });
  try {
    await page.locator('.productos-window-title').getByText('Productos', { exact: true }).waitFor();
  } catch (error) {
    mkdirSync(screenshotDir, { recursive: true });
    await page.screenshot({ path: join(screenshotDir, `recipe-product-flow-error-${width}.png`), fullPage: true });
    console.error(`Recipe flow failed to load at ${width}px`, { body: await page.locator('body').innerText(), pageErrors });
    throw error;
  }
  assert.equal(await page.locator('.vite-error-overlay').count(), 0, 'Vite must not show an error overlay');
  assert.ok((await page.locator('body').innerText()).trim().length > 100, 'Products must render meaningful content');

  await page.getByRole('tab', { name: 'Receta', exact: true }).click();
  if (width === 1440) {
    await page.getByText('La edición permanece bloqueada hasta recuperar la versión vigente.').waitFor();
    assert.equal(await page.getByRole('button', { name: 'Configurar receta de este producto' }).isDisabled(), true);
    state.recipeReadFails = false;
    await page.getByRole('button', { name: 'Reintentar lectura', exact: true }).click();
    await page.getByRole('button', { name: 'Editar receta de este producto' }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Editar receta de este producto' }).isEnabled(), true);
  }
  await page.getByRole('button', { name: 'Editar receta de este producto' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByText('Receta: Producto de prueba').waitFor();
  const wasteInput = dialog.locator('input[aria-label^="Merma porcentual"]');
  try {
    await wasteInput.waitFor();
    assert.equal(await wasteInput.getAttribute('aria-label'), 'Merma porcentual de Harina de prueba');
    assert.equal(await wasteInput.inputValue(), '12.5');
  } catch (error) {
    console.error(`Recipe dialog did not load components at ${width}px`, { dialog: await dialog.innerText(), paths: state.paths });
    throw error;
  }
  assert.match(await dialog.innerText(), /1\.142857 PZA/);
  assert.match(await dialog.innerText(), /Costo confirmado por backend/);
  assert.match(await dialog.innerText(), /Precio de venta actual: \$10\.00 MXN/);

  await page.getByPlaceholder('Filtrar insumos por nombre o unidad').fill('harina');
  assert.equal(await dialog.locator('select[aria-label="Insumo 1"] option').count(), 2);
  mkdirSync(screenshotDir, { recursive: true });
  await page.screenshot({ path: join(screenshotDir, `recipe-product-flow-${width}.png`), fullPage: true });
  assert.equal(await page.locator('html').evaluate((element) => element.scrollWidth <= element.clientWidth), true, `document overflows at ${width}px`);

  if (width === 390) {
    await wasteInput.fill('-1');
    await page.getByRole('button', { name: 'Guardar Receta' }).click();
    await dialog.getByText('La merma debe ser un porcentaje entre 0 y 99.9999. Puedes usar punto o coma decimal.').waitFor();
    assert.equal(state.save, null, 'an invalid visible percentage must never reach the API');
  }
  await wasteInput.fill('20');
  await page.getByRole('button', { name: 'Guardar Receta' }).click();
  await page.getByText('Receta guardada y versionada. Puedes revisar el resultado o volver al producto.').waitFor();
  await page.waitForTimeout(900);
  assert.equal(await dialog.isVisible(), true, 'successful save must not auto-close the editor');
  assert.equal(state.save.body.components[0].waste_rate, '0.2');
  assert.equal('gross_quantity' in state.save.body.components[0], false);
  assert.equal(state.save.body.expected_active_recipe_id, 'recipe-qa');
  assert.equal(state.save.body.branch_id, branchId);
  assert.ok(state.save.idempotencyKey);

  await page.getByRole('button', { name: 'Volver al producto' }).click();
  await dialog.waitFor({ state: 'detached' });
  await page.getByText('Receta del producto').waitFor();
  if (width === 1440) {
    await page.getByRole('button', { name: 'Editar', exact: true }).click();
    await page.getByRole('button', { name: 'Guardar y configurar receta', exact: true }).click();
    const continuedDialog = page.getByRole('dialog');
    await continuedDialog.getByText('Receta: PRODUCTO DE PRUEBA').waitFor();
    assert.equal(state.productSave.body.expected_updated_at, '2026-09-24T12:00:00Z');
    assert.ok(state.productSave.idempotencyKey);
    state.conflictOnSave = true;
    const continuedWasteInput = continuedDialog.locator('input[aria-label^="Merma porcentual"]');
    await continuedWasteInput.fill('25');
    await continuedDialog.getByRole('button', { name: 'Guardar Receta' }).click();
    await continuedDialog.getByText('La receta cambió en otra sesión. Cierra y vuelve a abrir para ver la última versión.').waitFor();
    assert.equal(await continuedDialog.getByRole('button', { name: 'Guardar Receta' }).isDisabled(), true);
    assert.equal(await continuedWasteInput.inputValue(), '25', 'the conflicting draft must remain visible');
    await page.getByRole('button', { name: 'Volver al producto' }).click();
  }
  assert.deepEqual(pageErrors, []);
  await context.close();
}

const browser = await chromium.launch({ headless: true, ...(chromePath ? { executablePath: chromePath } : {}) });
try {
  for (const width of [390, 768, 1440]) await verifyViewport(browser, width);
  console.log('Recipe product flow browser QA passed');
} finally {
  await browser.close();
}
