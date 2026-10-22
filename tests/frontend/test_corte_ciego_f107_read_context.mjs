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

// Successful GETs in flight must never hydrate a different login or workspace.
localStorage.setItem('auth_token', 'old-human');
let finish;
globalThis.fetch = () => new Promise(resolve => { finish = resolve; });
const pending = api.fetchApi('/payments');
localStorage.setItem('auth_token', 'new-human');
finish(new Response(JSON.stringify([{amount_cents: 95123}])));
await assert.rejects(pending, error => error.code === 'api_read_context_changed');

localStorage.setItem('auth_token', 'same-human');
let parse;
globalThis.fetch = async () => ({ok: true, status: 200, json: () => new Promise(resolve => {parse = resolve;})});
const parsing = api.fetchApi('/payments');
while (!parse) await Promise.resolve();
localStorage.setItem('auth_token', 'another-human');
parse([{amount_cents: 95123}]);
await assert.rejects(parsing, error => error.code === 'api_read_context_changed');
console.log('F1-07 stale read context tests passed');


// Same bearer, different branch or authorization version still invalidates data.
const authority = (branch = uuid(3), version = 1) => ({organization_id:uuid(1),
  user:{id:uuid(2)}, active_branch:{id:branch}, scope:{authorization_version:version}});
for (const next of [authority(uuid(4)), authority(uuid(3), 2), null]) {
  localStorage.setItem('auth_token', 'same-credential');
  api.setApiReadAuthority(authority());
  globalThis.fetch = () => new Promise(resolve => {finish = resolve;});
  const pending = api.fetchApi('/financial/payments', {}, 'v2');
  api.setApiReadAuthority(next);
  finish(new Response(JSON.stringify({items:[{amount_cents:95123}]})));
  await assert.rejects(pending, error => error.code === 'api_read_context_changed');
}

let invalidations = 0;
const unsubscribe = api.subscribeToApiReadAuthorityChange(() => invalidations++);
api.setApiReadAuthority(authority());
api.setApiReadAuthority(authority());
assert.equal(invalidations, 1, 'Identical authority refresh preserves valid cache');
api.setApiReadAuthority(authority(uuid(3), 2));
assert.equal(invalidations, 2);
unsubscribe();
api.setApiReadAuthority(null);
assert.equal(invalidations, 2);

// Authority cleanup does not destroy durable command evidence.
localStorage.setItem('pos_cashier_drafts_v1:synthetic', 'pending-evidence');
api.setApiReadAuthority(authority());
api.setApiReadAuthority(null);
assert.equal(localStorage.getItem('pos_cashier_drafts_v1:synthetic'), 'pending-evidence');
globalThis.fetch = async () => new Response(JSON.stringify({items:[]}));
assert.deepEqual(await api.fetchApi('/financial/payments', {}, 'v2'), {items:[]});


const access = {schema_version:2, authorization_version:1, branches:[{
  branch_id:uuid(3), policy_version:1, state:'active', capabilities:{'cash.user_cut.capture':true}, datasets:[],
}]};
const scoped = {...authority(),financial_access:access};
assert.equal(api.financialAccessForBranch(scoped, uuid(3)).capabilities['cash.user_cut.capture'], true);
assert.throws(() => api.financialAccessForBranch(scoped, uuid(4)), /scope_denied/);
assert.throws(() => api.financialAccessForBranch({...scoped,scope:{authorization_version:2}},uuid(3)), /authority_changed/);
for (const malformed of [null, {...access,schema_version:1}, {...access,total_cents:95123},
  {...access,branches:[{...access.branches[0],datasets:['other']}]},
  {...access,branches:[{...access.branches[0],total_cents:95123}]},
  {...access,branches:[{...access.branches[0],state:'suspended'}]},
  {...access,branches:[access.branches[0],access.branches[0]]}]) {
  assert.throws(() => api.parseSessionFinancialAccess(malformed), /contract_invalid/);
}
api.setApiReadAuthority(scoped);
globalThis.fetch = () => new Promise(resolve => { finish = resolve; });
const oldPolicy = api.fetchApi('/cash/user-cuts', {}, 'v2');
api.setApiReadAuthority({...scoped, financial_access:{...access,branches:[{...access.branches[0],policy_version:2}]}});
finish(new Response(JSON.stringify({items:[]})));
await assert.rejects(oldPolicy, error => error.code === 'api_read_context_changed');
console.log('F1-07 closed financial session contracts and policy fence passed');
