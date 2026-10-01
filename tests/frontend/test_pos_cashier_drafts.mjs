import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-cashier-drafts-'));
class MemoryStorage {
  values = new Map();
  failWrites = false;
  get length() { return this.values.size; }
  key(index) { return [...this.values.keys()][index] ?? null; }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { if (this.failWrites) throw new Error('quota'); this.values.set(key, value); }
  removeItem(key) { this.values.delete(key); }
}
try {
  execFileSync(process.execPath, [join(root, 'node_modules/typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, join(root, 'packages/api-client/src/cashierDrafts.ts')],
  { cwd: root, stdio: 'pipe' });
  const drafts = await import(pathToFileURL(join(temporaryDirectory, 'cashierDrafts.js')).href);
  const storage = new MemoryStorage();
  const scope = { userId: 'cashier', branchId: 'branch', registerId: 'Caja 1', transport: 'online' };
  const draft = { id: '018f6f73-2d0a-74f0-8f1c-000000000111',
    paymentKey: '018f6f73-2d0a-74f0-8f1c-000000000112', createdAt: '2026-10-01T00:00:00Z',
    cart: [{ id: 'product', lineId: 'line', name: 'Producto', quantity: 2, notes: 'Salsa aparte',
      modifiers: [{ option_id: 'extra', option_name: 'Carne extra', price_delta_cents: 2000 }],
      commentPresets: [{ id: 'comment', text: 'Sin picante' }], ingredientExtras: [] }],
    ownerName: 'Cliente QA', orderType: 'delivery', paymentMethod: 'cash',
    customerId: 'customer', addressId: 'address', driverId: 'driver' };
  drafts.saveActiveCashierDraft(storage, scope, draft);
  assert.deepEqual(drafts.readCashierDrafts(storage, scope).active, draft);
  for (const changed of [{ userId: 'another' }, { branchId: 'other' }, { registerId: 'Caja 2' },
    { transport: 'local', gatewayUrl: 'http://127.0.0.1:8111', deviceId: 'device' }]) {
    assert.equal(drafts.readCashierDrafts(storage, { ...scope, ...changed }).active, null);
  }
  storage.failWrites = true;
  assert.throws(() => drafts.holdCashierDraft(storage, scope), /quota/);
  assert.deepEqual(drafts.readCashierDrafts(storage, scope).active, draft, 'failure cannot erase capture');
  storage.failWrites = false;
  drafts.holdCashierDraft(storage, scope);
  assert.equal(drafts.readCashierDrafts(storage, scope).active, null);
  const second = { ...draft, id: '018f6f73-2d0a-74f0-8f1c-000000000113', ownerName: 'Segundo QA' };
  drafts.saveActiveCashierDraft(storage, scope, second);
  assert.deepEqual(drafts.restoreHeldCashierDraft(storage, scope, draft.id), draft);
  assert.deepEqual(drafts.readCashierDrafts(storage, scope).held, [second], 'swap preserves current capture');
  drafts.saveActiveCashierDraft(storage, scope, { ...second, id: '018f6f73-2d0a-74f0-8f1c-000000000114', cart: [] });
  assert.throws(() => drafts.holdCashierDraft(storage, scope), /cashier_draft_empty/);
  assert.deepEqual(drafts.readCashierDrafts(storage, scope).active.cart, []);
  drafts.saveActiveCashierDraft(storage, scope, draft);
  const storedKey = storage.key(0);
  const original = storage.getItem(storedKey);
  const corrupt = JSON.parse(original);
  corrupt.held.push({ ...draft });
  storage.setItem(storedKey, JSON.stringify(corrupt));
  assert.throws(() => drafts.readCashierDrafts(storage, scope), /cashier_draft_invalid/, 'duplicate identity must fail closed');
  storage.setItem(storedKey, original);
  assert.throws(() => drafts.saveActiveCashierDraft(storage, scope, { ...draft, cart: [{ ...draft.cart[0], notes: 'x'.repeat(501) }] }), /cashier_draft_invalid/);
  assert.throws(() => drafts.readCashierDrafts(storage, { ...scope, userId: '' }), /scope_required/);
  storage.setItem('other-feature', 'preserve');
  drafts.clearCashierDraftStorage(storage);
  assert.equal(storage.length, 1);
  assert.equal(storage.getItem('other-feature'), 'preserve');
  const pos = readFileSync(join(root, 'apps/pos-web/src/features/pos/PointOfSale.tsx'), 'utf8');
  assert.doesNotMatch(pos, /onClick=\{\(\) => \{\s*setPaymentMethod\(null\);\s*setPaymentOpen\(true\)/,
    'Reviewing a restored draft must preserve its intended payment method');
} finally {
  assert.equal(dirname(temporaryDirectory), tmpdir());
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
