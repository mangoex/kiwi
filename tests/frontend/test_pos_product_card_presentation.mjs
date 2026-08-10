import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-pos-product-card-presentation-'));

try {
  const source = join(root, 'apps/pos-web/src/features/pos/productCardPresentation.ts');
  execFileSync(join(root, 'node_modules/.bin/tsc'), [
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, source,
  ], { cwd: root, stdio: 'pipe' });
  const presentation = await import(pathToFileURL(join(temporaryDirectory, 'productCardPresentation.js')).href);
  for (const imageUrl of [null, undefined, '', '   ']) {
    assert.equal(presentation.productCardPresentation(imageUrl), 'fallback');
  }
  assert.equal(presentation.productCardPresentation('https://cdn.example.test/salad.png'), 'image');
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
