import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const output = mkdtempSync(join(tmpdir(), 'restaurantos-pos-cash-movement-'));

function testReadOnlyLedger(form) {
  const readOnly = form.cashMovementCapabilities({
    canRead: true, canWithdraw: false, canDeposit: false,
  });
  assert.equal(readOnly.canUse, true);
  assert.equal(readOnly.canWrite, false);
  assert.equal(readOnly.canWithdraw, false);
  assert.equal(readOnly.canDeposit, false);
}

function testWithdrawOnlyForm(form) {
  const withdrawOnly = form.cashMovementCapabilities({
    canRead: false, canWithdraw: true, canDeposit: false,
  });
  assert.equal(withdrawOnly.canUse, true);
  assert.equal(withdrawOnly.canWrite, true);
  assert.equal(withdrawOnly.initialType, 'withdrawal');
  assert.equal(withdrawOnly.canDeposit, false);
}

function testDepositOnlyForm(form) {
  const depositOnly = form.cashMovementCapabilities({
    canRead: false, canWithdraw: false, canDeposit: true,
  });
  assert.equal(depositOnly.canUse, true);
  assert.equal(depositOnly.canWrite, true);
  assert.equal(depositOnly.initialType, 'deposit');
  assert.equal(depositOnly.canWithdraw, false);
}

function testCompensationSemantics(form) {
  assert.equal(form.cashMovementCapabilities({
    canRead: true, canWithdraw: false, canDeposit: false, canCompensate: true,
  }).canCompensate, true);
  assert.equal(form.canCompensateLedgerItem(true, 'eligible'), true);
  for (const state of ['compensated', 'compensation', 'ineligible']) {
    assert.equal(form.canCompensateLedgerItem(true, state), false);
  }
  assert.equal(form.canCompensateLedgerItem(false, 'eligible'), false);
  assert.deepEqual(
    form.buildCashCompensationPayload(' Captura errónea ', ' evidence://owner/1 '),
    { reason: 'Captura errónea', evidence_refs: ['evidence://owner/1'] },
  );
}

function testLedgerLocalization(form) {
  const movementTypes = [
    ['deposit', 'Depósito'],
    ['withdrawal', 'Retiro'],
    ['cash_reversal', 'Reversión de efectivo'],
  ];
  for (const [movementType, label] of movementTypes) {
    assert.equal(form.cashMovementTypeLabel(movementType), label);
  }
  assert.equal(form.cashMovementTypeLabel('future_movement_type'), 'No disponible');

  const compensationStates = [
    ['eligible', 'Elegible para compensación'],
    ['compensated', 'Compensado'],
    ['compensation', 'Compensación'],
    ['ineligible', 'No elegible'],
  ];
  for (const [compensationState, label] of compensationStates) {
    assert.equal(form.cashCompensationStateLabel(compensationState), label);
  }
  assert.equal(form.cashCompensationStateLabel('future_compensation_state'), 'No disponible');
}

function testCompensationIntentLifecycle(form) {
  let state = form.initialCashCompensationFormState();
  state = form.reduceCashCompensationFormState(state, { type: 'open', target: 'movement-A' });
  state = form.reduceCashCompensationFormState(state, { type: 'set_reason', reason: 'Captura A' });
  state = form.reduceCashCompensationFormState(state, { type: 'set_evidence', evidence: 'evidence://A' });
  state = form.reduceCashCompensationFormState(state, { type: 'begin_submit', idempotencyKey: 'key-A' });
  state = form.reduceCashCompensationFormState(state, { type: 'uncertain_failure' });
  assert.deepEqual(state, {
    intent: {
      target: 'movement-A', reason: 'Captura A', evidence: 'evidence://A', idempotencyKey: 'key-A',
    },
    loading: false,
  });

  state = form.reduceCashCompensationFormState(state, { type: 'cancel' });
  assert.deepEqual(state, { intent: null, loading: false });
  state = form.reduceCashCompensationFormState(state, { type: 'open', target: 'movement-B' });
  assert.deepEqual(state, {
    intent: { target: 'movement-B', reason: '', evidence: '', idempotencyKey: null }, loading: false,
  });

  state = form.reduceCashCompensationFormState(state, { type: 'begin_submit', idempotencyKey: 'key-B' });
  const loading = state;
  state = form.reduceCashCompensationFormState(state, { type: 'cancel' });
  assert.equal(state, loading);
  state = form.reduceCashCompensationFormState(state, { type: 'open', target: 'movement-C' });
  assert.equal(state, loading);
  state = form.reduceCashCompensationFormState(state, { type: 'complete' });
  assert.deepEqual(state, { intent: null, loading: false });
}

