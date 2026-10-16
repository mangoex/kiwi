import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const admin = readFileSync(
  'apps/admin-web/src/features/catalog/CatalogAdministration.tsx',
  'utf8',
);
const mobileApi = readFileSync('apps/mobile-web/src/api.ts', 'utf8');

assert.match(admin, /show_in_digital_menu\?:boolean/);
assert.match(admin, /digital-menu-visibility/);
assert.match(admin, /JSON\.stringify\(\{visible\}\)/);
assert.match(admin, /type="checkbox"/);
assert.match(admin, /checked=\{row\.show_in_digital_menu !== false\}/);
assert.match(admin, /Mostrar en menú digital/);
assert.match(admin, /aria-label=\{`Mostrar \$\{row\.name\} en menú digital`\}/);

assert.doesNotMatch(mobileApi, /BACKUP_CATALOG/);
assert.match(mobileApi, /return \{ products: \[\], categories: DEFAULT_CATEGORIES \}/);

console.log('Branch product digital visibility semantic checks passed');
