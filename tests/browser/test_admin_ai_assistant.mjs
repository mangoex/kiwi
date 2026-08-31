import assert from 'node:assert/strict';
const playwrightImport = process.env.AIA002_PLAYWRIGHT_IMPORT || 'playwright';
const { chromium } = await import(playwrightImport);

const baseUrl = process.env.AIA002_BASE_URL || 'http://127.0.0.1:4173/admin/products';
const branchId = '018f6f73-2d0a-74f0-8f1c-000000000003';
const productId = '018f6f73-2d0a-74f0-8f1c-000000000111';
const proposalId = '018f6f73-2d0a-74f0-8f1c-000000000099';
const outputDir = process.env.AIA002_OUTPUT_DIR
  || `${process.cwd()}/docs/implementation-reports/assets`;

const readyProposal = {
  id: proposalId,
  status: 'READY_FOR_REVIEW',
  payload: {
    answer: 'Preparé una propuesta revisable para el producto 1001.',
    sources: ['PRD-FR-010', 'SDD §43'],
    questions: [],
    warnings: ['El cambio sólo se aplicará después de tu aceptación.'],
    change_set: [{
      kind: 'product.update',
      target_id: productId,
      current: { name: 'Hamburguesa Kiwi', sku: '1001', price_cents: 12500 },
      proposed: { name: 'Hamburguesa Especial Kiwi' },
      review_path: '/products?search=1001',
      evidence_fields: ['target_id', 'name'],
    }],
  },
  result: null,
};

const clarificationProposal = {
  id: '018f6f73-2d0a-74f0-8f1c-000000000098',
  status: 'DRAFT',
  payload: {
    answer: '“Precio” no identifica una única autoridad para insumos.',
    sources: ['PRD-FR-093', 'PRD-FR-094'],
    questions: ['¿Quieres precio de compra o costo promedio?'],
    warnings: ['La consulta necesita una aclaración; no se realizó ningún cambio.'],
    change_set: [],
    clarification: {
      kind: 'inventory_price_authority',
      turn: 1,
      options: [
        { id: 'missing_purchase_price', label: 'Precio de compra' },
        { id: 'missing_average_cost', label: 'Costo promedio' },
      ],
    },
  },
  result: null,
};

const product = {
  id: productId,
  name: 'Hamburguesa Kiwi',
  sku: '1001',
  category_name: 'Alimentos',
  price_cents: 12500,
  station: 'kitchen',
  status: 'active',
  catalog_scope: 'organization',
  source_branch_id: null,
};

