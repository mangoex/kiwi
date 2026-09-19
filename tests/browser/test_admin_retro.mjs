// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-admin-retro-browser-v1
import assert from 'node:assert/strict';
import { appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

const playwrightImport = process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright';
const { chromium } = await import(playwrightImport);
const baseUrl = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
const branchId = '018f6f73-2d0a-74f0-8f1c-000000000003';
const otherBranchId = '018f6f73-2d0a-74f0-8f1c-000000000004';
const screenshotDir = process.env.ADMINRETRO_SCREENSHOT_DIR || join(process.cwd(), 'output', 'playwright');
const requestedViewports = (process.env.ADMINRETRO_VIEWPORTS || '390,768,1440').split(',').map((value) => Number(value.trim()));
const traceFile = process.env.ADMINRETRO_TRACE_FILE;
const checkpoint = (message) => {
  console.log(message);
  if (traceFile) appendFileSync(traceFile, `${message}\n`);
};

const products = [{
  id: '018f6f73-2d0a-74f0-8f1c-000000000111', name: 'Producto de prueba', sku: 'RETRO-001',
  category_name: 'Pruebas', station: 'kitchen', price_cents: 1000, status: 'active', catalog_scope: 'organization',
}, {
  id: '018f6f73-2d0a-74f0-8f1c-000000000112', name: 'Complemento de prueba', sku: 'RETRO-002',
  category_name: 'Pruebas', station: 'kitchen', price_cents: 500, status: 'active', catalog_scope: 'organization',
}];
const localProducts = [
  { ...products[1], id: 'local-centro', name: 'Local Centro', catalog_scope: 'branch', source_branch_id: branchId },
  { ...products[1], id: 'local-norte', name: 'Local Norte', catalog_scope: 'branch', source_branch_id: otherBranchId },
];

const neutral = (value) => {
  const parts = value.match(/\d+(?:\.\d+)?/g)?.slice(0, 3).map(Number) || [];
  return parts.length === 3 && parts[0] === parts[1] && parts[1] === parts[2];
};

async function mockApi(page, state) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/v1', '');
    if (path === '/branches') return route.fulfill({ json: [{ id: branchId, name: 'Sucursal de prueba', status: 'active' }, { id: otherBranchId, name: 'Norte', status: 'active' }] });
    if (path === '/auth/login') return route.fulfill({ json: { token: 'synthetic-adminretro-token', user: state.user } });
    if (path === '/dashboard/overview') return route.fulfill({ json: { total_revenue_cents: 0, total_orders: 0, average_ticket_cents: 0, total_products: 1, period_from_utc: '2026-09-01T00:00:00Z', period_to_utc: '2026-09-18T00:00:00Z', order_types: { mostrador: 0, para_llevar: 0, domicilio: 0 }, recent_transactions: [], activity_chart: [], recent_notifications: [], popular_categories: [] } });
    if (path === '/catalog/products') {
      assert.equal(url.searchParams.has('branch_id'), false, 'recipe editor must not require the POS catalog permission');
      return route.fulfill({ json: state.checkLocalCandidates ? [...products, ...localProducts] : products });
    }
    if (path === '/inventory/items') {
      if (state.inventory === 'loading') await state.inventoryGate;
      if (state.inventory === 'error') return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: { code: 'synthetic_failure', message: 'Fallo de prueba' } }) });
      return route.fulfill({ json: state.inventory === 'rows' ? [{ id: '018f6f73-2d0a-74f0-8f1c-000000000222', name: 'Harina de prueba', sku: 'INS-001', base_unit_id: 'unit-piece', unit_code: 'PZA', status: 'active' }] : [] });
    }
    if (path === '/inventory/units') return route.fulfill({ json: [{ id: 'unit-piece', name: 'Pieza', code: 'PZA' }] });
    if (path === '/purchase-presentations' || path === '/suppliers' || path === '/warehouses') return route.fulfill({ json: [] });
    if (path === '/recipes/workspace') return route.fulfill({ json: { selected_branch_id: branchId, corporate_allowed: true, scopes: { branches: [{ id: branchId, name: 'Sucursal de prueba', code: 'QA' }] }, products, items: [{ id: '018f6f73-2d0a-74f0-8f1c-000000000222', name: 'Harina de prueba', sku: 'INS-001', unit_id: 'unit-piece', unit_code: 'PZA' }] } });
    if (path === `/products/${products[0].id}/recipe`) return route.fulfill({ json: { id: 'recipe-qa', yield_quantity: '1', yield_unit_id: 'unit-piece', components: [] } });
    if (path === `/products/${products[0].id}/composition`) {
      if (route.request().method() === 'PUT') {
        if (state.comboConflictMode) { state.comboConflictRequest = route.request().postDataJSON(); return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: { code: 'combo_composition_version_conflict', message: 'Combo composition changed' } }) }); }
        state.comboSave = { body: route.request().postDataJSON(), idempotencyKey: route.request().headers()['idempotency-key'] };
        state.comboComposition = { id: 'combo-qa', combo_product_id: products[0].id, branch_id: branchId, version: 1, price_cents: 1000, currency: 'MXN', components: [{ product_id: products[1].id, quantity: '2.000000', name: products[1].name, sku: products[1].sku }] };
        state.comboRefreshError = true;
        return route.fulfill({ json: state.comboComposition });
      }
      if (state.comboRefreshError || state.comboReviewError) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: { code: 'synthetic_composition_refresh_failure', message: 'Lectura diferida no disponible' } }) });
      return route.fulfill({ json: { product: { id: products[0].id, name: products[0].name, sku: products[0].sku, catalog_scope: 'organization', is_combo: Boolean(state.comboComposition) }, branch_id: branchId, expected_version: state.comboComposition?.version || 0, current_composition: state.comboComposition || null, effective_composition: state.comboComposition || null } });
    }
    if (path === '/admin-catalog/category-priorities') {
      if (route.request().method() === 'PUT') state.prioritySave = route.request().postDataJSON();
      return route.fulfill({ json: { version: 4, view_order: [{ id: 'cat-food', name: 'Alimentos', position: 1 }, { id: 'cat-drinks', name: 'Bebidas', position: 2 }], print_order: [{ id: 'cat-drinks', name: 'Bebidas', position: 1 }, { id: 'cat-food', name: 'Alimentos', position: 2 }] } });
    }
    if (path === '/admin-catalog/stock-thresholds') return route.fulfill({ json: [{ item_id: '018f6f73-2d0a-74f0-8f1c-000000000222', item_name: 'Harina de prueba', branch_id: branchId, warehouse_id: 'warehouse-qa', unit_id: 'unit-piece', unit_code: 'PZA', quantity_on_hand: '8.5', minimum_quantity: '10', maximum_quantity: '25', version: 2, status: 'below_minimum', as_of: '2026-09-18T20:00:00Z' }] });
    if (path.startsWith('/admin-catalog/stock-thresholds/')) {
      state.thresholdRequest = { method: route.request().method(), body: route.request().postDataJSON() };
      return route.fulfill({ status: route.request().method() === 'DELETE' ? 204 : 200, json: { version: 3 } });
    }
    if (path.endsWith('/recipe-usages')) return route.fulfill({ json: [{ product_id: products[0].id, product_name: products[0].name, product_sku: products[0].sku, recipe_id: 'recipe-qa', recipe_version: 3, item_id: '018f6f73-2d0a-74f0-8f1c-000000000222', quantity_base_units: '2.5', unit_id: 'unit-piece', unit_code: 'PZA' }] });
    if (path === '/admin-catalog/recipes/bulk-preview') {
      state.bulkPreview = route.request().postDataJSON();
      return route.fulfill({ json: { branch_id: branchId, fingerprint: 'preview-qa', normalized_payload: { yield_quantity: '1', yield_unit_id: 'unit-piece', components: [{ item_id: '018f6f73-2d0a-74f0-8f1c-000000000222', unit_id: 'unit-piece', net_quantity: '2.5', waste_rate: '0', gross_quantity: '2.5' }] }, destinations: [{ product_id: products[0].id, expected_active_recipe_id: 'recipe-old', expected_version: 3, has_active_recipe: true, difference: { current_yield_quantity: '1', current_yield_unit_id: 'unit-piece', current_components: [{ item_id: '018f6f73-2d0a-74f0-8f1c-000000000222', unit_id: 'unit-piece', net_quantity: '1', waste_rate: '0' }], next_yield_quantity: '1', next_yield_unit_id: 'unit-piece', next_components: [{ item_id: '018f6f73-2d0a-74f0-8f1c-000000000222', unit_id: 'unit-piece', net_quantity: '2.5', waste_rate: '0' }], changed: true } }] } });
    }
    if (path === '/admin-catalog/recipes/bulk-apply') {
      state.bulkApply = { body: route.request().postDataJSON(), idempotencyKey: route.request().headers()['idempotency-key'] };
      return route.fulfill({ json: { command_id: 'command-qa', branch_id: branchId, destinations: [{ product_id: products[0].id, recipe_id: 'recipe-new', recipe_version: 4 }] } });
    }
    return route.fulfill({ json: [] });
  });
}

