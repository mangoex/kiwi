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
async function verifyPresentation(width, canEdit = true) {
  const context = await browser.newContext({ viewport: { width, height: 940 } });
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  await page.route('https://fonts.googleapis.com/**', route => route.abort());
  await page.route('https://fonts.gstatic.com/**', route => route.abort());
  let saved;
  let failSave = false;
  let previewPayload;
  let presentation = { id: 'pres-qa', code: 'PRES-1001', name: 'Aceituna frasco 450 g',
    item_id: 'olive-qa', supplier_id: 'general-qa', supplier_name: 'PROVEEDOR GENERAL',
    item_name: 'Aceituna', base_unit_code: 'KILO', base_unit_yield: '0.450000',
    usable_content: '1.000000', commercial_unit_id: 'kilo-qa', last_net_price: '91.050000',
    cost_per_base_unit: '202.333333', tax_rate: '0.160000', status: 'active',
    updated_at: '2026-10-20T12:00:00+00:00' };
  await page.addInitScript(() => localStorage.setItem('auth_token', 'synthetic-supplier-workspace-token'));
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
    if (path === '/auth/session') {
      const session = corporateAdminSession(user, branchId);
      session.admin_capabilities['admin.manage'] = canEdit;
      return route.fulfill({ json: session });
    }
    if (path === '/purchase-presentations/preview') {
      previewPayload = route.request().postDataJSON();
      return route.fulfill({ json: { cost_per_base_unit: '202.333333',
        content_cost_mismatch: previewPayload.usable_content === '1.000000' } });
    }
    if (path === '/purchase-presentations/pres-qa') {
      saved = route.request().postDataJSON();
      if (failSave) return route.fulfill({ status: 409, json: { detail: {
        code: 'presentation_version_conflict', message: 'La presentación cambió; actualiza el listado.' } } });
      presentation = { ...presentation, ...saved, supplier_name: 'Proveedor real QA' };
      return route.fulfill({ json: presentation });
    }
    if (path === '/purchase-presentations') return route.fulfill({ json: [presentation] });
    if (path === '/suppliers') return route.fulfill({ json: [
      { id: 'general-qa', commercial_name: 'PROVEEDOR GENERAL', status: 'active' },
      { id: 'real-qa', commercial_name: 'Proveedor real QA', status: 'active' },
      { id: 'inactive-qa', commercial_name: 'Proveedor inactivo QA', status: 'inactive' },
    ] });
    if (path === '/inventory/items') return route.fulfill({ json: [
      { id: 'olive-qa', name: 'Aceituna', sku: '1001', base_unit_id: 'kilo-qa', unit_code: 'KILO' },
    ] });
    if (path === '/inventory/units') return route.fulfill({ json: [
      { id: 'kilo-qa', code: 'KILO' }, { id: 'jar-qa', code: 'FRASCO' },
    ] });
    return route.fulfill({ json: [] });
  });
  try {
    await page.goto(`${baseUrl}/purchase-presentations`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    await page.getByText(presentation.name, { exact: true }).waitFor();
    const edit = page.getByRole('button', { name: `Editar ${presentation.name}`, exact: true });
    if (!canEdit) { assert.equal(await edit.count(), 0); return; }
    await edit.click();
    const dialog = page.getByRole('dialog');
    const save = dialog.getByRole('button', { name: 'Guardar Cambios', exact: true });
    await dialog.getByText('Revisa el contenido heredado', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('Proveedor', { exact: true }).isEnabled(), true);
    assert.equal(await page.getByLabel('Unidad comercial', { exact: true }).isEnabled(), true);
    assert.equal(await page.getByLabel('Insumo base', { exact: true }).isDisabled(), true);
    assert.equal(await page.getByLabel('Clave / Código', { exact: true }).isDisabled(), true);
    assert.equal(await page.getByLabel('Precio de compra neto ($ MXN)', { exact: true }).inputValue(), '91.05');
    assert.equal(await page.getByLabel('Impuesto (%)', { exact: true }).inputValue(), '16.00');
    assert.match(await dialog.innerText(), /202\.33/);
    assert.equal(previewPayload.presentation_id, presentation.id);
    await page.getByLabel('Proveedor', { exact: true }).selectOption('real-qa');
    await page.getByLabel('Unidad comercial', { exact: true }).selectOption('jar-qa');
    assert.equal(await page.getByLabel('Proveedor', { exact: true }).locator('option[value="inactive-qa"]').count(), 0);
    await save.click();
    await dialog.waitFor({ state: 'hidden' });
    assert.equal(saved.supplier_id, 'real-qa');
    assert.equal(saved.commercial_unit_id, 'jar-qa');
    assert.equal(saved.expected_updated_at, presentation.updated_at);
    assert.equal(saved.usable_content, '1.000000');
    assert.equal(saved.base_unit_yield, '0.450000');
    assert.equal(saved.last_net_price, '91.050000');
    assert.equal(saved.tax_rate, '0.160000');
    await page.getByText('Proveedor real QA', { exact: true }).waitFor();
    await edit.click();
    await dialog.getByText('Revisa el contenido heredado', { exact: true }).waitFor();
    await dialog.getByRole('button', { name: 'Usar rendimiento como contenido útil', exact: true }).click();
    await dialog.getByText('Revisa el contenido heredado', { exact: true }).waitFor({ state: 'hidden' });
    assert.equal(await page.getByLabel('Contenido útil (KILO)', { exact: true }).inputValue(), '0.45');
    await page.getByLabel('Precio de compra neto ($ MXN)', { exact: true }).fill('91.051');
    await dialog.getByRole('alert').getByText('Usa máximo 2 decimales, sin signos ni exponentes.', { exact: true }).waitFor();
    assert.equal(await save.isDisabled(), true);
    await page.getByLabel('Precio de compra neto ($ MXN)', { exact: true }).fill('91.05');
    failSave = true;
    await save.click();
    await dialog.getByRole('alert').getByText(/La presentación cambió/).waitFor();
    assert.equal(await page.getByLabel('Contenido útil (KILO)', { exact: true }).inputValue(), '0.45');
    failSave = false;
    await page.screenshot({ path: `${screenshotDir}/presentation-editor-${width}.png` });
    const layout = await dialog.evaluate(element => ({ width: element.clientWidth,
      scroll: element.scrollWidth, viewport: window.innerWidth, left: element.getBoundingClientRect().left }));
    assert.ok(layout.scroll <= layout.width + 1 && layout.left >= 0 && layout.width <= layout.viewport);
    await save.click();
    await dialog.waitFor({ state: 'hidden' });
    assert.equal(saved.usable_content, '0.450000');
    console.log(`Presentation correction: ${width}px, provider/unit, legacy cost, precision, explicit content and errors passed`);
  } catch (error) {
    console.error(error.message);
    console.error((await page.locator('body').innerText()).slice(-2400));
    await page.screenshot({ path: `${screenshotDir}/presentation-failure-${width}.png`, animations: 'disabled', timeout: 10000 });
    throw error;
  } finally { await context.close(); }
}
try { if (!process.env.SUPPLIER_PRESENTATION_ONLY) {
    await verify(1440); await verify(390); await verify(1440, false);
  }
  await verifyPresentation(1440); await verifyPresentation(390); await verifyPresentation(1440, false); }
finally { await browser.close(); }
