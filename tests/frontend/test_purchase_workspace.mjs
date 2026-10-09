import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

const source = readFileSync('packages/ui/src/components/purchaseDraft.ts', 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { initialPurchaseDraft, purchaseDraftReducer, purchasePayload } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
let draft = initialPurchaseDraft('branch-1:user-1', 'branch-1', '2026-09-30', 'key-1', 'line-1');
assert.equal(draft.payment_method, 'cash', 'New purchase defaults to cash');
assert.equal(draft.paid_from_cash, true);
for (const method of ['transfer', 'card', 'other', 'cash']) {
  const selected = purchaseDraftReducer(draft, { type: 'header', key: 'payment_method', value: method });
  assert.equal(selected.paid_from_cash, method === 'cash', 'Payment selector derives the cash flag');
}
draft = purchaseDraftReducer(draft, { type: 'header', key: 'supplier_id', value: 'supplier-1' });
draft = purchaseDraftReducer(draft, { type: 'header', key: 'folio', value: 'NOTE-1' });
draft = purchaseDraftReducer(draft, { type: 'line', id: 'line-1', key: 'presentation_id', value: 'presentation-1' });
draft = purchaseDraftReducer(draft, { type: 'line', id: 'line-1', key: 'unit_price', value: '0' });
draft = purchaseDraftReducer(draft, { type: 'add', id: 'line-2' });
draft = purchaseDraftReducer(draft, { type: 'add', id: 'line-3' });
assert.equal(draft.lines.length, 3);
assert.equal(purchasePayload(draft).lines[0].unit_price, '0', 'Explicit zero must survive');
assert.equal(purchasePayload(draft).document_date, '2026-09-30', 'Calendar date must survive');
assert.ok(!('id' in purchasePayload(draft).lines[0]), 'Local row IDs must not reach Python');
draft = purchaseDraftReducer(draft, { type: 'header', key: 'supplier_id', value: 'supplier-2' });
assert.equal(draft.lines[0].presentation_id, 'presentation-1', 'Changing supplier must preserve capture for review');
draft = purchaseDraftReducer(draft, { type: 'supplierException', value: true });
draft = purchaseDraftReducer(draft, { type: 'header', key: 'supplier_catalog_exception_reason', value: 'Compra urgente por desabasto' });
assert.equal(purchasePayload(draft).supplier_catalog_exception, true);
assert.equal(purchasePayload(draft).supplier_catalog_exception_reason, 'Compra urgente por desabasto');
draft = purchaseDraftReducer(draft, { type: 'submit' });
const frozen = draft;
assert.deepEqual(purchaseDraftReducer(draft, { type: 'line', id: 'line-1', key: 'quantity', value: '99' }), frozen, 'Uncertain creation cannot change the retry payload');
draft = purchaseDraftReducer(draft, { type: 'uncertain', message: 'Lost response' });
assert.equal(draft.creationKey, 'key-1', 'Lost response must retain creation key');
assert.deepEqual(purchasePayload(draft), purchasePayload(frozen));
assert.deepEqual(purchaseDraftReducer(draft, { type: 'remove', id: 'line-1' }), draft);
draft = purchaseDraftReducer(draft, { type: 'resolved', message: 'Rejected without writes' });
draft = purchaseDraftReducer(draft, { type: 'remove', id: 'line-2' });
assert.deepEqual(draft.lines.map(line => line.id), ['line-1', 'line-3']);
assert.equal(draft.lines[0].unit_price, '0');
const editor = readFileSync('packages/ui/src/components/PurchaseDocumentEditor.tsx', 'utf8');
assert.doesNotMatch(editor, /parseFloat|Math\.round|\.reduce\(/, 'Editor must not calculate domain totals');
assert.match(editor, /\/purchases\/preview/);
assert.match(editor, /Idempotency-Key/);
assert.match(editor, /Compra excepcional con presentación de otro proveedor/);
assert.match(editor, /item_name/);
assert.match(editor, /item_sku/);
assert.match(editor, /supplier_name/);
assert.match(editor, /groupKey = item\.item_id/,
  'Los productos homónimos se agrupan por identidad canónica, no sólo por nombre');
assert.match(editor, /<optgroup key=\{itemId\} label=\{group\.label\}>/,
  'Las presentaciones muestran producto y SKU relacionados');
for (const path of ['apps/admin-web/src/features/purchasing/PurchasesList.tsx']) {
  assert.match(readFileSync(path, 'utf8'), /<PurchaseDocumentEditor/, `${path} must use the shared editor`);
}
assert.match(readFileSync('apps/pos-web/src/App.tsx', 'utf8'), /<AdminModuleRedirect module="purchases"/);
console.log('Purchase workspace capture, zero, date, lost response and retry contracts passed');

const recipe = readFileSync('apps/admin-web/src/features/catalog/RecipeManager.tsx', 'utf8');
assert.doesNotMatch(recipe, /netVal \/ factor|gross \* unitCost|liveTotalCost/);
assert.match(recipe, /\/recipes\/.*\/preview/);
const presentations = readFileSync('apps/admin-web/src/features/purchasing/PresentationsList.tsx', 'utf8');
assert.doesNotMatch(presentations, /parseFloat/);
assert.match(presentations, /usePythonPreview/);
const items = readFileSync('apps/admin-web/src/features/inventory/ItemsList.tsx', 'utf8');
assert.doesNotMatch(items, /lastCost \*|lastCost \/|parseFloat\(newPresentation/);
assert.match(items, /cost-preview/);

async function loadTs(path) {
  const code = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
}
const confirmation = await loadTs('apps/admin-web/src/features/purchasing/purchaseConfirmation.ts');
assert.equal(confirmation.isDefinitivePurchaseRejection(409, 'purchase_cash_context_changed', true), true);
assert.equal(confirmation.isDefinitivePurchaseRejection(409, 'cash_shift_not_open', true), true);
for (const [status, code] of [[401, 'token_invalid'], [403, 'permission_denied'], [409, 'idempotency_key_conflict'], [503, 'database_unavailable']]) assert.equal(confirmation.isDefinitivePurchaseRejection(status, code, true), false, 'An unresolved intent must survive uncertain rejection');
const scope = { organization_id: 'org-a', actor_id: 'actor-a', branch_id: 'branch-a' };
const cash = { branch_id: 'branch-a', open_registers: [{ register_id: 'CAJA-01', cash_shift_id: 'shift-1', opened_at: '2026-10-09T12:00:00Z' }] };
const purchase = { id: 'purchase-1', organization_id: 'org-a', branch_id: 'branch-a', payment_method: 'cash', paid_from_cash: true };
assert.equal(confirmation.selectedPurchaseRegister(cash, 'branch-a', 'AJENA'), 'CAJA-01');
assert.equal(confirmation.selectedPurchaseRegister(cash, 'branch-b', 'CAJA-01'), '');
assert.equal(confirmation.selectedPurchaseRegister({ ...cash, open_registers: [...cash.open_registers, { ...cash.open_registers[0], register_id: 'CAJA-02' }] }, 'branch-a', null), '');
const attempt = confirmation.createPurchaseAttempt(scope, purchase, cash, 'CAJA-01', 'stable-command');
assert.deepEqual(attempt.body, { branch_id: 'branch-a', register_id: 'CAJA-01', expected_cash_shift_id: 'shift-1' });
for (const patch of [{ branch_id: 'branch-b' }, { organization_id: 'org-b' }, { payment_method: 'other' }]) assert.throws(() => confirmation.createPurchaseAttempt(scope, { ...purchase, ...patch }, cash, 'CAJA-01', 'stable-command'));
assert.throws(() => confirmation.createPurchaseAttempt(scope, purchase, undefined, 'CAJA-01', 'stable-command'));
const store = new Map();
const storage = { getItem(key) { return store.get(key) || null; } };
store.set(confirmation.purchaseAttemptKey(scope, purchase.id), JSON.stringify(attempt));
assert.deepEqual(confirmation.readPurchaseAttempt(storage, scope, purchase.id), attempt);
assert.equal(confirmation.readPurchaseAttempt(storage, { ...scope, actor_id: 'actor-b' }, purchase.id), null);
assert.equal(confirmation.readPurchaseAttempt(storage, { ...scope, organization_id: 'org-b' }, purchase.id), null);
cash.open_registers[0].cash_shift_id = 'reopened-shift';
assert.equal(confirmation.readPurchaseAttempt(storage, scope, purchase.id).body.expected_cash_shift_id, 'shift-1', 'Recovery must keep the exact reviewed shift');
assert.deepEqual(confirmation.createPurchaseAttempt(scope, { ...purchase, payment_method: 'transfer', paid_from_cash: false }, undefined, '', 'transfer-key').body, { branch_id: 'branch-a' });
store.set(confirmation.purchaseAttemptKey(scope, purchase.id), JSON.stringify({ ...attempt, body: { ...attempt.body, total: '300' } }));
assert.throws(() => confirmation.readPurchaseAttempt(storage, scope, purchase.id), 'Corrupt pending metadata must not silently permit a new intent');
console.log('Cash default, scoped context and frozen confirmation recovery passed');
const { isWorkspaceRejection } = await loadTs('packages/ui/src/components/workspaceRecovery.ts');
assert.equal(isWorkspaceRejection(undefined, '', true, 'purchase'), false);
assert.equal(isWorkspaceRejection(403, 'forbidden', true, 'purchase'), false, 'Revoked permission cannot prove absence of a receipt');
assert.equal(isWorkspaceRejection(409, 'purchase_creation_idempotency_conflict', true, 'purchase'), false);
assert.equal(isWorkspaceRejection(409, 'supplier_not_enabled_for_branch', true, 'purchase'), true);
assert.equal(isWorkspaceRejection(409, 'modifier_copy_source_version_conflict', true, 'copy'), true);
assert.equal(isWorkspaceRejection(409, 'product_not_found', true, 'copy'), false);
let blank = initialPurchaseDraft('scope', 'branch', '', 'key', 'row');
assert.equal(blank.dirty, false);
for (const action of [{type:'header', key:'notes', value:'Only notes'}, {type:'header', key:'document_date', value:'2026-09-30'}, {type:'line',id:'row',key:'tax',value:'3'}]) assert.equal(purchaseDraftReducer(blank, action).dirty, true);
const { registerWorkspaceNavigationGuard, confirmWorkspaceNavigation } = await loadTs('packages/ui/src/components/workspaceNavigation.ts');
const unregister = registerWorkspaceNavigationGuard(() => false);
assert.equal(confirmWorkspaceNavigation(), false);
unregister();
assert.equal(confirmWorkspaceNavigation(), true);
let popHandler, prevented = false, movement;
globalThis.window = {
  history: {state:{idx:2},go(delta){movement=delta;},replaceState(){}},
  location: {href:'http://qa/pos/'},
  addEventListener(name, handler){if(name==='popstate') popHandler=handler;},
  removeEventListener(){popHandler=undefined;},
};
const cancelBack = registerWorkspaceNavigationGuard(() => false);
window.history.state.idx=1;window.location.href='http://qa/pos/history';
popHandler({stopImmediatePropagation(){prevented=true;}});
assert.equal(prevented,true);
assert.equal(movement,1,'Blocked Back must restore the original history entry');
window.history.state.idx=2;window.location.href='http://qa/pos/';
popHandler({stopImmediatePropagation(){throw new Error('Restoration must pass');}});
cancelBack();delete globalThis.window;
console.log('Recovery rejection, complete dirty state and navigation guards passed');
