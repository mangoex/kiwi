import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-pos-assisted-order-'));

try {
  const source = join(root, 'apps/pos-web/src/features/pos/assistedOrderInterpreter.ts');
  execFileSync(process.execPath, [
    join(root, 'node_modules/typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, source,
  ], { cwd: root, stdio: 'pipe' });
  const interpreter = await import(pathToFileURL(join(temporaryDirectory, 'assistedOrderInterpreter.js')).href);

  const catalog = [
    { id: 'baguette-bbq', name: 'Baguette BBQ', active: true, available: true, instructions: [{ id: 'no-onion', name: 'Sin cebolla', kind: 'comment', priceDeltaCents: 0 }] },
  ];
  const draft = interpreter.interpretAssistedOrder(
    'Pedido para Cliente Sintético con teléfono 6672013019, un baguette de BBQ sin cebolla para recoger',
    catalog,
  );
  assert.equal(draft.customerName, 'Cliente Sintético');
  assert.equal(draft.phone, '6672013019');
  assert.equal(draft.orderType, 'takeout');
  assert.deepEqual(draft.lines, [{
    productId: 'baguette-bbq', quantity: 1, instructionId: 'no-onion', instructionName: 'Sin cebolla',
    instructionKind: 'comment', instructionPriceDeltaCents: 0, status: 'resolved', message: '',
  }]);
  assert.equal(JSON.stringify(draft).includes('price'), false, 'the local draft must never calculate price');

  const ambiguous = interpreter.interpretAssistedOrder('dos baguettes bbq', [
    ...catalog,
    { id: 'baguette-bbq-2', name: 'Baguette BBQ', active: true, available: true, instructions: [] },
  ]);
  assert.equal(ambiguous.lines[0].status, 'ambiguous');
  assert.equal(ambiguous.lines[0].productId, undefined);

  const unavailable = interpreter.interpretAssistedOrder('un baguette bbq extra picante', [
    { ...catalog[0], available: false },
  ]);
  assert.equal(unavailable.lines[0].status, 'not-found');
  assert.equal(unavailable.lines[0].productId, undefined);

  const unresolvedInstruction = interpreter.interpretAssistedOrder('un baguette bbq sin catsup', catalog);
  assert.equal(unresolvedInstruction.lines[0].status, 'not-found');
  assert.equal(unresolvedInstruction.lines[0].productId, 'baguette-bbq', 'the product may resolve while its instruction remains fail-closed');
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
