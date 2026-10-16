// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-workspace-provider-v1
// Executes the real provider with a minimal deterministic hook scheduler.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const mod = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, {
  compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022},
}).outputText).toString('base64');
const storage = () => {
  const values = new Map();
  return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),
    removeItem:key=>values.delete(key),key:n=>[...values.keys()][n]??null,get length(){return values.size;}};
};
globalThis.localStorage=storage();globalThis.sessionStorage=storage();
Object.defineProperty(globalThis,'navigator',{value:{onLine:true},configurable:true});
globalThis.window={setTimeout,clearTimeout,addEventListener(){},removeEventListener(){},
  location:{hostname:'localhost',port:'3003',href:''}};
globalThis.auditHooks={slots:[],cursor:0,effects:[],initial:true};
const react=mod(`
export const createContext=()=>({Provider:'provider'});
export function useState(initial){const h=globalThis.auditHooks,i=h.cursor++;if(!(i in h.slots))h.slots[i]=initial;
  return [h.slots[i],next=>{h.slots[i]=typeof next==='function'?next(h.slots[i]):next;}];}
export function useRef(initial){const h=globalThis.auditHooks,i=h.cursor++;return h.slots[i]??=( {current:initial} );}
export const useCallback=fn=>fn;
export const useEffect=fn=>{if(globalThis.auditHooks.initial)globalThis.auditHooks.effects.push(fn);};
export const useContext=()=>null;
export default {createElement:(_type,props)=>props};
`);
const modules=new Map(['cashierDrafts','operationalOrders','adminAccess','reconciliationV2','branchWorkspace']
  .map(name=>[name,mod(readFileSync('packages/api-client/src/'+name+'.ts','utf8'))]));
let apiSource=readFileSync('packages/api-client/src/index.ts','utf8');
for(const [name,url] of modules)apiSource=apiSource.replaceAll("'./"+name+"'",JSON.stringify(url));
const apiUrl=mod(apiSource),api=await import(apiUrl);
let sessionSource=readFileSync('apps/pos-web/src/session.ts','utf8')
  .replace("'@restaurantos/ui'",JSON.stringify(mod('export const confirmWorkspaceNavigation=()=>true;')))
  .replace("'react'",JSON.stringify(react)).replace("'@restaurantos/api-client'",JSON.stringify(apiUrl));
const {PosSessionProvider}=await import(mod(sessionSource));
const branch='018f6f73-2d0a-74f0-8f1c-000000000003';
const device='018f6f73-2d0a-74f0-8f1c-000000000007';
const config={branchId:branch,deviceId:device,gatewayUrl:'http://127.0.0.1:8091'};
localStorage.setItem('auth_token','qa-expired-central-credential');
localStorage.setItem('pos_operational_orders_enabled','true');
localStorage.setItem('pos_operational_orders_branch_id',branch);
localStorage.setItem('pos_operational_orders_device_id',device);
localStorage.setItem('pos_operational_orders_gateway_url',config.gatewayUrl);
api.storeOfflineOrderGrant({grant:'qa-independent-gateway-grant',expires_at:new Date(Date.now()+60000).toISOString()},config);
const profile={organization_id:'qa-organization',user:{id:'qa-actor'},active_branch:{id:branch,timezone:'America/Mazatlan'},
  scope:{allowed_branch_ids:[branch],authorization_version:1},permissions:['pos.operate']};
const seen=[];
globalThis.fetch=async (url,options)=>{
  seen.push({url,authorization:new Headers(options.headers).get('Authorization')});
  return url.startsWith(config.gatewayUrl)
    ?new Response(JSON.stringify(profile),{status:200})
    :new Response(JSON.stringify({detail:{code:'token_invalid',message:'Expired bearer'}}),{status:401});
};
PosSessionProvider({children:null});
auditHooks.initial=false;
for(const effect of auditHooks.effects)effect();
await new Promise(resolve=>setTimeout(resolve,30));
auditHooks.cursor=0;
const result=PosSessionProvider({children:null});
assert.equal(seen.length,2,'Gateway profile success followed by central appearance check');
assert.equal(seen[0].authorization,'Offline qa-independent-gateway-grant');
assert.equal(localStorage.getItem('auth_token'),'qa-expired-central-credential');
assert.equal(result.value.state.status,'ok','Independent gateway session must publish despite optional central 401');
assert.notEqual(api.loadUsableOfflineOrderGrant(config),null,'Gateway grant itself remains usable');
console.log('PASS: gateway auth/session=200 + optional central auth/session=401 publishes valid gateway; bearer and independent gateway grant preserved.');

