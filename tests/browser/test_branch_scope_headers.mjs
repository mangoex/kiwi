// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-branch-scope-headers-v1
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { corporateAdminSession } from '../fixtures/admin_session_fixture.mjs';

const { chromium } = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const adminUrl = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
const posUrl = process.env.BRANCH_SCOPE_POS_URL || 'http://127.0.0.1:3001/pos';
const expectV2Enabled = process.env.BRANCH_SCOPE_EXPECT_ENABLED === 'true';
const output = resolve('output/playwright/branch-scope-headers');
mkdirSync(output, { recursive: true });

const branches = [
  { id: '018f6f73-2d0a-74f0-8f1c-000000000001', name: 'Centro', code: 'CENTRO', status: 'active' },
  { id: '018f6f73-2d0a-74f0-8f1c-000000000002', name: 'Norte', code: 'NORTE', status: 'active' },
];

const posSession = (branchId) => ({
  user: { id: 'branch-scope-qa', email: 'qa@example.invalid', display_name: 'Administrador QA', status: 'active' },
  roles: [{ id: 'admin-role', name: 'Administrador', scope: 'organization', branch_id: null }],
  permissions: ['pos.operate', 'orders.create', 'branch.admin.access', 'pos.branch.select'],
  admin_capabilities: { 'branch.admin.access': true },
  scope: { level: 'organization', assigned_branch_id: branches[0].id, allowed_branch_ids: branches.map((branch) => branch.id) },
  active_branch: {
    ...branches.find((branch) => branch.id === branchId),
    timezone: 'America/Mazatlan',
    pos_catalog_visuals_enabled: true,
    business_unit: { id: 'business-unit', name: 'QA', code: 'QA', unit_type: 'store' },
    legal_entity: { id: 'legal-entity', name: 'QA' },
    warehouse: null,
  },
  allowed_branches: branches,
});

const branchAdminSession = () => {
  const session = corporateAdminSession({ id: 'branch-scope-local-qa', display_name: 'Jefe QA' }, branches[0].id, branches);
  return {
    ...session,
    roles: [{ id: 'branch-qa', name: 'Jefe de sucursal', scope: 'branch', branch_id: branches[0].id }],
    scope: { level: 'branch', assigned_branch_id: branches[0].id, allowed_branch_ids: [branches[0].id] },
    allowed_branches: [branches[0]],
  };
};

const browser = await chromium.launch({
  headless: true,
  ...(process.env.ADMINRETRO_CHROME_PATH ? { executablePath: process.env.ADMINRETRO_CHROME_PATH } : {}),
});

