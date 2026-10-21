import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { pathToFileURL } from 'node:url';

const dir = mkdtempSync(join(tmpdir(), 'delivery-fee-'));
try {
  execFileSync(process.execPath, ['node_modules/typescript/bin/tsc', '--target', 'ES2022',
    '--module', 'NodeNext', '--moduleResolution', 'NodeNext', '--outDir', dir,
    'packages/api-client/src/deliveryFee.ts']);
  const fee = await import(pathToFileURL(join(dir, 'deliveryFee.js')).href);
  assert.equal(fee.parseDeliveryAmount('28'), 2800);
  assert.equal(fee.parseDeliveryAmount('28.50'), 2850);
  for (const invalid of ['28.001', '-28', 'Infinity', '1e2', '', '28,50']) {
    assert.throws(() => fee.parseDeliveryAmount(invalid));
  }
  assert.deepEqual(fee.deliverySelectionFromDraft({ mode: 'REMOVED' }), { mode: 'REMOVED' });
  assert.deepEqual(fee.deliverySelectionFromDraft({ mode: 'SELECTED', tariff_id: 'tariff-2' }),
    { mode: 'SELECTED', tariff_id: 'tariff-2' });
  assert.deepEqual(fee.deliverySelectionFromDraft(undefined), { mode: 'AUTO' });
  assert.throws(() => fee.deliverySelectionFromDraft({ mode: 'SELECTED' }));
  console.log('Delivery amounts and restored selection passed');
} finally {
  rmSync(dir, { recursive: true, force: true });
}