// Definitive selection rejection should preserve the confirmed operational session.
auditHooks.slots=[];auditHooks.cursor=0;auditHooks.effects=[];auditHooks.initial=true;
localStorage.setItem('auth_token','qa-valid-central-credential');
localStorage.setItem('pos_operational_orders_enabled','false');
api.clearBranchWorkspace();
const branchB='018f6f73-2d0a-74f0-8f1c-000000000005';
const centralProfile={...profile,scope:{...profile.scope,allowed_branch_ids:[branch,branchB],can_select_branch:true},
  permissions:['pos.operate','pos.branch.select'],branch_context_reissue_required:true,
  branch_workspace_context_id:'qa-workspace-A',branch_workspace_state:'active',branch_workspace_secret_version:1};
globalThis.fetch=async url=>{
  if(url.endsWith('/auth/branch-selections'))return new Response(JSON.stringify({detail:{
    code:'branch_switch_open_shift',message:'An open shift blocks selection'}}),{status:409});
  const data=url.endsWith('/auth/branch-context-reissues')
    ?{...centralProfile,branch_workspace_context:'qa-memory-only-secret-'+'x'.repeat(32),branch_context_reissue_required:false}
    :centralProfile;
  return new Response(JSON.stringify(data),{status:200});
};
PosSessionProvider({children:null});auditHooks.initial=false;
for(const effect of auditHooks.effects)effect();
await new Promise(resolve=>setTimeout(resolve,30));
auditHooks.cursor=0;const ready=PosSessionProvider({children:null});
assert.equal(ready.value.state.status,'ok');
await assert.rejects(ready.value.selectBranch(branchB),error=>error.code==='branch_switch_open_shift');
auditHooks.cursor=0;const blocked=PosSessionProvider({children:null});
assert.equal(blocked.value.state.status,'ok');
assert.equal(blocked.value.session.active_branch.id,branch,'Definitive rejection retains canonical A');
assert.equal(blocked.value.state.validating,false);
assert.match(blocked.value.state.notice,/turno/);
assert.notEqual(api.branchWorkspaceSecret('qa-valid-central-credential'),null,'Original A secret remains valid in memory');
console.log('PASS: definitive branch_switch_open_shift=409 retains confirmed A, installed secret, notice, validating=false.');

let finishSelection;
globalThis.fetch=()=>new Promise(resolve=>{finishSelection=resolve;});
const pendingSelection=blocked.value.selectBranch(branchB);
auditHooks.cursor=0;const duringSelection=PosSessionProvider({children:null});
assert.equal(duringSelection.value.state.validating,true);
duringSelection.value.applyCatalogAppearance(branch,false);
auditHooks.cursor=0;const duringAppearanceCallback=PosSessionProvider({children:null});
assert.equal(duringAppearanceCallback.value.state.validating,true,'Appearance callback preserves pending selection fence');
finishSelection(new Response('{}',{status:503}));
await assert.rejects(pendingSelection);
auditHooks.cursor=0;const uncertain=PosSessionProvider({children:null});
assert.equal(uncertain.value.state.status,'error');
assert.ok(api.readBranchSelectionIntent(centralProfile),'Uncertain result retains frozen intent');
console.log('PASS: applyCatalogAppearance preserves validating=true while selection pending; uncertain 503 ends blocked and retains frozen intent.');

// Execute Admin's real load function; skip only its JSX presentation for this hook harness.
auditHooks.slots=[];auditHooks.cursor=0;auditHooks.effects=[];auditHooks.initial=true;
window.location.search='';
let adminSource=readFileSync('apps/admin-web/src/lib/adminSession.tsx','utf8');
adminSource=adminSource.slice(0,adminSource.indexOf('  if (!token()) return'))+'  return {state};\n}\n';
const router=mod('export const useLocation=()=>({key:"qa-admin-route",pathname:globalThis.adminPath||"/catalog"});export const Navigate="navigate";');
const ui=mod('export const quarantineWorkspaceSnapshots=()=>{};');
const queries=mod('export const useResetSessionQueries=()=>()=>{};');
const branches=mod('export const publishAdminSession=session=>{globalThis.publishedAdmin=session;};export const setCanonicalBranchId=()=>{};');
adminSource=adminSource.replaceAll("'react'",JSON.stringify(react))
  .replaceAll("'react-router-dom'",JSON.stringify(router))
  .replaceAll("'@restaurantos/api-client'",JSON.stringify(apiUrl))
  .replaceAll("'@restaurantos/ui'",JSON.stringify(ui))
  .replaceAll("'../components/AdminQueryProvider'",JSON.stringify(queries))
  .replaceAll("'./branchContext'",JSON.stringify(branches));
