// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-admin-session-runtime-v1
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const asModule = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText).toString('base64');
const apiUrl = asModule(readFileSync('packages/api-client/src/index.ts', 'utf8').replace(/^export \* from '\.\/operationalOrders';\s*$/m, ''));
const api = await import(apiUrl);
const storage = () => {
  const entries = new Map();
  return { getItem: key => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value), removeItem: key => entries.delete(key) };
};
globalThis.localStorage = storage();
globalThis.sessionStorage = storage();
const rejected = status => new Response(JSON.stringify({ detail: { code: 'permission_denied', message: 'Access denied' } }), { status });

// A request already in flight must not erase a newer login.
localStorage.setItem('auth_token', 'previous-credential');
let finish;
globalThis.fetch = () => new Promise(resolve => { finish = resolve; });
const previousRequest = api.fetchApi('/catalog/products');
localStorage.setItem('auth_token', 'new-credential');
finish(rejected(401));
await assert.rejects(previousRequest, error => error instanceof api.ApiError && error.status === 401);
assert.equal(localStorage.getItem('auth_token'), 'new-credential', 'A late 401 must preserve the new session');

// The server can issue the same token value for two logins within the same timestamp quantum.
localStorage.setItem('auth_token', 'same-token-value');
globalThis.fetch = () => new Promise(resolve => { finish = resolve; });
const previousGeneration = api.fetchApi('/catalog/products');
globalThis.fetch = async () => new Response(JSON.stringify({ token: 'same-token-value' }), { status: 200 });
const login = await api.fetchApi('/auth/login', { method: 'POST' });
localStorage.setItem('auth_token', login.token);
finish(rejected(401));
await assert.rejects(previousGeneration);
assert.equal(localStorage.getItem('auth_token'), 'same-token-value', 'A late previous-generation 401 must preserve even an identical token value');

let invalidations = 0;
const unsubscribe = api.subscribeToUnauthorized(() => { invalidations++; });
const responses = [];
globalThis.fetch = () => new Promise(resolve => responses.push(resolve));
const pending = [api.fetchApi('/catalog/products'), api.fetchApi('/categories')];
responses.forEach(resolve => resolve(rejected(401)));
await Promise.all(pending.map(request => assert.rejects(request)));
assert.equal(invalidations, 1, 'Concurrent 401 responses must notify once');
assert.equal(localStorage.getItem('auth_token'), null);
assert.equal(sessionStorage.getItem('auth_token'), null);

sessionStorage.setItem('auth_token', 'session-only-credential');
globalThis.fetch = async (_url, options) => {
  assert.equal(options.headers.Authorization, 'Bearer session-only-credential');
  return rejected(403);
};
await assert.rejects(api.fetchApi('/catalog/products'));
assert.equal(sessionStorage.getItem('auth_token'), 'session-only-credential');
assert.equal(invalidations, 1, '403 must retain the session');
globalThis.fetch = async () => rejected(401);
await assert.rejects(api.fetchApi('/auth/login', { method: 'POST' }));
assert.equal(sessionStorage.getItem('auth_token'), 'session-only-credential', 'Rejected login must not expire an existing session');
assert.equal(invalidations, 1);
await assert.rejects(api.fetchApi('/branches'));
assert.equal(invalidations, 2, 'Session storage credentials also notify');
unsubscribe();
localStorage.setItem('auth_token', 'another-credential');
await assert.rejects(api.fetchApi('/branches'));
assert.equal(invalidations, 2, 'Unsubscribed consumers must not be called');

const require = createRequire(new URL('../../apps/admin-web/package.json', import.meta.url));
const queryUrl = pathToFileURL(require.resolve('@tanstack/react-query')).href;
const retrySource = readFileSync('apps/admin-web/src/lib/sessionRecovery.ts', 'utf8')
  .replace("'@restaurantos/api-client'", JSON.stringify(apiUrl))
  .replace("'@tanstack/react-query'", JSON.stringify(queryUrl));
