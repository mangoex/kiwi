import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const failures=[];
class ApiError extends Error { constructor(status,code){super(code);this.status=status;this.code=code;this.operationalIntentPending=true;} }
function extract(path,name){
 const sf=ts.createSourceFile(path,readFileSync(path,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let source;
 const visit=node=>{if(ts.isVariableDeclaration(node)&&node.name.getText(sf)===name)source=node.initializer.getText(sf);
  if(ts.isFunctionDeclaration(node)&&node.name?.getText(sf)===name)source=node.getText(sf).replace('async function '+name,'async function');
  ts.forEachChild(node,visit);};visit(sf);assert.ok(source,'Source function exists: '+name);
 return ts.transpileModule('('+source+')',{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
}
for(const name of ['executeOpen','executeClose'])for(const [status,code]of[[403,'permission_denied'],[409,'operational_command_context_changed'],[409,'idempotency_conflict']]){
 const intent={key:'original-synthetic-key',payload:{branch_id:'synthetic-branch',register_id:'CAJA-SOL',opening_cash_cents:0},shiftId:'synthetic-shift'};
 const openIntentRef={current:intent},closeIntentRef={current:intent};let hasRetry;
 const env={ApiError,fetchApi:async()=>{throw new ApiError(status,code);},hasPendingOperationalIntent:e=>e.operationalIntentPending===true,
 openIntentRef,closeIntentRef,setHasRetryIntent:x=>{hasRetry=x;},setViewState:()=>{},announce:()=>{},formatApiError:()=>'',
 isIdempotencyConflict:e=>e.code==='idempotency_conflict',parseOpenShiftResponse:()=>{},parseCloseResponse:()=>{},setCurrentShift:()=>{},setLastClosure:()=>{}};
 const fn=new Function(...Object.keys(env),'return '+extract('apps/pos-web/src/features/settings/Settings.tsx',name))(...Object.values(env));
 await fn(intent);
 try{assert.equal(name==='executeOpen'?openIntentRef.current:closeIntentRef.current,intent,'Pending error must retain original intent');}
 catch{failures.push(`${name}: pending ${status}/${code} discarded original key/body`);}
}
for(const code of ['permission_denied','idempotency_conflict']){
 const intent={target:{id:'synthetic-source'},reason:'Synthetic',evidence:'synthetic-evidence',idempotencyKey:'original-synthetic-key'};
 const actions=[];
 const env={ApiError,fetchApi:async()=>{throw new ApiError(409,code);},hasPendingOperationalIntent:e=>e.operationalIntentPending===true,
 compensation:{intent},buildCashCompensationPayload:(reason,evidence)=>({reason,evidence_refs:[evidence]}),nextCashIdempotencyKey:k=>k,
 dispatchCompensation:a=>actions.push(a),setStatus:()=>{},setCurrentSummary:()=>{},refreshLedger:async()=>true};
 const fn=new Function(...Object.keys(env),'return '+extract('apps/pos-web/src/features/cash/CashMovements.tsx','submitCompensation'))(...Object.values(env));
 await fn({preventDefault(){}});
 try{assert.equal(actions.at(-1).type,'uncertain_failure','Pending error must retain compensation intent');}
 catch{failures.push(`submitCompensation: pending ${code} cleared original key/body`);}
}
console.log(JSON.stringify({tested:8,failures}));if(failures.length)process.exitCode=1;
