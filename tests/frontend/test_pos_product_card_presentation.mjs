import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-pos-product-card-presentation-'));

try {
  const source = join(root, 'apps/pos-web/src/features/pos/productCardPresentation.ts');
  const tscJs = join(root, 'node_modules/typescript/bin/tsc');
  execFileSync(process.execPath, [
    tscJs,
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, source,
  ], { cwd: root, stdio: 'pipe' });
  const presentation = await import(pathToFileURL(join(temporaryDirectory, 'productCardPresentation.js')).href);
  for (const imageUrl of [null, undefined, '', '   ', 'https://cdn.example.test/salad.png']) {
    assert.equal(presentation.productCardPresentation(imageUrl), 'icon');
  }

  const pointOfSale = readFileSync(join(root, 'apps/pos-web/src/features/pos/PointOfSale.tsx'), 'utf8');
  assert.match(pointOfSale, /getProductIcon\(product\.category, 32\)/);
  assert.match(pointOfSale, /getProductIcon\(item\.category, 22\)/);
  assert.doesNotMatch(pointOfSale, /<img src=\{product\.image_url\}/);
  assert.doesNotMatch(pointOfSale, /item\.image_url\s*\?\s*<img/);
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
