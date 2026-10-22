import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const moduleUrl=source=>'data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64');
const form=await import(moduleUrl(readFileSync('apps/pos-web/src/features/cash/cashMovementForm.ts','utf8')));
const permissions={canRead:true,canWithdraw:true,canDeposit:true,canCompensate:true};
const active={state:'active',datasets:[]};
const operator=form.cashMovementCapabilities(permissions,active);
assert.equal(operator.canRead,false,'Cash movement action must not expose financial ledger');
assert.equal(operator.canWrite,true);
assert.equal(form.cashMovementCapabilities(permissions,{...active,datasets:['cash.movements']}).canRead,true);
assert.equal(form.cashMovementCapabilities(permissions,{state:'suspended',datasets:[]}).canUse,false);
console.log('Movement financial/action split passed');
const receipt={projection:'operational',schema_version:2,policy_version:3,
  command_id:'command',resource_id:'movement',action:'cash.movement.create',status:'confirmed',
  version:1,accepted_at:'2026-10-22T12:00:00Z',replay:false,correlation_id:'correlation'};
assert.equal(form.parseCashMovementAcknowledgement(receipt,3,'create'),'command');
for(const invalid of [{...receipt,expected_cash_cents:0},{...receipt,current_summary:{}},
  {...receipt,policy_version:2},{...receipt,action:'cash.movement.compensate'},
  {...receipt,projection:'financial'},{...receipt,command_id:''},{...receipt,replay:null}]) {
  assert.throws(()=>form.parseCashMovementAcknowledgement(invalid,3,'create'));
}
assert.equal(form.parseCashMovementAcknowledgement({...receipt,action:'cash.movement.compensate'},3,'compensate'),'command');
console.log('Closed movement acknowledgement contracts passed');
