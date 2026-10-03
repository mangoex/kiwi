import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

const source = readFileSync('packages/ui/src/components/purchaseDraft.ts', 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { initialPurchaseDraft, purchaseDraftReducer, purchasePayload } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
let draft = initialPurchaseDraft('branch-1:user-1', 'branch-1', '2026-09-30', 'key-1', 'line-1');
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
for (const path of ['apps/admin-web/src/features/purchasing/PurchasesList.tsx', 'apps/pos-web/src/features/admin/BranchAdminOperations.tsx']) {
  assert.match(readFileSync(path, 'utf8'), /<PurchaseDocumentEditor/, `${path} must use the shared editor`);
}
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
console.log('Recovery rejection, complete dirty state and navigation guards passed');
