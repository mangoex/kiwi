// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-compound-product-browser-v1
import assert from 'node:assert/strict';
import { corporateAdminSession } from '../fixtures/admin_session_fixture.mjs';

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
const alternativeComponent = {
  id: '018f6f73-2d0a-74f0-8f1c-000000000114',
  name: 'Complemento alternativo QA',
  sku: 'SIMPLE-QA-2',
  category_name: 'Pruebas',
  station: 'kitchen',
  price_cents: 600,
  status: 'active',
  catalog_scope: 'organization',
};
const branchOnlyProduct = {
  id: '018f6f73-2d0a-74f0-8f1c-000000000115',
  name: 'Producto exclusivo de sucursal QA',
  sku: 'BRANCH-QA',
  category_name: 'Pruebas',
  station: 'kitchen',
  price_cents: 700,
  status: 'active',
  catalog_scope: 'branch',
  source_branch_id: branchId,
};
const inventoryItem = {
  id: '018f6f73-2d0a-74f0-8f1c-000000000313',
  name: 'Papa blanca QA',
};
const adminUser = {
  id: 'compound-product-qa',
  display_name: 'Administradora QA',
  is_superadmin: true,
  assigned_branch_id: branchId,
  roles: ['Administrador'],
  permissions: ['catalog.manage', 'recipes.manage'],
};
const state = {
  saved: null,
  previewRequests: 0,
  previewPayloads: [],
  catalogRequests: 0,
  failCopyCatalog: false,
  copyRequests: [],
  copyMode: 'replay',
};

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
    localStorage.setItem('auth_token', 'synthetic-compound-product-token');
    localStorage.setItem('admin_branch_id', branch);
    localStorage.setItem('user', JSON.stringify(user));
  }, { branch: branchId, user: adminUser });
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/v1', '');
    if (path === '/auth/session') return route.fulfill({ json: corporateAdminSession(adminUser, branchId) });
    if (path === '/auth/login') {
      return route.fulfill({ json: {
        token: 'synthetic-compound-product-token-refreshed',
        user: adminUser,
      } });
    }
    if (path === '/branches') {
      return route.fulfill({ json: [{ id: branchId, name: 'Sucursal QA', status: 'active' }] });
    }
    if (path === '/catalog/products') {
      state.catalogRequests += 1;
      if (state.failCopyCatalog && state.catalogRequests > 1) {
        return route.fulfill({ status: 503, json: { detail: { message: 'Catálogo no disponible' } } });
      }
      return route.fulfill({ json: [parent, component, alternativeComponent, branchOnlyProduct] });
    }
    if (path.endsWith('/modifier-configuration/selection-preview')) {
      state.previewRequests += 1;
      state.previewPayloads.push(route.request().postDataJSON());
      return route.fulfill({ json: {
        source: 'python',
        context_fingerprint: 'f'.repeat(64),
        line_total_cents: 2250,
        modifier_total_cents: 1250,
        consumption: { components: [{ item_id: inventoryItem.id, item_name: inventoryItem.name, gross_quantity: '0.250000', unit_code: 'KILO' }] },
      } });
    }
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
        component_candidates: [
          { id: component.id, name: component.name, sku: component.sku },
          { id: alternativeComponent.id, name: alternativeComponent.name, sku: alternativeComponent.sku },
        ],
      } });
    }
    if (path === `/products/${component.id}/modifier-configuration`) {
      return route.fulfill({ json: {
        product: { id: component.id, name: component.name, sku: component.sku, station: component.station },
        expected_version: 4,
        groups: [],
        component_candidates: [],
      } });
    }
    if (path === `/products/${parent.id}/modifier-configuration/copy`) {
      state.copyRequests.push({
        body: route.request().postData(),
        idempotencyKey: route.request().headers()['idempotency-key'],
      });
      if (state.copyMode === 'unauthorized') {
        state.copyMode = 'replay';
        return route.fulfill({
          status: 401,
          json: { detail: { code: 'session_expired', message: 'La sesión venció' } },
        });
      }
      return route.fulfill({ json: { version: 0, groups: [], result: 'replay' } });
    }
    return route.fulfill({ json: [] });
  });

  console.log('Opening compound-product Admin fixture');
  await page.goto(`${baseUrl}/products`, { waitUntil: 'domcontentloaded' });
  console.log(`Compound-product fixture URL: ${page.url()}`);
  console.log(`Compound-product fixture text: ${(await page.locator('body').innerText()).slice(0, 240)}`);
  await page.locator('.productos-window-container').waitFor();
  console.log('Products workspace loaded');
  await page.getByRole('cell', { name: parent.name, exact: true }).waitFor();
  await page.getByRole('tab', { name: 'Principal / Varios' }).press('End');
  assert.equal(await page.getByRole('tab', { name: 'Modificadores / Producto compuesto' }).getAttribute('aria-selected'), 'true');
  await page.getByRole('heading', { name: 'Grupos y productos seleccionables' }).waitFor();
  console.log('Compound-product tab loaded');
  const editorBeforePreview = await page.locator('body').evaluate(() => {
    const editor = [...document.querySelectorAll('button')].find((button) => button.textContent?.includes('Agregar grupo de selección'));
    const preview = [...document.querySelectorAll('h3')].find((heading) => heading.textContent?.includes('Probar selección guardada'));
    return Boolean(editor && preview && (editor.compareDocumentPosition(preview) & Node.DOCUMENT_POSITION_FOLLOWING));
  });
  assert.equal(editorBeforePreview, true, 'editor must precede preview tools');
  await page.getByRole('button', { name: 'Agregar grupo de selección' }).focus();
  await page.keyboard.press('Enter');
  await page.getByLabel('Nombre del grupo').fill('Acompañamientos');
  await page.getByLabel('Selecciones incluidas').fill('0');
  await page.getByRole('button', { name: 'Agregar producto u opción' }).click();
  const editor = page.getByRole('region', { name: /^Producto compuesto/ });
  await editor.locator('.modifier-option-row select').nth(1).selectOption(component.id);
  await page.getByLabel('Precio extra MXN').fill('12.50');
  await page.getByRole('button', { name: 'Agregar producto u opción' }).click();
  const secondOption = editor.locator('.modifier-option-row').nth(1);
  await secondOption.locator('select').nth(1).selectOption(alternativeComponent.id);
  const save = page.getByRole('button', { name: 'Guardar configuración' });
  assert.equal(await save.isDisabled(), false);
  await save.click();
  await page.getByText(/Configuración guardada como versión 1/).waitFor();
  console.log('Compound-product draft saved');

  assert.equal(state.saved.body.expected_version, 0);
  assert.equal(state.saved.body.groups[0].included_selections, 0);
  assert.equal(state.saved.body.groups[0].options[0].component_product_id, component.id);
  assert.equal(state.saved.body.groups[0].options[0].price_delta_cents, 1250);
  assert.equal(state.saved.body.groups[0].options[1].component_product_id, alternativeComponent.id);
  assert.ok(state.saved.idempotencyKey);
  await page.waitForTimeout(350);
  assert.equal(state.previewRequests, 0, 'preview must wait for a valid explicit request');

  const sourceSelect = page.getByLabel('Producto de origen');
  assert.equal(await sourceSelect.locator(`option[value="${component.id}"]`).count(), 1);
  assert.equal(await sourceSelect.locator(`option[value="${branchOnlyProduct.id}"]`).count(), 0, 'branch products cannot be copy sources');
  assert.ok(state.catalogRequests >= 1, 'copy source uses the canonical catalog');

  await page.getByRole('checkbox', { name: component.name }).check();
  assert.equal(await page.getByRole('checkbox', { name: alternativeComponent.name }).isDisabled(), true);
  const previewButton = page.getByRole('button', { name: 'Calcular vista previa' });
  assert.equal(await previewButton.isDisabled(), false);
  await previewButton.click();
  await page.getByText(inventoryItem.name).waitFor();
  await page.getByText('Precio: $22.50 MXN · adicionales: $12.50 MXN').waitFor();
  assert.equal(state.previewRequests, 1);
  assert.deepEqual(state.previewPayloads[0].modifiers, [{ option_id: 'option-qa-1' }]);
  assert.equal(await page.getByText(inventoryItem.id, { exact: false }).count(), 0, 'UUID must not be the primary inventory label');
  await previewButton.click();
  await page.waitForTimeout(350);
  assert.equal(state.previewRequests, 2, 'each explicit preview action recalculates in Python');
  assert.equal(
    await page.locator('html').evaluate((element) => element.scrollWidth <= element.clientWidth),
    true,
    'compound-product editor must not overflow the 1440px viewport',
  );
  assert.deepEqual(errors, []);
  if (screenshotPath) await page.screenshot({ path: screenshotPath, fullPage: true });

  await page.getByRole('tab', { name: 'Modificadores / Producto compuesto' }).press('Home');
  assert.equal(await page.getByRole('tab', { name: 'Principal / Varios' }).getAttribute('aria-selected'), 'true');
  await page.getByRole('heading', { name: 'Probar selección guardada' }).waitFor({ state: 'detached' });

  const selectParent = async () => {
    await page.waitForFunction(() => !document.body.innerText.includes('Cargando contexto de sucursal...'));
    const cell = page.getByRole('cell', { name: parent.name, exact: true });
    await cell.waitFor();
    await cell.click();
    await page.getByRole('tab', { name: 'Principal / Varios' }).waitFor();
  };
  const openModifierTab = async () => {
    await page.getByRole('button', { name: /Mostrar página \d+ de \d+/ }).last().click();
    await page.getByRole('tab', { name: 'Modificadores / Producto compuesto' }).click();
    await page.getByRole('heading', { name: 'Probar selección guardada' }).waitFor();
  };

  // A catalog failure must block a brand-new copy before any command is sent.
  state.failCopyCatalog = false;
  state.catalogRequests = 0;
  await page.reload({ waitUntil: 'domcontentloaded' });
  await selectParent();
  state.failCopyCatalog = true;
  await openModifierTab();
  await page.waitForTimeout(500);
  assert.ok(state.catalogRequests > 1, 'copy source must issue its own canonical catalog request');
  await page.getByText('No se pudo cargar el catálogo corporativo. No puedes iniciar una copia nueva.').waitFor();
  assert.equal(await page.getByLabel('Producto de origen').isDisabled(), true);
  assert.equal(await page.getByRole('button', { name: 'Confirmar copia completa' }).isDisabled(), true);
  assert.equal(state.copyRequests.length, 0, 'catalog failure must not send a new copy command');

  // Create a real uncertain intent: the copy receives 401, the session boundary quarantines it,
  // and the same actor signs back in without reloading the JavaScript runtime.
  state.failCopyCatalog = false;
  state.catalogRequests = 0;
  await page.reload({ waitUntil: 'domcontentloaded' });
  await selectParent();
  await openModifierTab();
  await page.getByLabel('Producto de origen').selectOption(component.id);
  await page.getByText('Origen v4 · destino v0.').waitFor();
  await page.getByRole('checkbox', { name: /Revisé el reemplazo completo/ }).check();
  state.copyMode = 'unauthorized';
  await page.getByRole('button', { name: 'Confirmar copia completa' }).click();
  await page.getByText('Tu sesión venció o fue invalidada. Inicia sesión de nuevo.').waitFor();
  assert.equal(state.copyRequests.length, 1);
  const uncertainIntent = state.copyRequests[0];
  assert.ok(uncertainIntent.idempotencyKey);
  assert.deepEqual(JSON.parse(uncertainIntent.body), {
    source_product_id: component.id,
    expected_source_version: 4,
    expected_target_version: 0,
  });

  state.catalogRequests = 0;
  await page.getByLabel('Correo electrónico').fill('admin@example.test');
  await page.getByLabel('Contraseña').fill('test-only-password');
  await page.getByRole('button', { name: 'Iniciar Sesión' }).click();
  await page.waitForFunction(() => localStorage.getItem('auth_token') === 'synthetic-compound-product-token-refreshed');
  await page.evaluate(() => {
    window.history.pushState(null, '', '/admin/products');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await page.locator('.productos-window-container').waitFor();
  await selectParent();
  state.failCopyCatalog = true;
  await openModifierTab();
  await page.getByText('No se pudo actualizar el catálogo corporativo. La recuperación conserva la intención pendiente.').waitFor();
  assert.equal(await page.getByLabel('Producto de origen').isDisabled(), true);
  const recoverCopy = page.getByRole('button', { name: 'Recuperar copia' });
  assert.equal(await recoverCopy.isDisabled(), false, 'catalog failure must not block an idempotent replay');
  await recoverCopy.click();
  await page.getByText('Copia registrada y destino releído.').waitFor();
  await page.getByText('No se pudo cargar el catálogo corporativo. No puedes iniciar una copia nueva.').waitFor();
  assert.equal(await page.getByRole('button', { name: 'Confirmar copia completa' }).isDisabled(), true);
  assert.equal(state.copyRequests.length, 2);
  assert.equal(state.copyRequests[1].idempotencyKey, uncertainIntent.idempotencyKey);
  assert.equal(state.copyRequests[1].body, uncertainIntent.body);
  assert.deepEqual(errors, []);
  console.log('Compound-product Admin browser QA passed');
} finally {
  await browser.close();
}
