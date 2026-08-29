import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-pos-progressive-catalog-'));

try {
  const source = join(root, 'apps/pos-web/src/features/pos/progressiveCatalogFlow.ts');
  execFileSync(process.execPath, [
    join(root, 'node_modules/typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, source,
  ], { cwd: root, stdio: 'pipe' });
  const flow = await import(pathToFileURL(join(temporaryDirectory, 'progressiveCatalogFlow.js')).href);

  assert.equal(flow.progressiveCatalogStage({ hasCategory: false, selectionRequired: false, hasModifierProduct: false }), 'categories');
  assert.equal(flow.progressiveCatalogStage({ hasCategory: true, selectionRequired: true, hasModifierProduct: false }), 'selection');
  assert.equal(flow.progressiveCatalogStage({ hasCategory: true, selectionRequired: false, hasModifierProduct: false }), 'products');
  assert.equal(flow.progressiveCatalogStage({ hasCategory: false, selectionRequired: false, hasModifierProduct: false, startsAtProducts: true }), 'products');
  assert.equal(flow.progressiveCatalogStage({ hasCategory: true, selectionRequired: false, hasModifierProduct: true }), 'modifiers');

  const groups = [
    { id: 'base', minimum_selections: 1, maximum_selections: 1 },
    { id: 'extras', minimum_selections: 0, maximum_selections: 3 },
  ];
  assert.equal(flow.modifierSelectionsMeetMinimums(groups, { base: [], extras: [] }), false);
  assert.equal(flow.modifierSelectionsMeetMinimums(groups, { base: ['chicken'] }), true);
  assert.equal(flow.modifierSelectionsMeetMinimums(groups, { base: ['chicken'], extras: [] }), true);
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