function syntheticUser() {
  return {
    id: 'adminretro-qa', display_name: 'Administradora de prueba', email: 'qa@example.invalid', is_superadmin: true,
    assigned_branch_id: branchId, roles: ['Administrador'], permissions: ['catalog.manage', 'recipes.manage', 'inventory.read'],
  };
}

async function prepareUser(page) {
  await page.addInitScript(({ id, branch }) => {
    localStorage.setItem('auth_token', 'synthetic-adminretro-token');
    localStorage.setItem('admin_branch_id', branch);
    localStorage.setItem('user', JSON.stringify({
      id, display_name: 'Administradora de prueba', email: 'qa@example.invalid', is_superadmin: true,
      assigned_branch_id: branch, roles: ['Administrador'], permissions: ['catalog.manage', 'recipes.manage', 'inventory.read'],
    }));
  }, { id: 'adminretro-qa', branch: branchId });
}

async function verifyLogin(browser) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  page.setDefaultTimeout(20_000);
  page.setDefaultNavigationTimeout(20_000);
  const state = { inventory: 'empty', user: syntheticUser() };
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  if (traceFile) {
    page.on('console', (message) => checkpoint(`Login console ${message.type()}: ${message.text()}`));
    page.on('pageerror', (error) => checkpoint(`Login page error: ${error.message}`));
  }
  await mockApi(page, state);
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' });
  checkpoint('Login loaded');
  if (traceFile) checkpoint(`Login headings: ${JSON.stringify(await page.locator('h1').allInnerTexts())}`);
  await page.getByRole('heading', { name: 'RestaurantOS' }).waitFor();
  assert.equal(await page.locator('html').evaluate((element) => element.scrollWidth <= element.clientWidth), true, 'login overflows at 390px');
  await assertNeutralSurface(page.locator('.admin-login .ui-card'));
  checkpoint('Login surface checked');
  await page.getByLabel('Correo electrónico').fill('qa@example.invalid');
  checkpoint('Login email filled');
  await page.getByLabel('Contraseña').fill('synthetic-secret');
  checkpoint('Login password filled');
  await page.getByRole('button', { name: 'Iniciar Sesión' }).press('Enter');
  checkpoint('Login submitted');
  await page.getByRole('heading', { name: 'Panel administrativo' }).waitFor();
  checkpoint('Login completed');
  assert.deepEqual(errors, []);
  await context.close();
}