const { shouldRetryAdminQuery, createAdminQueryClient } = await import(asModule(retrySource));
assert.equal(shouldRetryAdminQuery(0, new api.ApiError(401, 'token_invalid', 'Rejected')), false);
assert.equal(shouldRetryAdminQuery(0, new api.ApiError(403, 'forbidden', 'Rejected')), false);
assert.equal(shouldRetryAdminQuery(0, new api.ApiError(503, 'database_unavailable', 'Retry')), true);
assert.equal(shouldRetryAdminQuery(3, new Error('Network error')), false);
const oldClient = createAdminQueryClient();
let completeMutation;
const mutation = oldClient.getMutationCache().build(oldClient, {
  mutationFn: () => new Promise(resolve => { completeMutation = resolve; }),
  onSuccess: saved => oldClient.setQueryData(['products'], (current = []) => [...current, saved]),
});
const mutationResult = mutation.execute({});
await new Promise(resolve => setTimeout(resolve, 0));
await oldClient.cancelQueries();
oldClient.clear();
const newClient = createAdminQueryClient();
newClient.setQueryData(['products'], [{ id: 'new-session-product' }]);
completeMutation({ id: 'old-session-product' });
await mutationResult;
assert.deepEqual(newClient.getQueryData(['products']), [{ id: 'new-session-product' }], 'A late committed mutation cannot contaminate the new session cache');
assert.deepEqual(oldClient.getQueryData(['products']), [{ id: 'old-session-product' }], 'Committed command result is retained on its original client');
oldClient.clear();
newClient.clear();
const recovery = await import(asModule(readFileSync('packages/ui/src/components/workspaceSessionRecovery.ts', 'utf8')));
const purchase = await import(asModule(readFileSync('packages/ui/src/components/purchaseDraft.ts', 'utf8')));
let draft = purchase.initialPurchaseDraft('actor-one:branch-one', 'branch-one', '2026-10-01', 'retained-create-key', 'line');
draft = purchase.purchaseDraftReducer(draft, { type: 'header', key: 'folio', value: 'KEEP-UNCERTAIN' });
draft = purchase.purchaseDraftReducer(draft, { type: 'submit', fingerprint: 'reviewed-context' });
const unregister = recovery.registerWorkspaceSnapshot('purchase:actor-one:branch-one', () => draft);
recovery.quarantineWorkspaceSnapshots();
unregister();
assert.equal(recovery.readWorkspaceSnapshot('purchase:actor-two:branch-one'), undefined);
assert.equal(recovery.readWorkspaceSnapshot('purchase:actor-one:branch-two'), undefined);
const snapshot = recovery.readWorkspaceSnapshot('purchase:actor-one:branch-one');
assert.deepEqual(recovery.readWorkspaceSnapshot('purchase:actor-one:branch-one'), snapshot, 'StrictMode double initializer must not consume the snapshot');
const restored = purchase.restorePurchaseDraft(snapshot);
assert.equal(restored.phase, 'uncertain');
assert.equal(restored.creationKey, draft.creationKey);
assert.equal(restored.reviewFingerprint, 'reviewed-context');
assert.deepEqual(purchase.purchasePayload(restored), purchase.purchasePayload(draft));
snapshot.folio = 'Changed copy';
assert.equal(recovery.readWorkspaceSnapshot('purchase:actor-one:branch-one').folio, 'KEEP-UNCERTAIN', 'Snapshot reads must be isolated');
recovery.discardWorkspaceSnapshot('purchase:actor-one:branch-one');
assert.equal(recovery.readWorkspaceSnapshot('purchase:actor-one:branch-one'), undefined);
const copyKey = 'compound-copy:actor-one:product-one';
const intent = { key: 'copy-key', body: '{"source_product_id":"source","expected_source_version":2,"expected_target_version":5}', sourceId: 'source' };
const unregisterCopy = recovery.registerWorkspaceSnapshot(copyKey, () => intent);
recovery.quarantineWorkspaceSnapshots();
unregisterCopy();
assert.deepEqual(recovery.readWorkspaceSnapshot(copyKey), intent);
assert.equal(recovery.readWorkspaceSnapshot('compound-copy:actor-two:product-one'), undefined);
assert.equal(recovery.readWorkspaceSnapshot('compound-copy:actor-one:product-two'), undefined);
recovery.discardWorkspaceSnapshot(copyKey);
console.log('Admin session: late/concurrent 401, login rejection, 403, unsubscribe and bounded retry passed');
