// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-supplier-workspace-v1
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { corporateAdminSession } from '../fixtures/admin_session_fixture.mjs';

const { chromium } = await import(process.env.SUPPLIER_PLAYWRIGHT_IMPORT || 'playwright');
const baseUrl = process.env.SUPPLIER_BASE_URL || 'http://127.0.0.1:3002/admin';
const screenshotDir = process.env.SUPPLIER_SCREENSHOT_DIR || 'output/playwright';
const branchId = '018f6f73-2d0a-74f0-8f1c-000000000003';
const user = { id: 'supplier-qa-user', display_name: 'Administradora QA', email: 'supplier@example.invalid' };
const browser = await chromium.launch({ headless: true, ...(process.env.SUPPLIER_CHROME_PATH ? { executablePath: process.env.SUPPLIER_CHROME_PATH } : {}) });
mkdirSync(screenshotDir, { recursive: true });

async function verify(width, canManage = true) {
  const context = await browser.newContext({ viewport: { width, height: 940 } });
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  const state = { mode: 'rows', saved: null, presentationError: false };
  const supplier = { id: 'supplier-qa', code: 'P001', commercial_name: 'Proveedor de bebidas QA', legal_name: 'Bebidas de prueba SA', tax_id: '', status: 'active', credit_days: 0, credit_limit: '123.456789', municipality: '', state: '' };
  await page.addInitScript(() => localStorage.setItem('auth_token', 'synthetic-supplier-workspace-token'));
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
    if (path === '/auth/session') {
      const session = corporateAdminSession(user, branchId);
      session.admin_capabilities['catalog.manage'] = canManage;
      return route.fulfill({ json: session });
    }
    if (path === '/suppliers/supplier-qa' && route.request().method() === 'PUT') {
      state.saved = route.request().postDataJSON();
      return route.fulfill({ json: { ...supplier, ...state.saved } });
    }
    if (path === '/suppliers') {
      if (state.mode === 'error') return route.fulfill({ status: 503, json: { detail: { code: 'synthetic_failure', message: 'Error de prueba' } } });
      return route.fulfill({ json: state.mode === 'empty' ? [] : [{ ...supplier, ...state.saved }, { ...supplier, id: 'supplier-other', code: 'P002', commercial_name: 'Proveedor de empaques QA', status: 'inactive', credit_days: 30 }, { ...supplier, id: 'supplier-suspended', code: 'P003', commercial_name: 'Proveedor suspendido QA', status: 'suspended' }] });
    }
    if (path === '/purchase-presentations') {
      if (state.presentationError) return route.fulfill({ status: 503, json: { detail: { code: 'synthetic_failure', message: 'Error de prueba' } } });
      return route.fulfill({ json: [{ id: 'presentation-qa', code: 'CAJA-24', name: 'Caja de 24 botellas', supplier_name: supplier.commercial_name, item_name: 'Bebida QA', last_net_price: 123.5 }] });
    }
    return route.fulfill({ json: [] });
  });
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  try {
    await page.goto(`${baseUrl}/suppliers`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    await page.getByText(supplier.commercial_name, { exact: true }).first().waitFor();
    await page.getByText(supplier.commercial_name, { exact: true }).first().click();
    const drawer = page.getByRole('complementary', { name: 'Panel lateral de detalles FastTab' });
    await drawer.waitFor();
    assert.doesNotMatch(await drawer.innerText(), /F-9081|F-9204|A-9842|22 días|14,500|Flujo Semanal Compensado/, 'El proveedor no debe heredar facturas o métricas ficticias');
    assert.equal(await page.getByLabel('Días de crédito', { exact: true }).inputValue(), '0', 'El crédito cero no debe convertirse en 15');
    assert.equal(await page.getByLabel('Días de crédito', { exact: true }).isDisabled(), true);
    await drawer.getByText('Cuentas por pagar', { exact: true }).click();
    await drawer.getByText('Cuentas por pagar', { exact: true }).click();
    await drawer.getByText('El saldo y los vencimientos no están disponibles en esta vista.', { exact: true }).waitFor();
    const layout = await page.evaluate(() => {
      const drawer = document.querySelector('.fast-tab-drawer');
      const input = document.querySelector('#supplier-credit-days');
      const label = document.querySelector('label[for="supplier-credit-days"]');
      return { drawer: drawer.getBoundingClientRect().toJSON(), field: input.getBoundingClientRect().toJSON(), label: label.getBoundingClientRect().toJSON(), radius: getComputedStyle(input).borderRadius, scroll: drawer.querySelector('.fast-tab-drawer__body').scrollHeight > drawer.querySelector('.fast-tab-drawer__body').clientHeight };
    });
    assert.ok(layout.field.top >= layout.label.bottom + 4, 'La etiqueta y el campo deben tener separación vertical');
    assert.ok(parseFloat(layout.radius) >= 8, 'Los campos deben tener esquinas suaves');
    assert.ok(layout.drawer.x >= -1 && layout.drawer.right <= width + 1, 'El panel debe caber en el viewport');
    if (width === 390) assert.equal(layout.scroll, true, 'El expediente debe poder desplazarse en móvil');
    await page.screenshot({ path: `${screenshotDir}/supplier-detail-${width}${canManage ? '' : '-readonly'}.png` });
    await drawer.getByRole('button', { name: 'Cerrar', exact: true }).click();
    await page.getByText('Proveedor de empaques QA', { exact: true }).click();
    assert.equal(await page.getByLabel('Días de crédito', { exact: true }).inputValue(), '30', 'Cada ficha debe usar el crédito de su propio proveedor');
    await drawer.getByRole('button', { name: 'Cerrar', exact: true }).click();
    const suspendedRow = page.getByRole('row').filter({ hasText: 'Proveedor suspendido QA' });
    assert.match(await suspendedRow.innerText(), /Suspendido/, 'Una suspensión debe distinguirse de una desactivación');
    await page.getByText('Proveedor suspendido QA', { exact: true }).click();
    await drawer.getByText('Suspendido', { exact: true }).waitFor();
    await drawer.getByRole('button', { name: 'Cerrar', exact: true }).click();
    if (canManage) {
      await page.getByRole('button', { name: `Editar ${supplier.commercial_name}`, exact: true }).click();
      await page.getByLabel('Teléfono', { exact: true }).fill('6671234567');
      await page.getByRole('button', { name: 'Guardar proveedor', exact: true }).click();
      await drawer.waitFor({ state: 'hidden' });
      assert.equal(state.saved.credit_days, 0, 'Guardar otro campo debe conservar el crédito cero');
      assert.equal(state.saved.municipality, '', 'Guardar no debe inventar una ciudad');
      assert.equal(state.saved.credit_limit, '123.456789', 'Guardar otro campo no debe redondear un límite de crédito interno');
    } else {
      assert.equal(await page.getByRole('button', { name: /Editar / }).count(), 0);
      assert.equal(await page.getByRole('button', { name: 'Nuevo proveedor', exact: true }).count(), 0);
    }
    await page.getByRole('button', { name: /Presentaciones de compra/ }).click();
    await page.getByText('Caja de 24 botellas', { exact: true }).waitFor();
    assert.match(await page.locator('.suppliers-workspace').innerText(), /123\.50/, 'El precio debe mostrar dos decimales');
    await page.screenshot({ path: `${screenshotDir}/supplier-presentations-${width}.png` });
    state.presentationError = true;
    await page.reload();
    await page.getByRole('button', { name: /Presentaciones de compra/ }).click();
    await page.getByText('No pudimos cargar las presentaciones.', { exact: true }).waitFor();
    state.mode = 'empty';
    state.presentationError = false;
    await page.reload();
    await page.getByText('Todavía no hay proveedores registrados.', { exact: true }).waitFor();
    state.mode = 'error';
    await page.reload();
    await page.getByText('No pudimos cargar los proveedores.', { exact: true }).waitFor();
    state.mode = 'rows';
    await page.getByRole('button', { name: 'Reintentar', exact: true }).click();
    await page.getByText(supplier.commercial_name, { exact: true }).first().waitFor();
    console.log(`Supplier workspace: ${width}px, ${canManage ? 'editable' : 'read-only'}, zero credit, unavailable finance, errors and recovery passed`);
  } catch (error) {
    console.error({ pageErrors, url: page.url(), body: (await page.locator('body').innerText()).slice(0, 1800) });
    await page.screenshot({ path: `${screenshotDir}/supplier-failure-${width}.png` });
    throw error;
  } finally { await context.close(); }
}
try { await verify(1440); await verify(390); await verify(1440, false); }
finally { await browser.close(); }