try {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }]) {
    const label = `${viewport.width}x${viewport.height}`;
    const admin = await browser.newPage({ viewport });
    await admin.addInitScript(() => {
      localStorage.setItem('auth_token', 'branch-scope-admin-token');
      localStorage.setItem('user', JSON.stringify({ id: 'branch-scope-qa', display_name: 'Administrador QA' }));
    });
    await admin.route('**/api/v1/**', async (route) => {
      const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
      if (path === '/auth/session') {
        return route.fulfill({ json: corporateAdminSession({ id: 'branch-scope-qa', display_name: 'Administrador QA' }, branches[0].id, branches) });
      }
      if (path === '/dashboard/overview') {
        return route.fulfill({ json: { total_revenue_cents: 0, total_orders: 0, average_ticket_cents: 0, total_products: 0, order_types: {}, recent_transactions: [], activity_chart: [], recent_notifications: [], popular_categories: [] } });
      }
      return route.fulfill({ json: [] });
    });
    await admin.goto(`${adminUrl}/`, { waitUntil: 'domcontentloaded' });
    const dashboardScope = admin.getByLabel('Sucursal del panel');
    await dashboardScope.waitFor();
    assert.equal(await dashboardScope.inputValue(), '');
    assert.equal(await dashboardScope.getByRole('option', { name: 'Todas las sucursales' }).count(), 1);
    assert.equal(await admin.locator('.admin-dashboard-filters select').count(), 1, 'Only the month filter remains in the dashboard');
    const topbar = await admin.locator('.admin-topbar').boundingBox();
    const indicator = await admin.locator('.configuration-scope-indicator').boundingBox();
    assert.ok(topbar && indicator && indicator.y - (topbar.y + topbar.height) >= 16, `Admin content gap must be >=16px at ${label}`);

    const branchAdmin = await browser.newPage({ viewport });
    await branchAdmin.addInitScript(() => {
      localStorage.setItem('auth_token', 'branch-scope-local-token');
      localStorage.setItem('user', JSON.stringify({ id: 'branch-scope-local-qa', display_name: 'Jefe QA' }));
    });
    await branchAdmin.route('**/api/v1/**', async (route) => {
      const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
      if (path === '/auth/session') return route.fulfill({ json: branchAdminSession() });
      if (path === '/dashboard/overview') {
        return route.fulfill({ json: { total_revenue_cents: 0, total_orders: 0, average_ticket_cents: 0, total_products: 0, order_types: {}, recent_transactions: [], activity_chart: [], recent_notifications: [], popular_categories: [] } });
      }
      return route.fulfill({ json: [] });
    });
    await branchAdmin.goto(`${adminUrl}/`, { waitUntil: 'domcontentloaded' });
    assert.equal(await branchAdmin.getByLabel('Sucursal del panel').count(), 0, 'Branch-scoped actors cannot select an organization dashboard');
    await branchAdmin.locator('.admin-active-branch-label').getByText('Centro', { exact: true }).waitFor();
    await branchAdmin.getByText('Panel de Centro', { exact: true }).waitFor();
    await branchAdmin.close();

    await dashboardScope.selectOption(branches[1].id);
    await admin.getByText('Panel de Norte', { exact: true }).waitFor();
    await admin.getByRole('button', { name: 'Productos', exact: true }).click();
    if (!expectV2Enabled) {
      assert.equal(await admin.getByLabel('Alcance de configuración').count(), 0);
      await admin.locator('.admin-active-branch-label').getByText('Centro', { exact: true }).waitFor();
      await admin.screenshot({ path: `${output}/admin-default-off-${label}.png`, fullPage: true });
      await admin.close();

      const pos = await browser.newPage({ viewport });
      await pos.addInitScript((branchId) => {
        localStorage.setItem('auth_token', 'branch-scope-pos-token');
        localStorage.setItem('pos_branch_id', branchId);
        localStorage.setItem('user', JSON.stringify({ id: 'branch-scope-qa', display_name: 'Administrador QA' }));
      }, branches[0].id);
      await pos.route('**/api/v1/**', async (route) => {
        const url = new URL(route.request().url());
        const path = url.pathname.replace('/api/v1', '');
        if (path === '/auth/session') return route.fulfill({ json: posSession(branches[0].id) });
        return route.fulfill({ json: [] });
      });
      await pos.goto(`${posUrl}/`, { waitUntil: 'domcontentloaded' });
      assert.equal(await pos.getByLabel('Sucursal de trabajo').count(), 0);
      await pos.getByText(/Centro/).first().waitFor();
      await pos.screenshot({ path: `${output}/pos-default-off-${label}.png`, fullPage: true });
      await pos.close();
      continue;
    }
    const adminScope = admin.getByLabel('Alcance de configuración');
    await adminScope.waitFor();
    assert.equal(await adminScope.inputValue(), '', 'Configuration scope stays independent from dashboard filter');

    admin.once('dialog', async (dialog) => {
      assert.match(dialog.message(), /sólo a Norte/);
      await dialog.dismiss();
    });
    await adminScope.selectOption(branches[1].id);
    assert.equal(await adminScope.inputValue(), '', 'Cancel keeps organization scope');

    admin.once('dialog', async (dialog) => { await dialog.accept(); });
    await adminScope.selectOption(branches[1].id);
    await admin.getByText('Sólo Norte', { exact: true }).waitFor();
    await admin.getByText('Configuración local todavía no disponible', { exact: true }).waitFor();
    await admin.screenshot({ path: `${output}/admin-${label}.png`, fullPage: true });
    await admin.close();

    const pos = await browser.newPage({ viewport });
    await pos.addInitScript((branchId) => {
      localStorage.setItem('auth_token', 'branch-scope-pos-token');
      localStorage.setItem('pos_branch_id', branchId);
      localStorage.setItem('user', JSON.stringify({ id: 'branch-scope-qa', display_name: 'Administrador QA' }));
    }, branches[0].id);
    await pos.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname.replace('/api/v1', '');
      if (path === '/auth/session') {
        return route.fulfill({ json: posSession(url.searchParams.get('branch_id') || branches[0].id) });
      }
      return route.fulfill({ json: [] });
    });
    await pos.goto(`${posUrl}/`, { waitUntil: 'domcontentloaded' });
    const posScope = pos.getByLabel('Sucursal de trabajo');
    await posScope.waitFor();
    assert.equal(await posScope.inputValue(), branches[0].id);
    const posHeader = await pos.locator('.pos-sale-header').boundingBox();
    assert.ok(posHeader && posHeader.height >= 78, `POS header height must be >=78px at ${label}`);
    assert.ok(await posScope.isVisible(), `POS selector must remain visible at ${label}`);
    pos.once('dialog', async (dialog) => {
      assert.match(dialog.message(), /operación del POS a Norte/);
      await dialog.accept();
    });
    await posScope.selectOption(branches[1].id);
    await pos.waitForFunction((branchId) => document.querySelector('[aria-label="Sucursal de trabajo"]')?.value === branchId, branches[1].id);
    await pos.screenshot({ path: `${output}/pos-${label}.png`, fullPage: true });
    await pos.close();
  }
  console.log('Admin/POS branch selectors and header spacing passed at 1440x900 and 1024x768.');
} finally {
  await browser.close();
}