try {
  const source = join(root, 'apps/pos-web/src/features/cash/cashMovementForm.ts');
  execFileSync(
    process.env.RESTAURANTOS_TSC || process.execPath,
    [
      ...(process.env.RESTAURANTOS_TSC ? [] : [join(root, 'node_modules/typescript/bin/tsc')]),
      '--target', 'ES2022',
      '--module', 'NodeNext',
      '--moduleResolution', 'NodeNext',
      '--outDir', output,
      source,
    ],
    { cwd: root, stdio: 'pipe' },
  );
  const form = await import(pathToFileURL(join(output, 'cashMovementForm.js')).href);
  assert.equal(form.parseCashCents('20'), 2000);
  assert.equal(form.parseCashCents('20.5'), 2050);
  assert.equal(form.parseCashCents('20.50'), 2050);
  for (const value of ['', '-1', '0', '20.001', 'NaN', '90071992547409.92']) {
    assert.equal(form.parseCashCents(value), null);
  }
  assert.equal(form.nextCashIdempotencyKey('retry-key'), 'retry-key');
  const afterSuccess = form.nextCashIdempotencyKey(null);
  const afterConflict = form.nextCashIdempotencyKey(null);
  assert.notEqual(afterSuccess, afterConflict);
  testReadOnlyLedger(form);
  testWithdrawOnlyForm(form);
  testDepositOnlyForm(form);
  testCompensationSemantics(form);
  testLedgerLocalization(form);
  testCompensationIntentLifecycle(form);

  const component = readFileSync(
    join(root, 'apps/pos-web/src/features/cash/CashMovements.tsx'),
    'utf8',
  );
  const app = readFileSync(join(root, 'apps/pos-web/src/App.tsx'), 'utf8');
  assert.match(component, /localStorage\.getItem\('pos_register_id'\)/);
  assert.match(component, /\/cash-shifts\/current\?/);
  assert.match(component, /\/cash\/movements\?branch_id=/);
  assert.match(component, /!capabilities\.canWrite/);
  assert.match(component, /capabilities\.canRead && <section aria-label="Ledger de caja">/);
  assert.match(component, /capabilities\.canWrite && <>/);
  assert.match(component, /setKey\(commandKey\)/);
  assert.match(component, /reduceCashCompensationFormState/);
  assert.match(component, /dispatchCompensation\(\{ type: 'cancel' \}\)/);
  assert.match(component, /buildCashCompensationPayload/);
  assert.match(component, /cashMovementTypeLabel\(item\.movement_type\)/);
  assert.match(component, /cashCompensationStateLabel\(item\.compensation_state\)/);
  assert.match(component, /cashMovementTypeLabel\(compensation\.intent\.target\.movement_type\)/);
  assert.match(component, /canCompensateLedgerItem\(capabilities\.canCompensate, item\.compensation_state\)/);
  assert.match(component, /\/cash\/movements\/\$\{encodeURIComponent\(intent\.target\.id\)\}\/compensations/);
  assert.match(component, /await refreshLedger\(\)/);
  assert.match(component, /Efectivo esperado:/);
  assert.match(component, /aria-label="Compensar movimiento"/);
  assert.match(component, /idempotency_conflict/);
  assert.match(component, /setKey\(null\)/);
  assert.doesNotMatch(component, /CAJA-01/);
  assert.match(app, /AnyPermissionRoute/);
  assert.doesNotMatch(component, /cash\.withdraw/);
} finally {
  rmSync(output, { recursive: true, force: true });
}
