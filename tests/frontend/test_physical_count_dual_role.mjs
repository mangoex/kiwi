import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

const app = read('apps/pos-web/src/App.tsx');
const layout = read('apps/pos-web/src/components/PosLayout.tsx');
const posCount = read('apps/pos-web/src/features/inventory/PhysicalCountCapturePage.tsx');
const adminCount = read('apps/admin-web/src/features/inventory/PhysicalCountList.tsx');
const sharedCapture = read('packages/ui/src/components/PhysicalCountCapture.tsx');
const bdd = read('docs/03-BDD-physical-counts.md');
const tdd = read('docs/04-TDD-physical-counts.md');

assert.match(app, /path="inventory-counts"/);
assert.match(app, /permissions=\{\['inventory\.count\.capture', 'inventory\.count'\]\}/);
assert.match(layout, /hasPermission\('inventory\.count\.capture'\).*hasPermission\('inventory\.count'\)/s);
assert.match(layout, /label: 'Conteo físico'/);

assert.match(posCount, /active_branch/);
assert.match(posCount, /navigator\.onLine/);
assert.match(posCount, /Sin conexión/);
assert.doesNotMatch(posCount, /snapshot_difference|snapshot_unit_cost|theoretical_quantity/);

assert.match(sharedCapture, /presentations\.map/);
assert.match(sharedCapture, /base_unit_yield/);
assert.match(sharedCapture, /expected_version/);
assert.match(sharedCapture, /Guardar y siguiente/);
assert.match(sharedCapture, /Enviar a revisión/);

assert.match(adminCount, /category_names: selectedGroups/);
assert.match(adminCount, /Inventario teórico/);
assert.match(adminCount, /Inventario físico/);
assert.match(adminCount, /snapshot_difference_value/);
assert.match(adminCount, /Aprobar ajustes/);

for (const id of ['BDD-SC-580', 'BDD-SC-581', 'BDD-SC-582', 'BDD-SC-583', 'BDD-SC-584', 'BDD-SC-585']) {
  assert.match(bdd, new RegExp(id));
}
assert.match(tdd, /TDD-TS-131/);
assert.match(tdd, /TDD-TC-302/);

console.log('Dual-role physical count semantic contract passed.');
