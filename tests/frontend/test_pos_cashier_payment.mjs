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
    { code: 'offline_order_stream_conflict' }, { code: 'offline_order_grant_required' },
    { code: 'payment_already_confirmed' }]) {
    assert.equal(flow.paymentWasDefinitelyRejected(error), false);
  }
  assert.equal(flow.paymentWasDefinitelyRejected({ code: 'cash_received_insufficient' }), true);
  const alreadyPaid = Object.assign(new Error('Already paid'), { code: 'payment_already_confirmed' });
  const calls = [];
  const request = async (path, options) => {
    calls.push({ path, options });
    if (options?.method === 'POST') throw alreadyPaid;
    return { id: attempt.orderId, payment_status: 'CONFIRMED', status: 'READY' };
  };
  const reconciled = await flow.submitCashierPayment(request, attempt.orderId, {
    method: 'POST', headers: { 'Idempotency-Key': attempt.key }, body: JSON.stringify(attempt.body),
  });
  assert.deepEqual(reconciled, { order_status: 'READY', already_confirmed: true });
  assert.equal(reconciled.cash_tender, undefined, 'Never invent change for money received by another command');
  assert.equal(calls.filter((call) => call.options?.method === 'POST').length, 1);
  assert.equal(calls[1].path, `/orders/${attempt.orderId}`);
  for (const detail of [
    { id: attempt.orderId, payment_status: 'PENDING', status: 'ACCEPTED' },
    { id: 'another-order', payment_status: 'CONFIRMED', status: 'READY' },
  ]) {
    await assert.rejects(flow.submitCashierPayment(async (_path, options) => {
      if (options?.method === 'POST') throw alreadyPaid;
      return detail;
    }, attempt.orderId, { method: 'POST' }), (error) => error === alreadyPaid);
  }
  await assert.rejects(flow.submitCashierPayment(async (_path, options) => {
    if (options?.method === 'POST') throw alreadyPaid;
    throw new Error('network');
  }, attempt.orderId, { method: 'POST' }), /network/);
  assert.equal(flow.readPaymentAttempt(storage).key, attempt.key, 'Failed reconciliation preserves the receipt');
  flow.clearPaymentAttempt(storage, '33333333-3333-4333-8333-333333333333');
  assert.equal(flow.readPaymentAttempt(storage).key, attempt.key, 'Late response cannot erase another attempt');
  flow.clearPaymentAttempt(storage, attempt.key);
  assert.equal(flow.readPaymentAttempt(storage), null);
  assert.throws(() => flow.storePaymentAttempt({ ...storage, setItem() { throw new Error('quota'); } }, attempt), /quota/);
  const history = readFileSync(join(root, 'apps/pos-web/src/features/history/History.tsx'), 'utf8');
  assert.match(history, /CashierPaymentDialog/, 'existing order must open a review before payment');
  assert.doesNotMatch(history, /`pay-\$\{selected\.id\}-\$\{Date\.now\(\)\}/,
    'retry must not generate a new command key');
  const pos = readFileSync(join(root, 'apps/pos-web/src/features/pos/PointOfSale.tsx'), 'utf8');
  assert.equal((pos.match(/await submitCashierPayment\(requestOrder, orderData.id,/g) || []).length, 2,
    'New checkout and uncertain checkout recovery must both reconcile the authoritative state');
  const dialog = readFileSync(join(root, 'apps/pos-web/src/features/pos/CashierPaymentDialog.tsx'), 'utf8');
  assert.match(dialog, /await submitCashierPayment\(request, command.orderId,/);
  assert.match(pos, /sourceLineId: line.id/);
  assert.match(pos, /source_line_id: item.sourceLineId/);
  assert.match(pos, /source_line_id: line.source_line_id \?\? null/,
    'Amendments must mark new lines explicitly even when every original line was removed');
} finally {
  assert.equal(dirname(temporaryDirectory), tmpdir());
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
