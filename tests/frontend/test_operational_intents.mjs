import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

const asModule = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText).toString('base64');
const modules = new Map(['cashierDrafts', 'operationalOrders', 'adminAccess', 'reconciliationV2', 'branchWorkspace','deliveryFee']
  .map(name => [name, asModule(readFileSync(`packages/api-client/src/${name}.ts`, 'utf8'))]));
let apiSource = readFileSync('packages/api-client/src/index.ts', 'utf8');
for (const [name, url] of modules) apiSource = apiSource.replaceAll(`'./${name}'`, JSON.stringify(url));
const api = await import(asModule(apiSource));
const uuid = n => `018f6f73-2d0a-74f0-8f1c-${String(n).padStart(12, '0')}`;
const storage = () => {
  const entries = new Map();
  return {getItem: key => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value),
    removeItem: key => entries.delete(key)};
};
globalThis.localStorage = storage(); globalThis.sessionStorage = storage();
const profile = version => ({organization_id: uuid(1), user: {id: uuid(2)}, active_branch: {id: uuid(3)},
  scope: {authorization_version: 1, allowed_branch_ids: [uuid(3)]},
  branch_workspace_context_id: uuid(4), branch_workspace_secret_version: version,
  branch_workspace_state: 'active', branch_workspace_context: 'synthetic-workspace-context'.repeat(2)});
function install(version = 1) {
  api.clearBranchWorkspace(); localStorage.setItem('auth_token', 'synthetic-session-credential');
  const ticket = api.beginBranchWorkspaceRequest('synthetic-session-credential');
  assert.equal(api.installBranchWorkspace(profile(version), ticket, 'synthetic-session-credential'), true);
}
const body = {branch_id: uuid(3), lines: [], register_id: 'CAJA-01'};
const options = {method: 'POST', headers: {'Idempotency-Key': 'synthetic-order-intent-001',
  'X-Operational-Intent': 'stale-form-value'}, body: JSON.stringify(body)};
const receipt = {id: uuid(5), kind: 'order.create', branch_id: uuid(3), state: 'prepared', resource_id: null};
const requests = [];
function transport(callback) {
  requests.length = 0;
  globalThis.fetch = async (url, init) => {
    const item = {url, init, headers: new Headers(init.headers)};
    requests.push(item); return callback(item, requests.length);
  };
}
install();
transport(({url}, number) => new Response(JSON.stringify(number === 1 ? receipt
  : url.endsWith('/resolve') ? {...receipt, state: 'acknowledged', resource_id: uuid(6)} : {id: uuid(6)})));
assert.deepEqual(await api.fetchApi('/orders', options), {id: uuid(6)});
assert.deepEqual(requests.map(r => r.url), ['/api/v1/operational-intents', '/api/v1/orders',
  `/api/v1/operational-intents/${uuid(5)}/resolve`]);
assert.deepEqual(JSON.parse(requests[0].init.body), {kind: 'order.create', target_id: null, payload: body});
assert.equal(requests[0].headers.get('X-Operational-Intent'), null);
assert.equal(requests[1].headers.get('X-Operational-Intent'), uuid(5));
assert.equal(requests[1].init.body, options.body);
assert.equal(requests[1].headers.get('Idempotency-Key'), options.headers['Idempotency-Key']);
assert.equal(requests[2].headers.get('X-Branch-Context'), null, 'Minimum recovery never renews workspace authority');

for (const key of ['x', 'x'.repeat(180), '\u00a0x\u00a0']) {
  install();
  const cashReceipt = {...receipt, kind:'cash.movement.create'};
  transport((_, number) => new Response(JSON.stringify(number === 1 ? cashReceipt
    : number === 2 ? {movement:{id:uuid(6)}} : {...cashReceipt,state:'acknowledged',resource_id:uuid(6)})));
  await api.fetchApi('/cash/movements', {method:'POST', headers:{'Idempotency-Key':key},
    body:JSON.stringify({branch_id:uuid(3),register_id:'CAJA-01',movement_type:'withdrawal',
      concept_id:uuid(7),amount_cents:100,reference:'synthetic',evidence_refs:['synthetic']})});
  assert.equal(requests[1].headers.get('Idempotency-Key'), key);
  assert.equal(requests[0].headers.get('Idempotency-Key'), key.trim());
}