async function verifyViewport(browser, name, viewport) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  let status = 'READY_FOR_REVIEW';
  let reviewHeader = '';
  let delayClarification = false;

  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));

  await page.addInitScript(({ branchId: activeBranchId }) => {
    const avatar = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="80" height="80"%3E%3Crect width="80" height="80" rx="40" fill="%2322c55e"/%3E%3Ccircle cx="40" cy="31" r="14" fill="white"/%3E%3Cpath d="M16 72c2-18 15-27 24-27s22 9 24 27" fill="white"/%3E%3C/svg%3E';
    localStorage.setItem('auth_token', 'synthetic-aia002-token');
    localStorage.setItem('admin_branch_id', activeBranchId);
    localStorage.setItem('user_avatar_aia002-admin', avatar);
    localStorage.setItem('user', JSON.stringify({
      id: 'aia002-admin',
      display_name: 'Administradora QA',
      email: 'qa@example.invalid',
      is_superadmin: true,
      assigned_branch_id: activeBranchId,
      roles: ['Administrador'],
      permissions: ['catalog.manage', 'recipes.manage', 'reports.sales.read'],
    }));
  }, { branchId });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '');
    if (request.method() === 'GET' && path === '/branches') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ id: branchId, name: 'Centro', status: 'active' }]) });
    }
    if (request.method() === 'GET' && path === '/catalog/products') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([product]) });
    }
    if (request.method() === 'POST' && path === '/admin-ai/proposals') {
      const body = request.postDataJSON();
      assert.equal(body.branch_id, branchId);
      if (body.prompt.includes('insumos no tienen precio')) {
        if (delayClarification) await new Promise((resolve) => setTimeout(resolve, 400));
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(clarificationProposal) });
      }
      assert.match(body.prompt, /Hamburguesa Kiwi/);
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(readyProposal) });
    }
    if (request.method() === 'GET' && path === `/admin-ai/proposals/${proposalId}`) {
      const response = status === 'APPLIED'
        ? { ...readyProposal, status, result: { id: productId, name: 'Hamburguesa Especial Kiwi' } }
        : readyProposal;
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(response) });
    }
    if (request.method() === 'POST' && path === `/admin-ai/proposals/${proposalId}/review`) {
      reviewHeader = request.headers()['idempotency-key'] || '';
      assert.match(reviewHeader, new RegExp(`^admin-ai-review-${proposalId}-`));
      assert.deepEqual(request.postDataJSON(), { accept: true });
      status = 'APPLIED';
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...readyProposal, status, result: { id: productId, name: 'Hamburguesa Especial Kiwi' } }),
      });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.goto(baseUrl, { waitUntil: 'networkidle' });
  assert.ok((await page.locator('body').innerText()).trim().length > 100);
  assert.equal(await page.locator('vite-error-overlay, .vite-error-overlay, #webpack-dev-server-client-overlay').count(), 0);
  await page.getByRole('heading', { name: 'Productos y catálogo' }).waitFor();
  await page.getByTitle('Editar mi perfil').waitFor();

  await page.getByRole('button', { name: 'Abrir asistente de configuración' }).click();
  await page.getByLabel('Consulta para asistente de configuración').fill('¿Qué insumos no tienen precio?');
  await page.getByRole('button', { name: 'Consultar' }).click();
  await page.getByRole('heading', { name: 'Aclaremos tu consulta' }).waitFor();
  await page.getByRole('button', { name: 'Cerrar' }).click();
  await page.getByRole('button', { name: 'Abrir asistente de configuración' }).click();
  await page.getByLabel('Consulta para asistente de configuración').waitFor();
  assert.equal(await page.getByRole('heading', { name: 'Aclaremos tu consulta' }).count(), 0);

  delayClarification = true;
  await page.getByLabel('Consulta para asistente de configuración').fill('¿Qué insumos no tienen precio?');
  await page.getByRole('button', { name: 'Consultar' }).click();
  await page.getByRole('button', { name: 'Cerrar' }).click();
  await page.waitForTimeout(600);
  await page.getByRole('button', { name: 'Abrir asistente de configuración' }).click();
  await page.getByLabel('Consulta para asistente de configuración').waitFor();
  assert.equal(await page.getByRole('heading', { name: 'Aclaremos tu consulta' }).count(), 0);
  await page.getByRole('button', { name: 'Cerrar' }).click();

  await page.getByRole('button', { name: 'Abrir asistente de configuración' }).click();
  await page.getByRole('heading', { name: 'Asistente de configuración' }).waitFor();
  await page.getByLabel('Consulta para asistente de configuración').fill('Actualiza Hamburguesa Kiwi a Hamburguesa Especial Kiwi');
  await page.getByRole('button', { name: 'Consultar' }).click();
  await page.getByText('Propuesta lista para revisión').waitFor();
  await page.getByRole('button', { name: 'Revisar configuración' }).click();

  await page.getByRole('heading', { name: 'Revisar configuración propuesta' }).waitFor();
  await page.getByRole('heading', { name: 'Configuración actual' }).waitFor();
  await page.getByRole('heading', { name: 'Configuración propuesta', exact: true }).waitFor();
  assert.match(page.url(), new RegExp(`admin_ai_proposal=${proposalId}`));
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${outputDir}/AIA-002A-${name}-review.png`, fullPage: true });

  await page.getByRole('button', { name: 'Aceptar configuración' }).click();
  await page.getByText('APPLIED', { exact: true }).waitFor();
  assert.ok(reviewHeader);
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${outputDir}/AIA-002A-${name}-applied.png`, fullPage: true });

  assert.deepEqual(pageErrors, []);
  assert.deepEqual(consoleErrors, []);
  await context.close();
  return { name, viewport, idempotencyHeader: reviewHeader, pageErrors, consoleErrors };
}

const browser = await chromium.launch({
  headless: true,
  ...(process.env.AIA002_CHROME_PATH
    ? { executablePath: process.env.AIA002_CHROME_PATH }
    : {}),
});
try {
  const results = [];
  results.push(await verifyViewport(browser, 'desktop', { width: 1440, height: 1000 }));
  results.push(await verifyViewport(browser, 'mobile', { width: 390, height: 844 }));
  console.log(JSON.stringify({ ok: true, results }, null, 2));
} finally {
  await browser.close();
}
