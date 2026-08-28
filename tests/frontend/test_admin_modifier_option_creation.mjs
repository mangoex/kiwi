import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-admin-modifier-price-'));

try {
  const moneySource = join(root, 'apps/admin-web/src/features/catalog/ingredientVariationMoney.ts');
  execFileSync(process.execPath, [
    join(root, 'node_modules/typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, moneySource,
  ], { cwd: root, stdio: 'pipe' });
  const money = await import(pathToFileURL(join(temporaryDirectory, 'ingredientVariationMoney.js')).href);
  assert.equal(money.mxnToCentsExact('22'), 2200);
  assert.equal(money.mxnToCentsExact('22.00'), 2200);
  assert.equal(money.mxnToCentsExact('24.50'), 2450);

  const form = readFileSync(join(root, 'apps/admin-web/src/features/catalog/modifiers/CreateOptionForm.tsx'), 'utf8');
  const manager = readFileSync(join(root, 'apps/admin-web/src/features/catalog/ModifierManager.tsx'), 'utf8');
  assert.match(form, /mxnToCentsExact\(priceStr \|\| '0'\)/);
  assert.doesNotMatch(form, /parseFloat|Math\.round/);
  assert.match(form, /role="alert"/);
  assert.match(manager, /onCreateOption=\{async \(groupId, payload\) => \{ await createOption\.mutateAsync\(\{ groupId, payload \}\); \}\}/);
  assert.doesNotMatch(manager, /onCreateOption=\{async \(groupId, payload\) => \{ createOption\.mutate\(/);
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
