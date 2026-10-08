import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync('apps/admin-web/src/App.tsx', 'utf8');
const hub = readFileSync('apps/admin-web/src/features/hubs/CatalogHub.tsx', 'utf8');
const nav = readFileSync('apps/admin-web/src/components/CategorySubNav.tsx', 'utf8');
const workspace = readFileSync('apps/admin-web/src/features/catalog/SharedModifierWorkspace.tsx', 'utf8');
const products = readFileSync('apps/admin-web/src/features/catalog/ProductsList.tsx', 'utf8');

assert.match(app, /path="modifiers"/);
assert.match(hub, /Modificadores/);
assert.match(nav, /\/modifiers/);
assert.match(workspace, /categorySelectionState/);
assert.match(workspace, /toggleCategoryProducts/);
assert.match(workspace, /\/catalog\/modifier-sets/);
assert.match(workspace, /aria-checked=.*mixed/);
assert.match(workspace, /registerWorkspaceSnapshot\(createRecoveryKey/);
assert.match(workspace, /registerWorkspaceSnapshot\(scopeRecoveryKey/);
assert.match(workspace, /createIntent\.current \?\?= \{/);
assert.match(workspace, /scopeIntent\.current \?\?= \{/);
assert.doesNotMatch(workspace, /product_component/);
assert.doesNotMatch(
  products,
  /Modificadores \/ Producto compuesto|<ModifierManager|\/catalog\/modifier-sets/,
  'Productos no debe duplicar la administración central de modificadores',
);

console.log('admin shared modifiers semantic checks passed');
