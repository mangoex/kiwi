import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const purchases = readFileSync('apps/admin-web/src/features/purchasing/PurchasesList.tsx', 'utf8');
assert.match(purchases, /Compra corporativa/, 'Compras must offer the corporate workflow explicitly');
assert.match(purchases, /Compra de sucursal/, 'Compras must keep the branch workflow explicit');
assert.match(purchases, /CorporatePurchaseWorkspace/);

const corporatePath = 'apps/admin-web/src/features/purchasing/CorporatePurchaseWorkspace.tsx';
assert.ok(existsSync(corporatePath), 'The corporate workspace must be a separate component');
const corporate = readFileSync(corporatePath, 'utf8');
for (const label of ['Razón social', 'Distribución por sucursal', 'Cantidad pendiente', 'Recibir']) {
  assert.match(corporate, new RegExp(label), `Corporate workspace must expose ${label}`);
}
assert.match(corporate, /\/corporate-purchases/);
assert.doesNotMatch(corporate, /fetchApi\('\/suppliers'\)|fetchApi\('\/purchase-presentations'\)/,
  'Corporate reference data must use the organization-scoped corporate endpoint');
assert.match(corporate, /canManage && <button className="premium-add-btn"/,
  'Read-only corporate users must not see the create action');
assert.match(corporate, /canManage && selected\.status === 'DRAFT'/,
  'Read-only corporate users must not see approval or cancellation actions');
assert.match(corporate, /PAGE_SIZE/);
assert.match(corporate, />Anterior</);
assert.match(corporate, />Siguiente</);
assert.match(corporate, /setPage\(/,
  'Corporate order history must remain reachable beyond the first bounded page');
assert.doesNotMatch(corporate, /cash-context|Caja para compras|turno abierto/i,
  'Corporate procurement must not imply a branch cash effect');

const pos = readFileSync('apps/pos-web/src/App.tsx', 'utf8');
assert.match(pos, /<AdminModuleRedirect module="purchases"/,
  'POS keeps a link to Admin instead of duplicating the corporate editor');

console.log('Corporate and branch purchasing remain explicit, separate workflows');
