import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-ingredient-money-'));

try {
  const source = join(root, 'apps/admin-web/src/features/catalog/ingredientVariationMoney.ts');
  execFileSync(
    join(root, 'node_modules/.bin/tsc'),
    [
      '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
      '--outDir', temporaryDirectory, source,
    ],
    { cwd: root, stdio: 'pipe' },
  );
  const money = await import(pathToFileURL(join(temporaryDirectory, 'ingredientVariationMoney.js')).href);

  assert.equal(money.mxnToCentsExact('20'), 2000);
  assert.equal(money.mxnToCentsExact('20.5'), 2050);
  assert.equal(money.mxnToCentsExact('20.50'), 2050);
  assert.equal(money.centsToMxn(2000), '20.00');
  assert.equal(money.centsToMxn(money.mxnToCentsExact('20.50')), '20.50');
  for (const value of ['', '-1', '20.001', 'letras', 'NaN', 'Infinity', '90071992547409.92']) {
    assert.throws(() => money.mxnToCentsExact(value));
  }
  assert.equal(money.surchargeMxnError(true, '0'), 'El precio adicional debe ser mayor a $0.00.');
  assert.equal(money.surchargeMxnError(true, '20.50'), null);
  assert.equal(money.surchargeMxnError(false, ''), null);
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
