import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8');

const adminSession = read('apps/admin-web/src/lib/adminSession.tsx');
const adminLayout = read('apps/admin-web/src/components/AdminLayout.tsx');
const overview = read('apps/admin-web/src/features/dashboard/Overview.tsx');
const adminStyles = read('apps/admin-web/src/App.css');
const posSession = read('apps/pos-web/src/session.ts');
const pointOfSale = read('apps/pos-web/src/features/pos/PointOfSale.tsx');
const settings = read('apps/pos-web/src/features/settings/Settings.tsx');
const posStyles = read('apps/pos-web/src/App.css');
const posLayout = read('apps/pos-web/src/components/PosLayout.tsx');
const posApp = read('apps/pos-web/src/App.tsx');

assert.match(adminSession, /kind:\s*'organization',\s*branch_id:\s*null/);
assert.match(adminSession, /selectConfigurationScope/);
assert.match(adminSession, /branchId === null[\s\S]*session\.scope\.level !== 'organization'[\s\S]*permission_denied/);
assert.doesNotMatch(adminSession, /localStorage\.getItem\('admin_configuration_scope'/);

assert.match(adminLayout, /'Sucursal del panel' : 'Alcance de configuración'/);
assert.match(adminLayout, /VITE_BRANCH_SCOPE_V2_ENABLED/);
assert.match(adminLayout, /VITE_BRANCH_SCOPE_V2_ENABLED\s*===\s*'true'/);
assert.match(adminLayout, /allowDashboardScopeSelection\s*=\s*isDashboard\s*&&\s*session\.scope\.level\s*===\s*'organization'/);
assert.match(adminLayout, /allowDashboardScopeSelection\s*\|\|\s*\(!isDashboard\s*&&\s*allowConfigurationScopeSelection\)/);
assert.match(adminLayout, /<option value="">Todas las sucursales<\/option>/);
assert.match(adminLayout, /Los cambios se aplicarán sólo a/);
assert.match(adminLayout, /configuration-scope-indicator/);
assert.match(adminLayout, /configuration-scope-unsupported/);

assert.doesNotMatch(overview, /<option value="">Todas las sucursales<\/option>/);
assert.doesNotMatch(overview, /fetchApi<Branch\[]>\('\/branches'\)/);
assert.match(overview, /dashboardBranchId/);
assert.doesNotMatch(overview, /configurationScope/);
assert.match(overview, /new AbortController\(\)/);

assert.match(adminStyles, /\.admin-content\s*\{[^}]*padding:\s*20px 32px 32px/s);
assert.match(adminStyles, /\.configuration-scope-indicator/);

assert.match(posSession, /allowed_branches:\s*\{/);
assert.match(posSession, /if \(!confirmWorkspaceNavigation\(\)\) return false/);
assert.match(posSession, /permissions\.includes\('pos\.branch\.select'\)/);
assert.match(posSession, /applySession\(nextSession\);\s*return true/s);
assert.match(pointOfSale, /aria-label="Sucursal de trabajo"/);
assert.doesNotMatch(pointOfSale, /VITE_BRANCH_SCOPE_V2_ENABLED/);
assert.match(pointOfSale, /session\.scope\.can_select_branch/);
assert.match(pointOfSale, /!loadOperationalOrderConfig\(\)/);
assert.match(pointOfSale, /await selectBranch\(targetBranchId\)/);
assert.match(pointOfSale, /Cambiarás la operación del POS a/);
assert.doesNotMatch(settings, /VITE_BRANCH_SCOPE_V2_ENABLED/);
assert.match(settings, /session\?\.scope\.can_select_branch/);
assert.match(posSession, /\/auth\/branch-selections/);
assert.doesNotMatch(posSession, /\/auth\/session\?branch_id/);
assert.match(posLayout, /session\?\.pos_modules/);
for (const module of ['uber_eats', 'didi_food', 'rappi', 'invoicing']) {
  assert.match(posLayout, new RegExp(`posModules\\.${module}`));
  assert.match(posApp, new RegExp(`module="${module}"`));
}
assert.match(posStyles, /\.pos-sale-header\s*\{[^}]*min-height:\s*78px[^}]*padding:\s*10px 22px/s);

console.log('Branch scope header contracts verified.');
