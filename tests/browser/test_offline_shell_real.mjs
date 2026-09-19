import assert from 'node:assert/strict';

const { chromium } = await import(process.env.OFFLINE_PLAYWRIGHT_IMPORT || 'playwright');
const branchId = '11111111-1111-4111-8111-111111111111';
const deviceId = '22222222-2222-4222-8222-222222222222';
const profile = {
  user: { id: 'u', email: 'qa@example.invalid', display_name: 'QA', status: 'active' },
  roles: [], permissions: ['pos.operate', 'orders.create', 'orders.read', 'kds.tasks.operate'],
  scope: { level: 'branch', assigned_branch_id: branchId, allowed_branch_ids: [branchId] },
  active_branch: { id: branchId, name: 'Sucursal QA', code: 'QA', timezone: 'UTC', status: 'active',
    business_unit: { id: 'bu', name: 'QA', code: 'QA', unit_type: 'store' },
    legal_entity: { id: 'le', name: 'QA' }, warehouse: null },
};

async function verify({ baseUrl, basePath, title, kds }) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await page.addInitScript(({ branchId, deviceId }) => {
      localStorage.setItem('auth_token', 'synthetic-token');
      localStorage.setItem('pos_operational_orders_enabled', 'true');
      localStorage.setItem('pos_operational_orders_branch_id', branchId);
      localStorage.setItem('pos_operational_orders_device_id', deviceId);
      localStorage.setItem('pos_operational_orders_gateway_url', 'https://gateway.branch.example');
      sessionStorage.setItem('pos_offline_order_grant_v3', 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx');
      sessionStorage.setItem('pos_offline_order_grant_v3_expires_at', new Date(Date.now() + 600_000).toISOString());
      sessionStorage.setItem('pos_offline_order_grant_v3_branch_id', branchId);
      sessionStorage.setItem('pos_offline_order_grant_v3_device_id', deviceId);
      sessionStorage.setItem('pos_offline_order_grant_v3_gateway_url', 'https://gateway.branch.example');
    }, { branchId, deviceId });
    await page.route('**/api/v1/**', async (route) => {
      if (kds) return route.fulfill({ json: { permissions: ['kds.tasks.operate'], active_branch: { id: branchId, name: 'Sucursal QA' } } });
      return route.fulfill({ json: { user: { id: 'u', email: 'qa@example.invalid', display_name: 'QA', status: 'active' }, roles: [], permissions: ['orders.create'], scope: { level: 'branch', assigned_branch_id: branchId, allowed_branch_ids: [branchId] }, active_branch: { id: branchId, name: 'Sucursal QA', code: 'QA', timezone: 'UTC', status: 'active', business_unit: { id: 'bu', name: 'QA', code: 'QA', unit_type: 'store' }, legal_entity: { id: 'le', name: 'QA' }, warehouse: null } } });
    });
    await page.route('https://gateway.branch.example/**', async route => {
      assert.match(route.request().headers().authorization || '', /^Offline /);
      const path = new URL(route.request().url()).pathname;
      return route.fulfill({ json: path.endsWith('/auth/session') ? profile : [] });
    });
    await page.goto(baseUrl, { waitUntil: 'networkidle' });
    const rendered = () => kds ? page.getByText(title).waitFor({timeout: 15_000})
      : page.getByPlaceholder('Buscar producto…').waitFor({timeout: 15_000});
    await rendered();
    await page.evaluate(() => navigator.serviceWorker.ready);
    if (!await page.evaluate(() => Boolean(navigator.serviceWorker.controller))) await page.reload({ waitUntil: 'networkidle' });
    assert.equal(await page.evaluate(() => Boolean(navigator.serviceWorker.controller)), true, `${title} worker controls page`);
    await page.waitForTimeout(500);
    const cacheState = await page.evaluate(async (basePath) => {
      const result = [];
      for (const name of await caches.keys()) {
        const cache = await caches.open(name);
        const keys = await cache.keys();
        result.push({ name, api: Boolean(await cache.match('/api/v1/auth/session')), assets: keys.filter((request) => request.url.includes(`${basePath}assets/`)).length });
      }
      return result;
    }, basePath);
    assert.equal(cacheState.some((entry) => entry.api), false, `${title} does not cache auth API`);
    assert.equal(cacheState.some((entry) => entry.assets > 0), true, `${title} precaches loaded assets`);
    // Simulate loss of cloud/WAN while retaining the branch LAN. Routes are deliberately
    // installed after the precache; a controlled service worker serves shell assets before
    // Playwright routing sees a network request.
    let cloudAttempts = 0;
    await page.route('**/api/v1/**', async route => {
      if (route.request().url().startsWith('https://gateway.branch.example')) return route.fallback();
      const request = route.request();
      const path = new URL(request.url()).pathname;
      // External-channel badges are outside the offline capability. Their failed
      // GETs may continue; session/core reads and every write must stay local.
      if (request.method() !== 'GET' || /\/(auth\/session|catalog\/products|categories|kds\/tasks)$/.test(path)) cloudAttempts++;
      return route.abort('internetdisconnected');
    });
    await context.setOffline(true);
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 15_000 });
    await rendered();
    assert.equal(cloudAttempts, 0, 'Core offline bootstrap must not contact cloud');
    console.log(`${title} disconnected cloud shell reload passed`);
  } finally {
    await browser.close();
  }
}

await verify({ baseUrl: 'http://127.0.0.1:4175/pos/', basePath: '/pos/', title: 'Punto de Venta', kds: false });
if (process.env.OFFLINE_SHELL_POS_ONLY !== '1') {
  await verify({ baseUrl: 'http://127.0.0.1:4176/kds/', basePath: '/kds/', title: 'Sistema KDS de Cocina', kds: true });
}
