import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { corporateAdminSession } from '../fixtures/admin_session_fixture.mjs';

const { chromium } = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const admin = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
const pos = process.env.BRANCH_SCOPE_POS_URL || 'http://127.0.0.1:3001/pos';
const id = n => `018f6f73-2d0a-74f0-8f1c-${String(n).padStart(12, '0')}`;
const branches = [{ id: id(3), name: 'Centro QA', code: 'QA', status: 'active' },
  { id: id(4), name: 'Norte QA', code: 'QA2', status: 'active' }];
const products = [1, 2].map(n => ({ id: id(110+n), sku: `100${n}`, name: `PRODUCTO QA ${n}`,
  category_id: id(20), category_name: 'PRUEBAS', station: 'kitchen', price_cents: 1000,
  status: 'active', updated_at: '2026-10-15T00:00:00Z', catalog_scope: 'organization' }));
const profile = corporateAdminSession({ id: id(6), display_name: 'Dueño QA', email: 'pilot@example.invalid' }, id(3), branches);
profile.organization_id = id(1);
profile.scope = { ...profile.scope, authorization_version: 1, can_select_branch: false,
  branch_selection_block_reason: 'rollout_disabled' };
profile.active_branch = { ...profile.active_branch, timezone: 'America/Mazatlan', pos_catalog_visuals_enabled: false };
profile.pos_modules = { uber_eats: false, didi_food: false, rappi: false, invoicing: false };
const detail = { id: id(50), folio: 'QA-POS-0001', branch_id: id(3), status: 'ACCEPTED',
  version: 1, payment_status: 'PENDING', total_cents: 1000, created_at: '2026-10-15T00:00:00Z',
  lines: [], production_tasks: [], corrections: [], editable: true, service_type: 'takeout' };
const output = 'output/playwright/pilot-pos-admin';
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ headless: true, ...(process.env.ADMINRETRO_CHROME_PATH
  ? { executablePath: process.env.ADMINRETRO_CHROME_PATH } : {}) });
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    const errors = [], reads = [], writes = [];
    let returnedBranchId = id(3);
    page.on('pageerror', error => errors.push(error.message));
    page.setDefaultTimeout(15000);
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'pilot-synthetic-session');
      localStorage.setItem('pos_register_id', 'CAJA-QA');
    });
    await page.route('**/api/v1/**', async route => {
      const req = route.request(), url = new URL(req.url());
      const path = url.pathname.replace('/api/v1', '');
      if (req.method() !== 'GET') writes.push(path);
      if (path === '/auth/session') return route.fulfill({ json: profile });
      if (path === '/catalog/products') return route.fulfill({ json: products });
      if (path === '/categories') return route.fulfill({ json: [{ id: id(20), name: 'PRUEBAS', status: 'active' }] });
      if (path === '/orders/accounts') return route.fulfill({ json: { items: [detail], next_cursor: null } });
      if (path === `/orders/${detail.id}`) { reads.push(path); return route.fulfill({ json: { ...detail, branch_id: returnedBranchId } }); }
      if (path === '/orders/pending-count') return route.fulfill({ json: { count: 0 } });
      if (path.includes('/selection-group')) return route.fulfill({ json: { category_id: id(20), group: null, values: [], products: [] } });
      return route.fulfill({ json: [] });
    });
    await page.goto(`${admin}/inventory`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: 'Inventario y Almacén' }).waitFor();
    assert.equal(await page.locator('.admin-configuration-scope-control').count(), 0);
    await page.goto(`${admin}/inventory/items`, { waitUntil: 'domcontentloaded' });
    await page.locator('.insumos-window-title').getByText('Insumos', { exact: true }).waitFor();
    assert.equal(await page.locator('.admin-configuration-scope-control').count(), 0);
    await page.goto(`${admin}/products`, { waitUntil: 'domcontentloaded' });
    const selector = page.getByLabel('Producto', { exact: true });
    await selector.selectOption(products[1].id);
    assert.equal(await selector.inputValue(), products[1].id);
    const bounds = await page.locator('.productos-detail-panel').boundingBox();
    const container = await page.locator('.productos-workspace-layout').boundingBox();
    assert.ok(bounds && container && Math.abs(bounds.width - container.width) < 3);
    const selectorBounds = await selector.boundingBox();
    assert.ok(selectorBounds.y < bounds.y);
    await page.getByRole('button', { name: 'Editar', exact: true }).click();
    const productName = page.getByPlaceholder('Ej. AGUA DE FRESA CHICA');
    await productName.fill('BORRADOR QA');
    page.once('dialog', dialog => dialog.dismiss());
    await selector.selectOption(products[0].id);
    assert.equal(await selector.inputValue(), products[1].id);
    assert.equal(await productName.inputValue(), 'BORRADOR QA');
    page.once('dialog', dialog => dialog.accept());
    await selector.selectOption(products[0].id);
    assert.equal(await selector.inputValue(), products[0].id);
    await page.getByRole('button', { name: '+ Nuevo', exact: true }).click();
    page.once('dialog', dialog => dialog.dismiss());
    await selector.selectOption(products[1].id);
    assert.equal(await selector.inputValue(), '');
    assert.equal(await page.getByRole('button', { name: 'Guardar Nuevo', exact: true }).count(), 1);
    await page.getByRole('button', { name: 'Deshacer', exact: true }).click();
    await page.screenshot({ path: `${output}/productos-${width}.png`, fullPage: true });
    await page.emulateMedia({ media: 'print' });
    assert.equal(await page.getByRole('table', { name: 'Catálogo de productos para impresión' }).isVisible(), true);
    assert.equal(await page.locator('.productos-print-catalog tbody tr').count(), 2);
    await page.emulateMedia({ media: 'screen' });
    await page.goto(`${pos}/`, { waitUntil: 'domcontentloaded' });
    const branchSelect = page.getByLabel('Sucursal de trabajo');
    await branchSelect.waitFor();
    assert.equal(await branchSelect.isDisabled(), true);
    await page.getByText('El cambio de sucursal aún no está habilitado en el servidor.', { exact: true }).waitFor();
    await page.screenshot({ path: `${output}/sucursal-${width}.png`, fullPage: true });
    await page.goto(`${pos}/history?order_id=${detail.id}&branch_id=${id(4)}`, { waitUntil: 'domcontentloaded' });
    await page.getByText('El pedido pertenece a otro contexto de sucursal. Vuelve a su sucursal de origen.', { exact: true }).waitFor();
    assert.equal(reads.length, 0, 'Otro contexto no dispara la consulta de detalle');
    await page.goto(`${pos}/history?order_id=${detail.id}&branch_id=${id(3)}`, { waitUntil: 'domcontentloaded' });
    await page.getByText('QA-POS-0001', { exact: true }).last().waitFor();
    assert.ok(reads.length > 0);
    await page.screenshot({ path: `${output}/pedido-${width}.png`, fullPage: true });
    returnedBranchId = id(4);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.getByText('El pedido no corresponde a la sucursal de trabajo.', { exact: true }).waitFor();
    assert.deepEqual(writes, [], 'Cambiar selección, descartar y consultar no escriben pedidos/productos');
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`Pilot Admin/POS browser contracts passed at ${width}px`);
  }
} finally { await browser.close(); }
