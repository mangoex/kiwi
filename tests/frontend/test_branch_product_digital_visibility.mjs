import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const admin = readFileSync(
  'apps/admin-web/src/features/catalog/CatalogAdministration.tsx',
  'utf8',
);
const catalogHub = readFileSync('apps/admin-web/src/features/hubs/CatalogHub.tsx', 'utf8');
const subNav = readFileSync('apps/admin-web/src/components/CategorySubNav.tsx', 'utf8');
const app = readFileSync('apps/admin-web/src/App.tsx', 'utf8');
const access = readFileSync('packages/api-client/src/adminAccess.ts', 'utf8');
const recipes = readFileSync('apps/admin-web/src/features/recipes/RecipesWorkspace.tsx', 'utf8');
const bulkRecipes = readFileSync('apps/admin-web/src/features/admin-catalog/BulkRecipeWorkspace.tsx', 'utf8');
const combo = readFileSync('apps/admin-web/src/features/catalog/ComboCompositionModal.tsx', 'utf8');
const mobileApi = readFileSync('apps/mobile-web/src/api.ts', 'utf8');
const mobileApp = readFileSync('apps/mobile-web/src/App.tsx', 'utf8');

assert.match(admin, /show_in_digital_menu\?:\s*boolean/);
assert.match(admin, /digital-menu-visibility/);
assert.match(admin, /JSON\.stringify\(\{\s*visible\s*\}\)/);
assert.match(admin, /type="checkbox"/);
assert.match(admin, /checked=\{row\.show_in_digital_menu !== false\}/);
assert.match(admin, /menú digital/);
assert.match(admin, /aria-label=\{`Mostrar \$\{row\.name\} en menú digital`\}/);
assert.match(admin, /Todas las sucursales actuales/);
assert.match(admin, /all-active-summary/);
assert.match(admin, /digital-menu-visibility\/all-active/);
assert.match(admin, /availability\/all-active/);
assert.match(admin, /availability_summary/);
assert.match(admin, /digital_menu_summary/);
assert.match(admin, /window\.confirm/);
assert.match(admin, /session\.allowed_branches/);
assert.match(admin, /session\.scope\.level\s*===\s*'organization'\s*\?\s*'all-active'/);
assert.match(admin, /onMutate:\s*async/);
assert.match(admin, /availability-product-card/);
assert.match(admin, /export function AvailabilityAdministration/);
assert.doesNotMatch(admin, /kind === 'products' \|\| branchManage/);
assert.match(admin, /return <Navigate to="\/availability" replace \/>/);

assert.match(catalogHub, /title:\s*'Disponibilidad'/);
assert.match(catalogHub, /path:\s*'\/availability'/);
assert.match(subNav, /path:\s*'\/availability',\s*label:\s*'Disponibilidad'/);
assert.match(app, /path="availability" element=\{<AvailabilityAdministration \/>\}/);
assert.match(access, /'\/availability':\s*\[\['branch\.admin\.access'\]\]/);
assert.match(access, /'\/products':\s*\[\['catalog\.manage'\], \['recipes\.manage'\], \['branch\.admin\.access'\]\]/);
assert.match(access, /products:\s*'\/availability'/);

for (const source of [recipes, bulkRecipes, combo]) {
  assert.doesNotMatch(source, /useState<string \| null>\(\(\) => resolveBranchId\(\) \|\| null\)/);
}

assert.doesNotMatch(mobileApi, /BACKUP_CATALOG/);
assert.match(mobileApi, /return \{ products: \[\], categories: DEFAULT_CATEGORIES \}/);
assert.match(mobileApi, /cache:\s*'no-store'/);
assert.match(mobileApp, /document\.addEventListener\('visibilitychange'/);
assert.match(mobileApp, /window\.addEventListener\('focus'/);

console.log('Branch product digital visibility semantic checks passed');
