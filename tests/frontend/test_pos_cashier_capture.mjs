import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-cashier-capture-'));
try {
  execFileSync(process.execPath, [join(root, 'node_modules/typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, join(root, 'apps/pos-web/src/features/pos/cashierCapture.ts')],
  { cwd: root, stdio: 'pipe' });
  const flow = await import(pathToFileURL(join(temporaryDirectory, 'cashierCapture.js')).href);
  for (const value of ['', '0', '-1', '1.5', '1e2', 'Infinity', '9007199254740992']) {
    assert.equal(flow.parseCartQuantity(value), null);
  }
  assert.equal(flow.parseCartQuantity('5'), 5);
  assert.equal(flow.parseCartQuantity(' 02 '), 2);
  const groups = [{ id: 'extra', minimum_selections: 0 }, { id: 'required', minimum_selections: 1 },
    { id: 'second-required', minimum_selections: 2 }, { id: 'comment', minimum_selections: 0 }];
  assert.deepEqual(flow.requiredGroupsFirst(groups).map((group) => group.id),
    ['required', 'second-required', 'extra', 'comment']);
  assert.equal(groups[0].id, 'extra', 'ordering must not mutate the server catalog');
} finally {
  assert.equal(dirname(temporaryDirectory), tmpdir());
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
