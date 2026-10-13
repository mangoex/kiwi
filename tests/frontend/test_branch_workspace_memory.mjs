// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-workspace-memory-v1
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

const asModule = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText).toString('base64');
const workspaceUrl = asModule(readFileSync('packages/api-client/src/branchWorkspace.ts', 'utf8'));
const workspace = await import(workspaceUrl);
const uuid = n => `018f6f73-2d0a-74f0-8f1c-${String(n).padStart(12, '0')}`;
const profile = (version, context=uuid(4), branch=uuid(3)) => ({
  organization_id: uuid(1), user: {id: uuid(2)}, active_branch: {id: branch},
  scope: {authorization_version: 1, allowed_branch_ids: [uuid(3),uuid(5)]},
  branch_workspace_context_id: context, branch_workspace_secret_version: version,
  branch_workspace_state: 'active', branch_workspace_context: `qa-workspace-secret-${version}-${'x'.repeat(32)}`,
});

let writes = 0;
globalThis.localStorage = {setItem: () => { writes++; }, getItem: () => null};
globalThis.sessionStorage = {setItem: () => { writes++; }, getItem: () => null};
workspace.clearBranchWorkspace();
let ticket = workspace.beginBranchWorkspaceRequest('credential-a');
assert.equal(workspace.installBranchWorkspace(profile(3), ticket, 'credential-a'), true);
assert.equal(workspace.installBranchWorkspace(profile(2), ticket, 'credential-a'), false);
assert.equal(workspace.installBranchWorkspace(profile(3), ticket, 'credential-a'), false);
assert.equal(workspace.branchWorkspaceSecret('credential-a'), profile(3).branch_workspace_context);
assert.equal(workspace.hydrateBranchWorkspace({...profile(3),branch_workspace_context:null}, ticket, 'credential-a'), true);
assert.equal(workspace.branchWorkspaceSecret('credential-a'), profile(3).branch_workspace_context);
assert.equal(workspace.hydrateBranchWorkspace({...profile(4),branch_workspace_context:null}, ticket, 'credential-a'), false);
assert.equal(workspace.branchWorkspaceSecret('credential-a'), null, 'An unseen server rotation must disable the old secret');
assert.equal(workspace.installBranchWorkspace(profile(4), ticket, 'credential-a'), true);
const stale = ticket;
ticket = workspace.beginBranchWorkspaceRequest('credential-a');
assert.equal(workspace.installBranchWorkspace(profile(1,uuid(6),uuid(5)), ticket, 'credential-a'), true);
assert.equal(workspace.installBranchWorkspace(profile(5), stale, 'credential-a'), false, 'Late different-context issuance must not restore A');
assert.equal(workspace.branchWorkspaceSecret('credential-a'), profile(1).branch_workspace_context);
assert.equal(workspace.branchWorkspaceSecret('credential-b'), null, 'A changed credential cannot send A context');
assert.equal(workspace.installBranchWorkspace(profile(6), ticket, 'credential-a'), false, 'Observing B invalidates old A tickets');
const other = workspace.beginBranchWorkspaceRequest('credential-b');
assert.equal(workspace.installBranchWorkspace(profile(7), other, 'credential-a'), false);
assert.equal(workspace.installBranchWorkspace(profile(7), other, 'credential-b'), true);
for (const invalid of [
  {...profile(8),branch_workspace_context:''},
  {...profile(8),branch_workspace_secret_version:1.5},
  {...profile(8),branch_workspace_state:'superseded'},
  {...profile(8),scope:{authorization_version:2,allowed_branch_ids:[]}},
  {...profile(8),organization_id:undefined},
]) assert.equal(workspace.installBranchWorkspace(invalid, other, 'credential-b'), false);
assert.equal(writes, 0, 'Opaque workspace secrets must never enter persistent storage');
workspace.clearBranchWorkspace();
assert.equal(workspace.branchWorkspaceSecret('credential-b'), null);
assert.equal(workspace.installBranchWorkspace(profile(9), other, 'credential-b'), false);
console.log('Workspace monotonic rotation, hydration, account binding and late-response fencing verified.');

