import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync('apps/admin-web/src/App.tsx', 'utf8');
const categoryNav = readFileSync('apps/admin-web/src/components/CategorySubNav.tsx', 'utf8');
const priorities = readFileSync('apps/admin-web/src/features/admin-catalog/CategoryPriorities.tsx', 'utf8');
const bulk = readFileSync('apps/admin-web/src/features/admin-catalog/BulkRecipeWorkspace.tsx', 'utf8');
const thresholds = readFileSync('apps/admin-web/src/features/admin-catalog/StockThresholds.tsx', 'utf8');
const usages = readFileSync('apps/admin-web/src/features/admin-catalog/RecipeUsagesModal.tsx', 'utf8');
const combos = readFileSync('apps/admin-web/src/features/catalog/ComboCompositionModal.tsx', 'utf8');
const products = readFileSync('apps/admin-web/src/features/catalog/ProductsList.tsx', 'utf8');
const login = readFileSync('apps/admin-web/src/features/auth/Login.tsx', 'utf8');

assert.match(app, /path="category-priorities"/);
assert.match(app, /path="recipes\/bulk"/);
assert.match(app, /path="inventory\/thresholds"/);
assert.match(categoryNav, /\/category-priorities/);
assert.match(categoryNav, /\/recipes\/bulk/);
assert.match(categoryNav, /\/inventory\/thresholds/);

assert.match(priorities, /\/admin-catalog\/category-priorities/);
assert.match(priorities, /expected_version/);
assert.match(priorities, /view_category_ids/);
assert.match(priorities, /print_category_ids/);
assert.match(priorities, /window\.print\(\)/);
assert.match(priorities, /admin-catalog-catalog-view/);
assert.match(priorities, /admin-catalog-print-catalog/);
assert.doesNotMatch(priorities, /drag/i);

assert.match(bulk, /\/admin-catalog\/recipes\/bulk-preview/);
assert.match(bulk, /\/admin-catalog\/recipes\/bulk-apply/);
assert.match(bulk, /'Idempotency-Key'/);
assert.match(bulk, /preview_fingerprint/);
assert.match(bulk, /expected_active_recipe_ids/);
assert.match(bulk, /difference\.changed/);
assert.match(bulk, /current_yield_quantity/);
assert.match(bulk, /componentLabel/);
assert.match(bulk, /Antes/);
assert.match(bulk, /Después/);
assert.doesNotMatch(bulk, /toFixed\(|parseFloat\(|Number\(/);

assert.match(thresholds, /\/admin-catalog\/stock-thresholds/);
assert.match(thresholds, /expected_version/);
assert.match(thresholds, /quantity_on_hand/);
assert.doesNotMatch(thresholds, /parseFloat\(|Number\(/);

assert.match(usages, /\/admin-catalog\/items\//);
assert.match(usages, /recipe-usages/);
assert.match(usages, /Abrir receta/);
assert.match(usages, /product_name/);
assert.match(usages, /product_sku/);
assert.match(usages, /unit_code/);

assert.match(products, /ComboCompositionModal/);
assert.match(products, /Composición fija/);
assert.match(combos, /\/products\/\$\{product\.id\}\/composition/);
assert.match(combos, /'Idempotency-Key'/);
assert.match(combos, /expected_version/);
assert.match(combos, /branch_id/);
assert.match(combos, /\^\[1-9\]\\d\*\$/);
assert.match(combos, /hydrateWholeQuantity/);
assert.match(combos, /setQueryData<CompositionView>/);
assert.match(combos, /\['catalog', 'products', 'combo-composition', branchId\]/);
assert.match(combos, /fetchApi\('\/catalog\/products'\)/);
assert.match(combos, /catalog_scope === 'organization'/);
assert.match(combos, /candidate\.source_branch_id === branchId/);
assert.match(combos, /setRequiresReview\(false\)/);
assert.doesNotMatch(combos, /parseFloat\(|Number\(/);
assert.match(login, /htmlFor="admin-login-email"/);
assert.match(login, /id="admin-login-password"/);

console.log('Admin catalog tools semantic contract passed');
