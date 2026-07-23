import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-pos-cart-money-'));

try {
  const source = join(root, 'apps/pos-web/src/features/pos/cartMoney.ts');
  execFileSync(
    join(root, 'node_modules/.bin/tsc'),
    [
      '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
      '--outDir', temporaryDirectory, source,
    ],
    { cwd: root, stdio: 'pipe' },
  );
  const money = await import(pathToFileURL(join(temporaryDirectory, 'cartMoney.js')).href);
  const line = {
    price_cents: 1250,
    modifierPriceCents: 75,
    ingredientExtras: [{ sale_price_cents: 130, portions: 2 }],
    quantity: 3,
  };

  assert.equal(money.extraTotalCents(line.ingredientExtras), 260);
  assert.equal(money.cartLineUnitTotalCents(line), 1585);
  assert.equal(money.cartLineTotalCents(line), 4755);
  assert.equal(money.cartSubtotalCents([line, { ...line, quantity: 1 }]), 6340);
  assert.equal(money.formatMxnCents(4755), '$47.55');
  assert.equal(money.formatMxnCents(-1), '-$0.01');
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
