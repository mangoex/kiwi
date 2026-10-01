import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-cashier-payment-'));
try {
  execFileSync(process.execPath, [join(root, 'node_modules/typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, join(root, 'apps/pos-web/src/features/pos/cashierPayment.ts')],
  { cwd: root, stdio: 'pipe' });
  const flow = await import(pathToFileURL(join(temporaryDirectory, 'cashierPayment.js')).href);
  const values = new Map();
  const storage = { getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
  const attempt = { schema: 1, authority: '["cashier","branch","register"]',
    orderId: '11111111-1111-4111-8111-111111111111', key: '22222222-2222-4222-8222-222222222222',
    body: { amount_cents: 9500, method: 'cash', register_id: 'CAJA-01', received_cash: '100.00' } };
  flow.storePaymentAttempt(storage, attempt);
  attempt.body.received_cash = '200';
  const recovered = flow.readPaymentAttempt(storage);
  assert.equal(recovered.body.received_cash, '100.00', 'uncertain retry must freeze tender');
  assert.equal(recovered.key, attempt.key);
  assert.throws(() => flow.storePaymentAttempt(storage, attempt), /pendiente/);
  for (const error of [new Error('network'), { status: 500 }, { code: 'payment_idempotency_conflict' },
    { code: 'offline_order_stream_conflict' }, { code: 'offline_order_grant_required' }]) {
    assert.equal(flow.paymentWasDefinitelyRejected(error), false);
  }
  assert.equal(flow.paymentWasDefinitelyRejected({ code: 'cash_received_insufficient' }), true);
  flow.clearPaymentAttempt(storage, '33333333-3333-4333-8333-333333333333');
  assert.equal(flow.readPaymentAttempt(storage).key, attempt.key, 'Late response cannot erase another attempt');
  flow.clearPaymentAttempt(storage, attempt.key);
  assert.equal(flow.readPaymentAttempt(storage), null);
  assert.throws(() => flow.storePaymentAttempt({ ...storage, setItem() { throw new Error('quota'); } }, attempt), /quota/);
  const history = readFileSync(join(root, 'apps/pos-web/src/features/history/History.tsx'), 'utf8');
  assert.match(history, /CashierPaymentDialog/, 'existing order must open a review before payment');
  assert.doesNotMatch(history, /`pay-\$\{selected\.id\}-\$\{Date\.now\(\)\}/,
    'retry must not generate a new command key');
} finally {
  assert.equal(dirname(temporaryDirectory), tmpdir());
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
