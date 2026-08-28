import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-pos-category-options-'));

try {
  const source = join(root, 'apps/pos-web/src/features/pos/categoryOptionFlow.ts');
  execFileSync(process.execPath, [
    join(root, 'node_modules/typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, source,
  ], { cwd: root, stdio: 'pipe' });
  const flow = await import(pathToFileURL(join(temporaryDirectory, 'categoryOptionFlow.js')).href);
  const group = { id: 'size', code: 'size', name: 'Tamaño', values: [
    { id: 'large', code: 'large', name: 'Grande', display_order: 30 },
    { id: 'small', code: 'small', name: 'Chica', display_order: 10 },
  ] };
  const categories = [{ id: 'salads', name: 'ENSALADAS', selection_group: group }];
  const products = [
    { id: 'small-product', category_id: 'salads', name: 'ENSALADA CHICA', selection: { group_id: 'size', value_id: 'small' } },
    { id: 'large-product', category_id: 'salads', name: 'ENSALADA GRANDE', selection: { group_id: 'size', value_id: 'large' } },
  ];
  const menuCategories = [
    { id: '', name: 'Todas' },
    { id: 'salads', name: 'ENSALADAS' },
    { id: 'drinks', name: 'BEBIDAS' },
    { id: 'empty', name: 'SIN PRODUCTOS' },
  ];
  const menuProducts = [
    products[0],
    { id: 'drink-product', category_id: 'drinks', name: 'AGUA', selection: null },
  ];
  assert.deepEqual(
    flow.categoriesWithAvailableProducts(menuCategories, menuProducts),
    menuCategories.slice(0, 3),
  );
  assert.deepEqual(flow.categoriesWithAvailableProducts(menuCategories, []), []);
  assert.deepEqual(flow.availableOptionValues(group), [group.values[1], group.values[0]]);
  assert.equal(flow.resolveCategoryOptionState(categories[0], ''), 'selection-required');
  assert.equal(flow.resolveCategoryOptionState(categories[0], 'obsolete'), 'selection-required');
  assert.deepEqual(flow.filterProductsForCategoryOption(products, 'salads', 'small', 'chica'), [products[0]]);
  assert.equal(flow.catalogProjectionState(true, group), 'error');
  assert.equal(flow.catalogProjectionState(false, { ...group, values: [] }), 'selection-empty');
  assert.equal(flow.catalogProjectionState(false, group), 'ready');
  assert.deepEqual(flow.transitionCategoryOption({ categoryId: 'salads', valueId: 'small' }, 'salads', 'large'), { categoryId: 'salads', valueId: 'large' });
  assert.deepEqual(flow.transitionCategoryOption({ categoryId: 'salads', valueId: 'small' }, 'other', ''), { categoryId: 'other', valueId: '' });
  const cart = [{ lineId: 'line-1', productId: 'small-product', quantity: 1 }];
  const navigation = flow.transitionCatalogNavigation({
    categoryId: 'salads', valueId: 'small', cart, search: 'chef',
    transient: { modifierProductId: 'small-product', groups: ['extras'], selections: { extras: ['avocado'] }, error: 'pendiente' },
  }, 'salads', 'large');
  assert.equal(navigation.valueId, 'large');
  assert.deepEqual(navigation.cart, cart);
  assert.equal(navigation.search, 'chef');
  assert.deepEqual(navigation.transient, { modifierProductId: null, groups: [], selections: {}, error: '' });
  const changedCategory = flow.transitionCatalogNavigation(navigation, 'drinks', 'large');
  assert.equal(changedCategory.valueId, '');
  assert.deepEqual(changedCategory.cart, cart);
  assert.equal(changedCategory.search, 'chef');
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
