import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

const compiled = ts.transpileModule(readFileSync(
  'apps/admin-web/src/features/purchasing/corporateIntent.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const api = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
for (const invalid of [undefined, '', ' ', '0', '-1', 'NaN', '1e3', '1.0000001', '2.000001']) {
  assert.throws(() => api.explicitReceiptQuantity(invalid, '2.000000'));
}
assert.equal(api.explicitReceiptQuantity('0.000001', '2.000000'), '0.000001');
assert.equal(api.explicitReceiptQuantity('2.000000', '2.000000'), '2.000000');
assert.equal(api.pendingBaseQuantity('999999999999.999999', '999999999999.999998'), '0.000001');
assert.equal(api.pendingBaseQuantity('0.333333', '0.166667'), '0.166666');
assert.equal(api.pendingBaseQuantity('0', '1'), 'Dato inválido');
const values = new Map();
const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
const authority = { organization_id: 'org-a', actor_id: 'actor-a' };
const body = JSON.stringify({ expected_version: 2, branch_id: 'branch-b', warehouse_id: 'warehouse-b',
  received_at: '2026-10-13', lines: [{ allocation_id: 'allocation-b', quantity: '0.000001' }] });
const beforePost = api.createCorporateIntent(storage, authority, '/corporate-purchases/order-a/receipts', body, 'stable-key');
const afterReload = api.readCorporateIntent(storage, authority);
assert.deepEqual(afterReload, beforePost, 'Lost response and reload preserve exact request');
assert.equal(afterReload.body, body);
assert.throws(() => api.createCorporateIntent(storage, authority, '/corporate-purchases', '{}', 'another-key'));
assert.equal(api.readCorporateIntent(storage, { ...authority, actor_id: 'another-actor' }), null);
values.set(api.corporateIntentKey(authority), '{bad-json');
assert.throws(() => api.readCorporateIntent(storage, authority), 'Corrupt history fails closed');
assert.throws(() => api.createCorporateIntent({ ...storage, getItem: () => null,
  setItem: () => { throw new Error('Quota exceeded'); } }, authority, '/corporate-purchases', '{}', 'key'));
for (const [status, code] of [[401, 'auth'], [403, 'permission_denied'], [500, 'db'],
  [409, 'corporate_purchase_idempotency_conflict']]) {
  assert.equal(api.definitiveCorporateRejection(status, code), false);
}
assert.equal(api.definitiveCorporateRejection(409, 'corporate_purchase_version_conflict'), true);
console.log('Explicit quantity, frozen intent, reload, authority isolation and storage failure passed');
