import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const manifestPath = process.env.ADMINRETRO_E2E_MANIFEST;
if (!manifestPath) throw new Error('ADMINRETRO_E2E_MANIFEST is required');
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
const playwrightImport = process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright';
const { chromium } = await import(playwrightImport);
const baseUrl = manifest.admin_base_url;
const apiBaseUrl = `${new URL(baseUrl).origin}/api/v1`;

const browser = await chromium.launch({
  headless: true,
  ...(process.env.ADMINRETRO_CHROME_PATH ? { executablePath: process.env.ADMINRETRO_CHROME_PATH } : {}),
});
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(20_000);
  page.setDefaultNavigationTimeout(20_000);
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' });
  await page.getByLabel('Correo electrónico').fill(manifest.login.email);
  await page.getByLabel('Contraseña').fill(manifest.login.password);
  await page.getByRole('button', { name: 'Iniciar Sesión' }).click();
  await page.waitForURL(/\/admin\/?$/);
  const authToken = await page.evaluate(() => localStorage.getItem('auth_token'));
  assert.ok(authToken, 'login must retain the authentication token for the conflict writer');
  await page.evaluate((branchId) => {
    localStorage.setItem('admin_branch_id', branchId);
    localStorage.setItem('pos_branch_id', branchId);
  }, manifest.branch_id);

  await page.goto(`${baseUrl}/category-priorities`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Prioridades administrativas' }).waitFor();
  const consultationOrder = page.locator('.admin-catalog-order:not(.admin-catalog-print-order) .admin-catalog-order-list');
  const printOrder = page.locator('.admin-catalog-print-order .admin-catalog-order-list');
  const beforeConsultation = await consultationOrder.innerText();
  const beforePrint = await printOrder.innerText();
  const down = page.getByRole('button', { name: /Bajar / }).first();
  if (await down.isEnabled()) await down.click();
  await page.getByRole('button', { name: 'Guardar prioridades' }).click();
  await page.getByText('Prioridades administrativas guardadas.').waitFor();
  const savedConsultation = await consultationOrder.innerText();
  assert.notEqual(savedConsultation, beforeConsultation);
  assert.equal(await printOrder.innerText(), beforePrint);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Prioridades administrativas' }).waitFor();
  assert.equal(await consultationOrder.innerText(), savedConsultation);
  await page.evaluate(() => {
    window.__adminRetroPrintCalls = 0;
    window.print = () => {
      window.__adminRetroPrintCalls += 1;
    };
  });
  await page.getByRole('button', { name: 'Imprimir catálogo' }).click();
  assert.equal(await page.evaluate(() => window.__adminRetroPrintCalls), 1);
  await page.emulateMedia({ media: 'print' });
  const printCatalog = page.locator('.admin-catalog-print-catalog');
  const consultationCatalog = page.locator('.admin-catalog-catalog-view');
  assert.equal(await printCatalog.isVisible(), true);
  assert.equal(await consultationCatalog.isVisible(), false);
  const printCategoryNames = (await printOrder.locator('li > span:first-child').allInnerTexts()).map((text) => text.replace(/^\d+\.\s*/, '').trim());
  assert.deepEqual(await printCatalog.locator('.admin-catalog-print-group h3').allInnerTexts(), printCategoryNames);
  assert.ok((await printCatalog.locator('.admin-catalog-print-group li').allInnerTexts()).length > 0, 'print output contains ordered products');
  await page.emulateMedia({ media: 'screen' });

  await page.locator('.admin-catalog-order:not(.admin-catalog-print-order)').getByRole('button', { name: /Bajar / }).first().click();
  const draftAfterConcurrentEdit = await consultationOrder.innerText();
  const latestPriorities = await page.request.get(`${apiBaseUrl}/admin-catalog/category-priorities`, {
    headers: { Authorization: `Bearer ${authToken}` },
  });
  assert.equal(latestPriorities.ok(), true);
  const latestPayload = await latestPriorities.json();
  const conflictWriter = await page.request.put(`${apiBaseUrl}/admin-catalog/category-priorities`, {
    headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' },
    data: {
      expected_version: latestPayload.version,
      view_category_ids: latestPayload.view_order.map((category) => category.id),
      print_category_ids: latestPayload.print_order.map((category) => category.id),
    },
  });
  assert.equal(conflictWriter.ok(), true);
  await page.getByRole('button', { name: 'Guardar prioridades' }).click();
  await page.locator('.admin-catalog-message').waitFor();
  assert.doesNotMatch(await page.locator('.admin-catalog-message').innerText(), /guardadas/i);
  assert.equal(await consultationOrder.innerText(), draftAfterConcurrentEdit, 'version conflict preserves the administrative draft');

  await page.goto(`${baseUrl}/inventory/thresholds`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Umbrales de existencias' }).waitFor();
  await page.getByRole('button', { name: /Editar umbrales de/ }).first().click();
  await page.getByLabel('Mínimo').fill('1');
  await page.getByLabel('Máximo').fill('5');
  await page.getByRole('button', { name: 'Guardar umbrales' }).click();
  await page.getByText('Umbrales guardados. La existencia se conserva sin cambios.').waitFor();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Umbrales de existencias' }).waitFor();
  assert.match(await page.locator('.premium-table tbody').innerText(), /\b1\b/);
  assert.match(await page.locator('.premium-table tbody').innerText(), /\b5\b/);

  await page.goto(`${baseUrl}/inventory/items`, { waitUntil: 'domcontentloaded' });
  await page.getByTitle('Consultar recetas que usan este insumo').first().click();
  await page.getByText(/Recetas que usan /).waitFor();
  await page.getByRole('button', { name: 'Abrir receta' }).first().waitFor({ state: 'visible' });
  assert.ok(await page.getByRole('button', { name: 'Abrir receta' }).count() > 0);
  await page.getByRole('button', { name: 'Abrir receta' }).first().click();
  await page.waitForURL(/\/admin\/recipes\?/);

  await page.goto(`${baseUrl}/recipes/bulk`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Aplicar receta a varios productos' }).waitFor();
  await page.getByLabel('Alcance').selectOption(manifest.branch_id);
  await page.getByLabel('Unidad de rendimiento').selectOption(manifest.unit_id);
  const destinations = page.locator('input[type="checkbox"]');
  await destinations.nth(0).check();
  await destinations.nth(1).check();
  const itemSelector = page.locator('tbody select').first();
  await itemSelector.selectOption(manifest.item_id);
  await page.locator('tbody input').first().fill('1');
  await page.getByRole('button', { name: 'Ver diferencias' }).click();
  await page.getByRole('heading', { name: 'Diferencias revisadas' }).waitFor();
  await page.getByRole('button', { name: 'Confirmar lote versionado' }).click();
  await page.getByText(/Lote aplicado: 2 receta\(s\) versionada\(s\)/).waitFor();

  const [comboProductId, componentProductId] = manifest.product_ids;
  const catalogResponse = await page.request.get(`${apiBaseUrl}/catalog/products`, { headers: { Authorization: `Bearer ${authToken}` } });
  assert.equal(catalogResponse.ok(), true);
  const comboProduct = (await catalogResponse.json()).find((product) => product.id === comboProductId);
  assert.ok(comboProduct, 'fixture combo product must be present in the administrative catalog');
  await page.goto(`${baseUrl}/products`, { waitUntil: 'domcontentloaded' });
  const comboRow = page.locator('tr').filter({ hasText: comboProduct.name });
  await comboRow.getByTitle('Composición fija').click();
  await page.getByText(/Composición fija:/).waitFor();
  await page.getByLabel('Producto componente 1').selectOption(componentProductId);
  await page.getByLabel('Cantidad del componente 1').fill('1');
  await page.getByRole('button', { name: 'Guardar composición versionada' }).click();
  await page.getByText(/Composición versionada \(v1\)/).waitFor();
  await page.getByRole('dialog').getByRole('button', { name: 'Cerrar', exact: true }).last().click();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.locator('tr').filter({ hasText: comboProduct.name }).getByTitle('Composición fija').click();
  await page.getByText(/Composición fija:/).waitFor();
  await page.waitForFunction((expected) => document.querySelector('select[aria-label="Producto componente 1"]')?.value === expected, componentProductId);
  assert.equal(await page.getByLabel('Producto componente 1').inputValue(), componentProductId);
  assert.equal(await page.getByLabel('Cantidad del componente 1').inputValue(), '1');

  await page.getByLabel('Cantidad del componente 1').fill('2');
  const comboConflictWriter = await page.request.put(`${apiBaseUrl}/products/${comboProductId}/composition`, {
    headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json', 'Idempotency-Key': 'adminretro-e2e-combo-conflict-writer' },
    data: { branch_id: manifest.branch_id, expected_version: 1, components: [{ product_id: componentProductId, quantity: '1' }] },
  });
  assert.equal(comboConflictWriter.ok(), true);
  await page.getByRole('button', { name: 'Guardar composición versionada' }).click();
  const conflictMessage = page.getByText('La composición cambió en otra sesión. Tu borrador se conserva; recarga antes de volver a guardar.');
  await conflictMessage.waitFor();
  assert.equal(await page.getByLabel('Cantidad del componente 1').inputValue(), '2', 'composition conflict preserves the exact draft quantity');
  assert.equal(await page.getByRole('button', { name: 'Guardar composición versionada' }).isDisabled(), true);
  await page.getByRole('button', { name: 'Revisar versión vigente' }).click();
  await page.getByText('Versión revisada: v2.').waitFor();
  assert.equal(await page.getByLabel('Cantidad del componente 1').inputValue(), '2');
  await page.getByRole('button', { name: 'Guardar composición versionada' }).click();
  await page.getByText(/Composición versionada \(v3\)/).waitFor();
  assert.deepEqual(pageErrors, []);
  console.log('Admin retro API-to-UI E2E passed');
} finally {
  await browser.close();
}