const storage = () => {
  const entries = new Map();
  return {getItem: key => entries.get(key) ?? null, setItem: (key,value) => entries.set(key,value),
    removeItem: key => entries.delete(key), get length() {return entries.size;}, key: n => [...entries.keys()][n] ?? null};
};
globalThis.localStorage = storage();
globalThis.sessionStorage = storage();
const modules = new Map(['cashierDrafts','operationalOrders','adminAccess','reconciliationV2','branchWorkspace']
  .map(name => [name, name === 'branchWorkspace' ? workspaceUrl : asModule(readFileSync(`packages/api-client/src/${name}.ts`, 'utf8'))]));
let apiSource = readFileSync('packages/api-client/src/index.ts', 'utf8');
for (const [name,url] of modules) apiSource = apiSource.replaceAll(`'./${name}'`,JSON.stringify(url));
const api = await import(asModule(apiSource));
localStorage.setItem('auth_token','credential-a');
ticket = api.beginBranchWorkspaceRequest('credential-a');
assert.equal(api.installBranchWorkspace(profile(1),ticket,'credential-a'),true);
const requests = [];
globalThis.fetch = async (url, options) => {
  requests.push({url,headers:new Headers(options.headers)});
  return new Response('{}',{status:200});
};
await api.fetchApi('/cash-shifts/open',{method:'POST',headers:{'x-branch-context':'form-stale-secret','authorization':'Bearer form-stale-bearer'}});
assert.equal(requests.at(-1).headers.get('X-Branch-Context'),profile(1).branch_workspace_context);
assert.equal(requests.at(-1).headers.get('Authorization'),'Bearer credential-a','Caller headers cannot combine a stale bearer with the confirmed credential');
await api.fetchApi('/auth/session');
assert.equal(requests.at(-1).headers.get('X-Branch-Context'),null,'Session hydration never transports the opaque secret');
localStorage.setItem('auth_token','credential-b');
await api.fetchApi('/cash-shifts/open',{headers:new Headers({'X-Branch-Context':'form-stale-secret'})});
assert.equal(requests.at(-1).headers.get('X-Branch-Context'),null);
assert.equal(requests.at(-1).headers.get('Authorization'),'Bearer credential-b');
ticket = api.beginBranchWorkspaceRequest('credential-b');
api.installBranchWorkspace(profile(2),ticket,'credential-b');
globalThis.fetch = async () => new Response(JSON.stringify({detail:{code:'token_invalid'}}),{status:401});
assert.equal(await api.fetchOptionalCentralSession(),null);
assert.equal(localStorage.getItem('auth_token'),'credential-b','Optional appearance cannot invalidate an independently signed gateway session');
assert.equal(api.branchWorkspaceSecret('credential-b'),profile(2).branch_workspace_context);
await assert.rejects(api.fetchApi('/cash-shifts/open'), error => error.status === 401);
assert.equal(api.branchWorkspaceSecret('credential-b'),null,'Current-session 401 discards the secret');

const gateway = await import(modules.get('operationalOrders'));
const config = {branchId:uuid(3),deviceId:uuid(7),gatewayUrl:'http://127.0.0.1:8091'};
gateway.storeOfflineOrderGrant({grant:'qa-independent-offline-grant',expires_at:new Date(Date.now()+60000).toISOString()},config);
globalThis.fetch = async (url, options) => {
  assert.ok(url.startsWith(config.gatewayUrl));
  assert.equal(new Headers(options.headers).get('Authorization'),'Offline qa-independent-offline-grant');
  assert.equal(new Headers(options.headers).get('X-Branch-Context'),null,'Gateway cannot receive a central workspace secret');
  return new Response('{}',{status:200});
};
await gateway.operationalOrderRequest(config,'/auth/session',{headers:{'X-Branch-Context':'form-stale-secret'}});
console.log('Central transport uses current memory; auth/gateway, stale forms and changed bearer are isolated.');

