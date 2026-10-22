// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-fiscal-download-v1
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const moduleUrl = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, {
  compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022},
}).outputText).toString('base64');
const modules=new Map(['cashierDrafts','operationalOrders','adminAccess','reconciliationV2','branchWorkspace','deliveryFee','projectionContract']
  .map(name=>[name,moduleUrl(readFileSync(`packages/api-client/src/${name}.ts`,'utf8'))]));
let source=readFileSync('packages/api-client/src/index.ts','utf8');
for (const [name,url] of modules) source=source.replaceAll(`'./${name}'`,JSON.stringify(url));
const api=await import(moduleUrl(source));
const access=await import(modules.get('adminAccess'));
const fiscalSession={active_branch:{id:'qa-branch'},scope:{allowed_branch_ids:['qa-branch'],level:'branch'},
  admin_capabilities:{'invoicing.read':true}};
assert.equal(access.canAccessAdminRoute(fiscalSession,'/integrations'),true,'Explicit fiscal reader can access documents');
assert.equal(access.canAccessAdminRoute({...fiscalSession,admin_capabilities:{'orders.read':true}},'/integrations'),false);
const storage=()=>{const values=new Map();return {getItem:key=>values.get(key)??null,
  setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};};
globalThis.localStorage=storage();globalThis.sessionStorage=storage();
const id=n=>`018f6f73-2d0a-74f0-8f1c-${String(n).padStart(12,'0')}`;
const profile=version=>({organization_id:id(1),user:{id:id(2)},active_branch:{id:id(3)},
  scope:{authorization_version:1,allowed_branch_ids:[id(3)]},branch_workspace_context_id:id(4),
  branch_workspace_secret_version:version,branch_workspace_state:'active',
  branch_workspace_context:`qa-fiscal-context-${version}-${'x'.repeat(32)}`});
const requests=[],created=[],revoked=[],saved=[];
const originalCreate=URL.createObjectURL,originalRevoke=URL.revokeObjectURL;
URL.createObjectURL=blob=>{created.push(blob);return 'blob:qa-fiscal';};
URL.revokeObjectURL=url=>revoked.push(url);
const timers=[];const originalTimer=globalThis.setTimeout;
globalThis.setTimeout=(fn,ms)=>{timers.push({fn,ms});return timers.length;};
globalThis.document={body:{append(){}},createElement:()=>({href:'',download:'',
  click(){saved.push({href:this.href,download:this.download});},remove(){}})};
const bearer='qa-fiscal-reader';localStorage.setItem('auth_token',bearer);
const ticket=api.beginBranchWorkspaceRequest(bearer);
assert.equal(api.installBranchWorkspace(profile(1),ticket,bearer),true);
let respond=async()=>new Response('%PDF-synthetic',{headers:{'Content-Type':'application/pdf'}});
globalThis.fetch=async(url,options)=>{requests.push({url,headers:new Headers(options.headers)});return respond();};
try {
  await api.downloadFiscalInvoice(id(5),'pdf');
  assert.equal(requests[0].url,`/api/v1/invoicing/invoices/${id(5)}/pdf`);
  assert.equal(requests[0].headers.get('Authorization'),'Bearer '+bearer);
  assert.equal(requests[0].headers.get('X-Branch-Context'),profile(1).branch_workspace_context);
  assert.deepEqual(saved,[{href:'blob:qa-fiscal',download:`factura-${id(5)}.pdf`}]);
  assert.equal(created[0].type,'application/pdf');
  timers.forEach(timer=>timer.fn());assert.deepEqual(revoked,['blob:qa-fiscal']);
  for (const [reference,format] of [['https://attacker.invalid','pdf'],[id(5),'html'],['../private','xml']]) {
    await assert.rejects(()=>api.downloadFiscalInvoice(reference,format),error=>error.code==='fiscal_document_reference_invalid');
  }
  assert.equal(requests.length,1,'Invalid references never create transport');
  respond=async()=>{localStorage.setItem('auth_token','qa-other-account');return new Response('private-file');};
  await assert.rejects(()=>api.downloadFiscalInvoice(id(5),'pdf'),error=>error.code==='fiscal_download_context_changed');
  assert.equal(saved.length,1,'Late response cannot download under a different account');
  localStorage.setItem('auth_token',bearer);
  const fresh=api.beginBranchWorkspaceRequest(bearer);
  assert.equal(api.installBranchWorkspace(profile(2),fresh,bearer),true);
  respond=async()=>{assert.equal(api.installBranchWorkspace(profile(3),fresh,bearer),true);return new Response('private-file');};
  await assert.rejects(()=>api.downloadFiscalInvoice(id(5),'xml'),error=>error.code==='fiscal_download_context_changed');
  assert.equal(saved.length,1,'Late context rotation cannot expose a downloaded document');
  respond=async()=>new Response(JSON.stringify({detail:{code:'permission_denied'}}),{status:403});
  await assert.rejects(()=>api.downloadFiscalInvoice(id(5),'pdf'),error=>error.code==='permission_denied');
  assert.equal(created.length,1,'Failed authorization creates no blob URL');
  localStorage.removeItem('auth_token');const before=requests.length;
  await assert.rejects(()=>api.downloadFiscalInvoice(id(5),'pdf'),error=>error.code==='actor_required');
  assert.equal(requests.length,before);
  console.log('Fiscal binary download: authenticated context, safe local reference, revoked blob, late account/context and denied response verified.');
} finally {
  URL.createObjectURL=originalCreate;URL.revokeObjectURL=originalRevoke;globalThis.setTimeout=originalTimer;
}
