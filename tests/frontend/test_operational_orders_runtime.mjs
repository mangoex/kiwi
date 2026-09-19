import assert from 'node:assert/strict';

class StorageMock {
  #data = new Map();
  getItem(key) { return this.#data.get(key) ?? null; }
  setItem(key, value) { this.#data.set(key, String(value)); }
  removeItem(key) { this.#data.delete(key); }
  clear() { this.#data.clear(); }
}

globalThis.localStorage = new StorageMock();
globalThis.sessionStorage = new StorageMock();

const client = await import('../../packages/api-client/src/operationalOrders.ts');
const config = {
  branchId: '11111111-1111-4111-8111-111111111111',
  deviceId: '22222222-2222-4222-8222-222222222222',
  gatewayUrl: 'https://gateway.branch.example',
};

assert.equal(client.loadOperationalOrderConfig(), null, 'Disabled mode must not route operational requests.');
client.storeOperationalOrderConfig(config);
assert.deepEqual(client.loadOperationalOrderConfig(), config, 'HTTPS explicit gateway configuration is retained.');
assert.throws(
  () => client.storeOperationalOrderConfig({ ...config, gatewayUrl: 'http://gateway.branch.example' }),
  /operational_order_config_invalid/,
  'LAN HTTP is refused; only loopback may use HTTP.',
);

const expiresAt = new Date(Date.now() + 30_000).toISOString();
client.storeOfflineOrderGrant({ grant: 'x'.repeat(32), expires_at: expiresAt }, config);
assert.equal(client.loadUsableOfflineOrderGrant(config), 'x'.repeat(32), 'A grant remains usable until its exact expiration.');

let observedRequest;
globalThis.fetch = async (url, init) => {
  observedRequest = { url: String(url), init };
  return new Response(JSON.stringify({ id: 'order-1', _offline: { status: 'PENDING_SYNC' } }), { status: 200 });
};
const result = await client.operationalOrderRequest(config, '/orders', {
  method: 'POST',
  headers: { Authorization: 'Bearer must-not-win', 'Idempotency-Key': 'same-key' },
  body: '{}',
});
assert.equal(result.id, 'order-1');
assert.equal(observedRequest.url, 'https://gateway.branch.example/api/v1/local/order-api/orders');
assert.equal(new Headers(observedRequest.init.headers).get('Authorization'), `Offline ${'x'.repeat(32)}`);
assert.equal(new Headers(observedRequest.init.headers).get('Idempotency-Key'), 'same-key');

sessionStorage.setItem('pos_offline_order_grant_v3_expires_at', new Date(Date.now() - 1).toISOString());
assert.equal(client.loadUsableOfflineOrderGrant(config), null, 'Expired grants are removed and cannot reach a gateway.');

localStorage.setItem('pos_operational_orders_enabled', 'true');
localStorage.setItem('pos_operational_orders_device_id', 'not-a-uuid');
assert.throws(() => client.loadOperationalOrderConfig(), /operational_order_config_invalid/, 'Corrupt enabled configuration fails closed.');

console.log('ORD-OFF-001 operational order transport runtime contract passed');