localStorage.setItem('auth_token','credential-c');
ticket = api.beginBranchWorkspaceRequest('credential-c');
const hydrated = {...profile(1),branch_workspace_context:null,branch_context_reissue_required:true};
let issuedCalls = 0;
let currentCredential = 'credential-c';
const recovered = await api.ensureBranchWorkspace(hydrated,ticket,() => currentCredential,async body => {
  issuedCalls++;
  assert.deepEqual(body,{context_id:uuid(4),expected_authorization_version:1});
  return profile(2);
});
assert.equal(recovered.branch_workspace_context,null,'React session never carries the opaque secret');
assert.equal(api.branchWorkspaceSecret('credential-c'),profile(2).branch_workspace_context);
await api.ensureBranchWorkspace({...hydrated,branch_workspace_secret_version:2},ticket,() => currentCredential,async () => {
  throw new Error('A hydrated current context must not rotate unnecessarily');
});
assert.equal(issuedCalls,1);
ticket = api.beginBranchWorkspaceRequest('credential-c');
const required = {...hydrated,branch_workspace_secret_version:3};
let release;
const pendingIssue = api.ensureBranchWorkspace(required,ticket,() => currentCredential,
  () => new Promise(resolve => {release=resolve;}));
currentCredential = 'credential-d';
api.beginBranchWorkspaceRequest('credential-d');
release(profile(4));
await assert.rejects(pendingIssue,/branch_workspace_response_superseded/);
assert.equal(api.branchWorkspaceSecret('credential-d'),null);
ticket = api.beginBranchWorkspaceRequest('credential-d');
const noHome = {...hydrated,active_branch:null,branch_selection_required:true,branch_workspace_context_id:null};
await api.ensureBranchWorkspace(noHome,ticket,() => currentCredential,async () => {throw new Error('Owner must select explicitly');});
const initial = {...hydrated,branch_workspace_context_id:null,branch_workspace_secret_version:null,branch_workspace_state:null};
await api.ensureBranchWorkspace(initial,ticket,() => currentCredential,async body => {
  assert.equal(body.context_id,null);
  return profile(1);
});

// Persist only frozen selection intent, scoped to the organization and actor.
const actorA = profile(1);
const first = api.branchSelectionIntent(actorA,uuid(5));
const afterLostResponse = {...actorA,active_branch:{id:uuid(5)}};
assert.deepEqual(api.branchSelectionIntent(afterLostResponse,uuid(5)),first);
assert.throws(() => api.branchSelectionIntent(actorA,uuid(3)),/branch_selection_uncertain_intent/);
assert.throws(() => api.readBranchSelectionIntent({...actorA,scope:{...actorA.scope,authorization_version:2}}),/branch_selection_intent_authority_changed/);
const actorB = {...actorA,user:{id:uuid(8)}};
assert.equal(api.readBranchSelectionIntent(actorB),null);
assert.notEqual(api.branchSelectionIntent(actorB,uuid(3)).idempotencyKey,first.idempotencyKey);
assert.equal(JSON.stringify(first).includes('secret'),false);
api.clearBranchSelectionIntent(actorA);
assert.equal(api.readBranchSelectionIntent(actorA),null);
assert.ok(api.readBranchSelectionIntent(actorB));
const corruptKey = `pos_branch_selection_intent_v2:${actorA.organization_id}:${actorA.user.id}`;
sessionStorage.setItem(corruptKey,'malformed');
assert.throws(() => api.readBranchSelectionIntent(actorA),/branch_selection_intent_invalid/);
assert.equal(sessionStorage.getItem(corruptKey),'malformed');
sessionStorage.removeItem(corruptKey);
sessionStorage.setItem('pos_branch_selection_intent_v1','legacy');
assert.throws(() => api.readBranchSelectionIntent(actorA),/branch_selection_legacy_intent_requires_review/);
sessionStorage.removeItem('pos_branch_selection_intent_v1');
const savedSet = sessionStorage.setItem;
sessionStorage.setItem = () => {throw new Error('storage_unavailable');};
assert.throws(() => api.branchSelectionIntent(actorA,uuid(5)),/storage_unavailable/);
sessionStorage.setItem = savedSet;
console.log('Reissue before publishing, late-account response and scoped frozen selection recovery verified.');
