import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const pos = readFileSync(
  join(root, 'apps/pos-web/src/features/pos/PointOfSale.tsx'),
  'utf8',
);
const posDashboard = readFileSync(
  join(root, 'apps/pos-web/src/features/dashboard/DashboardOverview.tsx'),
  'utf8',
);
const adminDashboard = readFileSync(
  join(root, 'apps/admin-web/src/features/dashboard/Overview.tsx'),
  'utf8',
);
const history = readFileSync(
  join(root, 'apps/pos-web/src/features/history/History.tsx'),
  'utf8',
);
const transfers = readFileSync(
  join(root, 'apps/admin-web/src/features/inventory/TransferList.tsx'),
  'utf8',
);
const physicalCounts = readFileSync(
  join(root, 'apps/admin-web/src/features/inventory/PhysicalCountList.tsx'),
  'utf8',
);
const recipeManager = readFileSync(
  join(root, 'apps/admin-web/src/features/catalog/RecipeManager.tsx'),
  'utf8',
);

assert.match(pos, /fetchApi<OrderQuote>\('\/orders\/quote'/);
assert.match(pos, /'\/orders\/adjustments\/authorize'/);
assert.match(pos, /tax_cents: number \| null/);
assert.match(pos, /lines: buildOrderLines\(cart\)/);
assert.match(pos, /quoteState !== 'ready'/);
assert.match(pos, /No determinado/);
assert.doesNotMatch(pos, /1\.16/);
assert.doesNotMatch(pos, /cartSubtotalCents|cartLineTotalCents/);
assert.match(pos, /effectiveCourtesyCents = orderQuote\?\.adjustment_cents \?\? 0/);
assert.doesNotMatch(pos, /Math\.round\(\(subtotalCents/);
assert.doesNotMatch(pos, /IVA \(16%/);
assert.match(history, /formatCurrency\(line\.unit_price_cents\)/);
assert.doesNotMatch(history, /line_total_cents\s*\/\s*line\.quantity/);
assert.doesNotMatch(transfers, /lines\.reduce/);
assert.doesNotMatch(physicalCounts, /lines\.reduce/);
assert.match(recipeManager, /component\.waste_rate/);
assert.doesNotMatch(recipeManager, /waste_rate[^\n]*\*\s*100/);
assert.doesNotMatch(recipeManager, /net_quantity[^\n]*\/\s*\(1\s*-\s*waste/);

for (const dashboard of [posDashboard, adminDashboard]) {
  assert.match(dashboard, /average_ticket_cents/);
  assert.doesNotMatch(dashboard, /total_revenue_cents\s*\/\s*data\.total_orders/);
  assert.doesNotMatch(dashboard, /totalRevenue\s*\/\s*totalOrders/);
}
assert.match(adminDashboard, /category\.share_bps/);
assert.doesNotMatch(adminDashboard, /total_orders \* 0\.(?:52|31|83)/);
assert.doesNotMatch(adminDashboard, /\(index \+ 1\) \/ topCategoryTotal/);