const {AdminSessionProvider}=await import(mod(adminSource));
const adminProfile={...centralProfile,permissions:['catalog.manage'],
  admin_capabilities:{'catalog.manage':true,'pos.operate':false},allowed_branches:[{id:branch}],
  scope:{...centralProfile.scope,level:'organization'}};
const adminSeen=[];
globalThis.fetch=async url=>{adminSeen.push(url);return new Response(JSON.stringify(adminProfile),{status:200});};
AdminSessionProvider({children:null});auditHooks.initial=false;
for(const effect of auditHooks.effects)effect();
await new Promise(resolve=>setTimeout(resolve,30));
auditHooks.cursor=0;const adminReady=AdminSessionProvider({children:null});
assert.equal(adminReady.state.session.user.id,adminProfile.user.id);
assert.deepEqual(adminSeen,['/api/v1/auth/session'],'Corporate Admin without POS must not reissue');
assert.equal(api.branchWorkspaceSecret('qa-valid-central-credential'),null,'Corporate-only Admin clears operational secret');
assert.equal(globalThis.publishedAdmin.admin_capabilities['catalog.manage'],true);
console.log('PASS: Admin catalog.manage without pos.operate publishes session and never POSTs reissue; operational memory cleared.');

// Document-only operators must acquire a branch context without a POS permission.
for (const capability of ['purchases.manage','expenses.manage','expenses.cancel']) {
  auditHooks.slots=[];auditHooks.cursor=0;auditHooks.effects=[];auditHooks.initial=true;
  api.clearBranchWorkspace();
  globalThis.adminPath=capability==='purchases.manage'?'/Purchases/':capability==='expenses.manage'?'/expenses':'/EXPENSES/';
  const documentProfile={...adminProfile,permissions:[capability],
    admin_capabilities:{[capability]:true,'pos.operate':false}};
  const calls=[];
  globalThis.fetch=async (url,options)=>{
    calls.push(url);
    const response=url.endsWith('/auth/branch-context-reissues')
      ?{...documentProfile,branch_workspace_context:'qa-document-only-secret-'+'x'.repeat(32),
        branch_context_reissue_required:false}:documentProfile;
    return new Response(JSON.stringify(response),{status:200});
  };
  AdminSessionProvider({children:null});auditHooks.initial=false;
  for(const effect of auditHooks.effects)effect();
  await new Promise(resolve=>setTimeout(resolve,30));
  auditHooks.cursor=0;const ready=AdminSessionProvider({children:null});
  assert.equal(ready.state.session.user.id,documentProfile.user.id);
  assert.deepEqual(calls,['/api/v1/auth/session','/api/v1/auth/branch-context-reissues'],capability);
  assert.notEqual(api.branchWorkspaceSecret('qa-valid-central-credential'),null,capability);
  assert.equal(globalThis.publishedAdmin.admin_capabilities['pos.operate'],false);
}
console.log('PASS: purchase/expense-only Admin profiles acquire operational context without POS capability.');

// A real catalog compatibility alias must not force context issuance on catalog routes.
auditHooks.slots=[];auditHooks.cursor=0;auditHooks.effects=[];auditHooks.initial=true;
api.clearBranchWorkspace();globalThis.adminPath='/catalog';
const catalogCalls=[];
globalThis.fetch=async url=>{catalogCalls.push(url);return new Response(JSON.stringify({
  ...adminProfile,admin_capabilities:{'catalog.manage':true,'purchases.manage':true,'pos.operate':false},
}),{status:200});};
AdminSessionProvider({children:null});auditHooks.initial=false;
for(const effect of auditHooks.effects)effect();
await new Promise(resolve=>setTimeout(resolve,30));
auditHooks.cursor=0;assert.ok(AdminSessionProvider({children:null}).state.session);
assert.deepEqual(catalogCalls,['/api/v1/auth/session']);
console.log('PASS: catalog purchase compatibility alias does not force a workspace on corporate catalog.');