async function assertNeutralSurface(locator) {
  const styles = await locator.evaluate((element) => {
    const style = getComputedStyle(element);
    return { color: style.color, backgroundColor: style.backgroundColor, borderColor: style.borderColor };
  });
  assert.ok(neutral(styles.color), `text must be neutral: ${styles.color}`);
  if (styles.backgroundColor !== 'rgba(0, 0, 0, 0)') assert.ok(neutral(styles.backgroundColor), `background must be neutral: ${styles.backgroundColor}`);
  assert.ok(neutral(styles.borderColor), `border must be neutral: ${styles.borderColor}`);
}

async function verifyViewport(browser, viewport) {
  checkpoint(`Checking ${viewport.width}px`);
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  page.setDefaultTimeout(20_000);
  page.setDefaultNavigationTimeout(20_000);
  const errors = [];
  const state = { inventory: 'empty', user: syntheticUser() };
  page.on('pageerror', (error) => errors.push(error.message));
  await prepareUser(page);
  await mockApi(page, state);
  await page.goto(`${baseUrl}/products`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Productos y catálogo' }).waitFor();
  checkpoint(`Products loaded ${viewport.width}px`);
  assert.equal(await page.locator('html').evaluate((element) => element.scrollWidth <= element.clientWidth), true, `document overflows at ${viewport.width}px`);
  await assertNeutralSurface(page.locator('.admin-sidebar'));
  await assertNeutralSurface(page.locator('.premium-card').first());
  await assertNeutralSurface(page.locator('.admin-sidebar-logo-icon'));
  assert.equal((await page.locator('.admin-sidebar-logo-icon').innerText()).includes('🥝'), false);
  assert.match(await page.locator('.admin-sidebar-logo-icon').evaluate((element) => getComputedStyle(element).fontFamily), /Tahoma|Segoe UI|Arial/);
  assert.match(await page.locator('.premium-table th').first().evaluate((element) => getComputedStyle(element).fontFamily), /Tahoma|Segoe UI|Arial/);
  assert.match(await page.getByRole('button', { name: 'Catálogo y Menú', exact: true }).evaluate((element) => getComputedStyle(element).fontFamily), /Tahoma|Segoe UI|Arial/);
  mkdirSync(screenshotDir, { recursive: true });
  await page.screenshot({ path: join(screenshotDir, `admin-retro-${viewport.width}.png`), fullPage: true });
  await page.getByRole('button', { name: 'Nuevo producto' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.waitFor();
  await assertNeutralSurface(dialog);
  await page.screenshot({ path: join(screenshotDir, `admin-retro-dialog-${viewport.width}.png`), fullPage: true });
  await page.keyboard.press('Escape');
  checkpoint(`Dialog dismissed ${viewport.width}px`);
  await page.getByRole('button', { name: 'Configuración', exact: true }).focus();
  await page.keyboard.press('Enter');
  assert.match(page.url(), /\/branches$/);
  checkpoint(`Configuration opened ${viewport.width}px`);
  await page.goto(`${baseUrl}/catalog`, { waitUntil: 'domcontentloaded' });
  const catalogCard = page.getByRole('button', { name: 'Acceder a Productos' });
  await catalogCard.focus();
  await page.keyboard.press('Enter');
  assert.match(page.url(), /\/products$/);
  checkpoint(`Catalog card opened ${viewport.width}px`);
  if (viewport.width === 1440) {
    for (const path of ['inventory/items', 'purchase-presentations', 'suppliers', 'recipes', 'warehouses']) {
      checkpoint(`Checking catalog route ${path}`);
      await page.goto(`${baseUrl}/${path}`, { waitUntil: 'domcontentloaded' });
      await page.locator('main, section, h1').first().waitFor();
      assert.ok((await page.locator('body').innerText()).trim().length > 40, `catalog route ${path} should render`);
    }
    state.inventory = 'loading';
    state.inventoryGate = new Promise((resolve) => { state.releaseInventory = resolve; });
    const loadingRoute = page.goto(`${baseUrl}/inventory/items`);
    await page.getByText('Cargando insumos...').waitFor();
    state.releaseInventory();
    await loadingRoute;
    await page.getByText('No hay insumos registrados').waitFor();
    checkpoint('Inventory loading and empty checked');
    state.inventory = 'error';
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.getByText('Error al cargar los insumos.').waitFor();
    checkpoint('Inventory error checked');
    state.inventory = 'empty';
    await page.goto(`${baseUrl}/products`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: 'Productos y catálogo' }).waitFor();
    await page.goto(`${baseUrl}/category-priorities`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: 'Prioridades administrativas' }).waitFor();
    checkpoint('Priorities loaded');
    await page.locator('.admin-catalog-order:not(.admin-catalog-print-order)').getByRole('button', { name: 'Bajar Alimentos' }).click();
    await page.getByRole('button', { name: 'Guardar prioridades' }).click();
    await page.getByText('Prioridades administrativas guardadas.').waitFor();
    checkpoint('Priorities saved');
    assert.deepEqual(state.prioritySave.view_category_ids, ['cat-drinks', 'cat-food']);
    assert.deepEqual(state.prioritySave.print_category_ids, ['cat-drinks', 'cat-food']);
    await page.goto(`${baseUrl}/inventory/thresholds`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: 'Umbrales de existencias' }).waitFor();
    checkpoint('Thresholds loaded');
    await page.getByRole('button', { name: 'Editar umbrales de Harina de prueba' }).click();
    await page.getByLabel('Mínimo').fill('11');
    await page.getByRole('button', { name: 'Guardar umbrales' }).click();
    await page.getByText('Umbrales guardados. La existencia se conserva sin cambios.').waitFor();
    checkpoint('Thresholds saved');
    assert.deepEqual(state.thresholdRequest, { method: 'PUT', body: { minimum_quantity: '11', maximum_quantity: '25', expected_version: 2 } });
    state.inventory = 'rows';
    await page.goto(`${baseUrl}/inventory/items`, { waitUntil: 'domcontentloaded' });
    await page.getByTitle('Consultar recetas que usan este insumo').click();
    await page.getByText('Producto de prueba').waitFor();
    checkpoint('Recipe usages loaded');
    await page.getByRole('button', { name: 'Abrir receta' }).click();
    await page.getByRole('heading', { name: 'Escandallo y Recetas por Producto' }).waitFor();
    await page.getByText('Versión efectiva solicitada: recipe-qa').waitFor();
    checkpoint('Recipe detail opened');
    await page.goto(`${baseUrl}/recipes/bulk`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: 'Aplicar receta a varios productos' }).waitFor();
    checkpoint('Bulk recipe loaded');
    await page.getByLabel('Unidad de rendimiento').selectOption('unit-piece');
    await page.getByLabel(/Producto de prueba/).check();
    await page.locator('.admin-catalog-tool tbody select').first().selectOption('018f6f73-2d0a-74f0-8f1c-000000000222');
    await page.locator('.admin-catalog-tool tbody input').first().fill('2.5');
    await page.getByRole('button', { name: 'Ver diferencias' }).click();
    await page.getByText('Diferencias revisadas').waitFor();
    checkpoint('Bulk preview displayed');
    assert.equal(state.bulkPreview.components[0].net_quantity, '2.5');
    const differenceText = await page.locator('.admin-catalog-difference').innerText();
    if (traceFile) checkpoint(`Bulk difference text: ${differenceText}`);
    assert.match(differenceText, /Harina de prueba.*1 PZA, merma 0/);
    assert.match(differenceText, /Harina de prueba.*2\.5 PZA, merma 0/);
    checkpoint('Bulk difference values checked');
    await page.getByRole('button', { name: 'Confirmar lote versionado' }).click();
    await page.getByText('Lote aplicado: 1 receta(s) versionada(s). Comando command-qa.').waitFor();
    checkpoint('Bulk recipe applied');
    assert.equal(state.bulkApply.body.preview_fingerprint, 'preview-qa');
    assert.ok(state.bulkApply.idempotencyKey);
    assert.equal('gross_quantity' in state.bulkApply.body.components[0], false);
    await page.goto(`${baseUrl}/products`, { waitUntil: 'domcontentloaded' });
    await page.getByTitle('Composición fija').first().click();
    await page.getByText('Composición fija: Producto de prueba').waitFor();
    checkpoint('Composition editor loaded');
    await page.getByLabel('Producto componente 1').selectOption(products[1].id);
    await page.getByLabel('Cantidad del componente 1').fill('1.5');
    await assert.equal(await page.getByRole('button', { name: 'Guardar composición versionada' }).isDisabled(), true);
    await page.getByLabel('Cantidad del componente 1').fill('2');
    const compositionRefresh = page.waitForResponse((response) => response.url().includes(`/products/${products[0].id}/composition`) && response.request().method() === 'GET');
    await page.getByRole('button', { name: 'Guardar composición versionada' }).click();
    await page.getByText('Composición versionada (v1). El precio canónico es MXN 10.00.').waitFor();
    await compositionRefresh;
    await page.getByText('No fue posible actualizar la lectura. Se conserva la última composición autoritativa y tu borrador.').waitFor();
    assert.equal(await page.getByLabel('Cantidad del componente 1').inputValue(), '2');
    state.comboRefreshError = false;
    state.comboConflictMode = true;
    await page.getByRole('button', { name: 'Guardar composición versionada' }).click();
    await page.getByRole('button', { name: 'Revisar versión vigente' }).waitFor();
    assert.equal(state.comboConflictRequest.expected_version, 1);
    assert.equal(await page.getByRole('button', { name: 'Guardar composición versionada' }).isDisabled(), true);
    assert.equal(await page.getByLabel('Cantidad del componente 1').inputValue(), '2');
    state.comboReviewError = true;
    await page.getByRole('button', { name: 'Revisar versión vigente' }).click();
    await page.getByText('No fue posible actualizar la lectura. Se conserva la última composición autoritativa y tu borrador.').waitFor();
    assert.equal(await page.getByRole('button', { name: 'Guardar composición versionada' }).isDisabled(), true);
    assert.equal(await page.getByLabel('Cantidad del componente 1').inputValue(), '2');
    state.comboReviewError = false;
    state.comboComposition.version = 2;
    await page.getByRole('button', { name: 'Revisar versión vigente' }).click();
    await page.getByText('Versión revisada: v2.').waitFor();
    assert.equal(await page.getByRole('button', { name: 'Guardar composición versionada' }).isDisabled(), false);
    state.checkLocalCandidates = true;
    const scopeSelect = page.getByRole('dialog').getByLabel('Alcance');
    const componentSelect = page.getByLabel('Producto componente 1');
    await scopeSelect.selectOption(otherBranchId);
    await componentSelect.locator('option[value="local-norte"]').waitFor({ state: 'attached' });
    assert.equal(await componentSelect.locator('option[value="local-centro"]').count(), 0);
    assert.equal(await page.getByText('Versión revisada: v2.').count(), 0);
    await scopeSelect.selectOption(branchId);
    await componentSelect.locator('option[value="local-centro"]').waitFor({ state: 'attached' });
    assert.equal(await componentSelect.locator('option[value="local-norte"]').count(), 0);
    await scopeSelect.selectOption('');
    await componentSelect.locator('option[value="local-centro"]').waitFor({ state: 'detached' });
    assert.equal(await componentSelect.locator('option[value="local-norte"]').count(), 0);
    assert.equal(await componentSelect.locator(`option[value="${products[1].id}"]`).count(), 1);
    checkpoint('Composition saved');
    assert.deepEqual(state.comboSave.body, { branch_id: branchId, expected_version: 0, components: [{ product_id: products[1].id, quantity: '2' }] });
    assert.ok(state.comboSave.idempotencyKey);
  }
  assert.deepEqual(errors, []);
  checkpoint(`Viewport done ${viewport.width}px`);
  await context.close();
}

const browser = await chromium.launch({ headless: true, ...(process.env.ADMINRETRO_CHROME_PATH ? { executablePath: process.env.ADMINRETRO_CHROME_PATH } : {}) });
try {
  await verifyLogin(browser);
  for (const width of requestedViewports) {
    await verifyViewport(browser, { width, height: width === 390 ? 844 : width === 768 ? 900 : 1000 });
  }
  console.log('Admin retro browser QA passed');
} catch (error) {
  checkpoint(`Admin retro browser QA failed: ${error instanceof Error ? error.stack || error.message : String(error)}`);
  throw error;
} finally {
  await browser.close();
}
