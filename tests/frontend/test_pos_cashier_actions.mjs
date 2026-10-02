import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-cashier-actions-'));
try {
  execFileSync(process.execPath, [join(root, 'node_modules/typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, join(root, 'apps/pos-web/src/features/pos/cashierOrderActions.ts')],
  { cwd: root, stdio: 'pipe' });
  const { cashierOrderActions: actions } = await import(pathToFileURL(join(temporaryDirectory, 'cashierOrderActions.js')).href);
  const order = { status: 'READY', service_type: 'takeout', payment_status: 'PENDING',
    lines: [{ id: 'current' }], production_tasks: [{ order_line_id: 'current', status: 'COMPLETED' }] };
  const cashier = new Set(['orders.read', 'payments.confirm', 'orders.amend']);
  assert.deepEqual(actions(order, cashier), { fulfillment: null, cancellation: null });
  const authorized = new Set(['orders.fulfill', 'orders.cancel']);
  assert.equal(actions(order, authorized).fulfillment.command, 'deliver');
  assert.equal(actions({ ...order, service_type: 'delivery' }, authorized).fulfillment.command, 'start_delivery');
  assert.equal(actions({ ...order, service_type: 'delivery', status: 'IN_DELIVERY' }, authorized).fulfillment.command, 'deliver');
  assert.equal(actions({ ...order, status: 'ACCEPTED' }, authorized).fulfillment, null);
  assert.equal(actions({ ...order, status: 'DELIVERED' }, authorized).fulfillment.command, 'close');
  assert.equal(actions({ ...order, status: 'CANCELLED' }, authorized).fulfillment, null);
  assert.equal(actions(order, authorized).cancellation, 'classification_required');
  assert.equal(actions({ ...order, payment_status: 'CONFIRMED' }, authorized).cancellation, null);
  assert.equal(actions({ ...order, production_tasks: [{ order_line_id: 'current', status: 'IN_PROGRESS' }] }, authorized).cancellation, null);
  assert.equal(actions({ ...order, production_tasks: [{ order_line_id: 'current', status: 'PENDING' },
    { order_line_id: 'old', status: 'COMPLETED' }] }, authorized).cancellation, 'reservation_release');
  const history = readFileSync(join(root, 'apps/pos-web/src/features/history/History.tsx'), 'utf8');
  assert.match(history, /cashierOrderActions\(/, 'history must use scoped state/permission actions');
  assert.match(history, /CashierOrderActionDialog/, 'action requires an explicit confirmation');
} finally {
  assert.equal(dirname(temporaryDirectory), tmpdir());
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