for (const [endpoint, key] of [['/cash/movements', 'x'.repeat(181)], ['/cash/movements', ' '],
  ['/orders', 'x'], ['/orders', 'x'.repeat(161)], [`/orders/${uuid(6)}/payments`, 'x'],
  [`/orders/${uuid(6)}/payments`, 'x'.repeat(161)]]) {
  install(); transport(() => {throw new Error('Invalid key must not reach transport');});
  await assert.rejects(api.fetchApi(endpoint, {...options, headers:{'Idempotency-Key':key}}),
    error => error.code === 'operational_command_required' && !api.hasPendingOperationalIntent(error));
  assert.equal(requests.length, 0);
}

for (const [endpoint, kind, target] of [
  ['/cash/shifts/open','cash.shift.open',null], ['/cash-shifts/open','cash.shift.open',null],
  ['/cash-shifts/close','cash.shift.close.register',null],
  [`/cash/shifts/${uuid(6)}/close-operationally`,'cash.shift.close',uuid(6)],
  [`/cash/movements/${uuid(6)}/compensations`,'cash.movement.compensate',uuid(6)],
]) {
  install(); const cashReceipt={...receipt,kind};
  transport((_,number)=>new Response(JSON.stringify(number===1?cashReceipt:number===2?{id:uuid(7)}:
    {...cashReceipt,state:'acknowledged',resource_id:uuid(7)})));
  await api.fetchApi(endpoint,{...options,headers:{'Idempotency-Key':'x'}});
  assert.equal(JSON.parse(requests[0].init.body).kind,kind);
  assert.equal(JSON.parse(requests[0].init.body).target_id,target);
  assert.equal(requests[1].url,`/api/v1${endpoint}`);
  assert.equal(requests[1].init.body,options.body);
  install(); transport((_,number)=>number===1?new Response(JSON.stringify(cashReceipt)):
    new Response(JSON.stringify({detail:{code:'idempotency_conflict',message:'Synthetic conflict'}}),{status:409}));
  await assert.rejects(api.fetchApi(endpoint,{...options,headers:{'Idempotency-Key':'x'}}),
    error=>error.code==='idempotency_conflict' && api.hasPendingOperationalIntent(error));
  assert.equal(requests.length,2);
}

for (const lostPhase of [1, 2]) {
  install(); transport((_, number) => {
    if (number === lostPhase) throw new TypeError('Synthetic lost response');
    return new Response(JSON.stringify(receipt));
  });
  await assert.rejects(api.fetchApi('/orders', options));
  assert.equal(requests.length, lostPhase, 'A lost result must not trigger resolution or alternate send');
}
install(); transport((_, number) => new Response(number === 1 ? JSON.stringify(receipt) : '{broken-json'));
await assert.rejects(api.fetchApi('/orders', options), error => api.hasPendingOperationalIntent(error));
assert.equal(requests.length, 2, 'An unreadable financial response remains uncertain without alternate send');
install(); transport((_, number) => number === 1 ? new Response(JSON.stringify(receipt))
  : new Response(JSON.stringify({detail:{code:'permission_denied',message:'Synthetic revoked permission'}}),{status:403}));
await assert.rejects(api.fetchApi('/orders', options), error => error.code === 'permission_denied'
  && api.hasPendingOperationalIntent(error));
assert.equal(requests.length, 2, 'Revocation must not discard the previously registered intention');
install(); transport((_, number) => {
  if (number === 3) localStorage.setItem('auth_token','another-synthetic-account');
  return new Response(JSON.stringify(number === 1 ? receipt : number === 2 ? {id:uuid(6)} : {...receipt,state:'acknowledged'}));
});
await assert.rejects(api.fetchApi('/orders', options), error => error.code === 'operational_command_context_changed'
  && api.hasPendingOperationalIntent(error));
install(); transport((_, number) => {
  if (number === 3) throw new TypeError('Synthetic lost recovery response');
  return new Response(JSON.stringify(number === 1 ? receipt : {id: uuid(6)}));
});
assert.deepEqual(await api.fetchApi('/orders', options), {id: uuid(6)},
  'Failure of housekeeping cannot erase the known financial response');

install(); transport((_, number) => {
  if (number === 1) localStorage.setItem('auth_token', 'another-synthetic-account');
  return new Response(JSON.stringify(receipt));
});
await assert.rejects(api.fetchApi('/orders', options), error => error.code === 'operational_command_context_changed');
assert.equal(requests.length, 1, 'Do not send a prepared command under another account');
console.log('Durable intent transport order, lost replies and account fence verified.');
