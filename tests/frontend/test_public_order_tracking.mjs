import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import test from 'node:test';

const ts = createRequire(import.meta.url)('typescript');
const source = readFileSync('apps/mobile-web/src/orderTracking.ts', 'utf8');
const exports = {};
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
} }).outputText, { exports, AbortController, Date, Set, Map, Error, JSON });
const { readTrackedReferences, rememberTrackedReference, forgetTrackedReference,
  getTrackingPresentation, parseTrackingResponse, startTrackingPoller } = exports;
const branch = '018f6f73-2d0a-74f0-8f1c-000000000003';
const otherBranch = '018f6f73-2d0a-74f0-8f1c-000000000004';
const reference = 'PI-4EBD96B8CD984E039D024285164E3D89';
const secondReference = 'PI-E5B94172860B4FF3A78D3EA98D5378F6';
const state = (display = 'PENDING_REVIEW', service = 'takeout') => ({
  public_reference: reference, branch_id: branch, branch_name: 'Centro', status: 'PENDING_REVIEW',
  version: 1, total_cents: 22500, service_type: service,
  operational_status: null, display_status: display, folio: null,
  created_at: '2026-10-16T12:00:00+00:00', updated_at: '2026-10-16T12:00:00+00:00',
  terminal: ['DELIVERED', 'CLOSED', 'REJECTED', 'CANCELLED', 'EXPIRED', 'FAILED', 'RETURNED'].includes(display),
});

test('storage keeps only scoped capabilities, preserves active references and handles corruption', () => {
  let value = null;
  const storage = { getItem: () => value, setItem: (_, data) => { value = data; } };
  assert.equal(rememberTrackedReference(storage, { public_reference: reference, branch_id: branch }), true);
  rememberTrackedReference(storage, { public_reference: secondReference, branch_id: otherBranch });
  assert.equal(readTrackedReferences(storage, branch).references.length, 1);
  assert.equal(readTrackedReferences(storage, otherBranch).references[0].public_reference, secondReference);
  assert.equal(value.includes('customer'), false);
  forgetTrackedReference(storage, branch, reference);
  assert.equal(readTrackedReferences(storage, branch).references.length, 0);
  assert.equal(readTrackedReferences(storage, otherBranch).references.length, 1);
  value = '{bad';
  assert.equal(readTrackedReferences(storage, branch).references.length, 0);
  assert.equal(readTrackedReferences({ getItem() { throw Error('blocked'); } }, branch).available, false);
});

test('presentation never accepts a pending request or treats READY as dispatched', () => {
  assert.equal(getTrackingPresentation(state()).step, -1);
  assert.equal(getTrackingPresentation(state('ACCEPTED')).step, 0);
  assert.equal(getTrackingPresentation(state('READY', 'delivery')).step, 1);
  assert.match(getTrackingPresentation(state('READY', 'delivery')).title, /Listo para salir/);
  assert.equal(getTrackingPresentation(state('READY')).step, 2);
  assert.equal(getTrackingPresentation(state('IN_DELIVERY', 'delivery')).step, 2);
  assert.match(getTrackingPresentation(state('CLOSED')).title, /finalizado/i);
  assert.match(getTrackingPresentation(state('RETURNED')).title, /devuelto/i);
});

test('response validation rejects cross-branch, malformed and unknown state data', () => {
  assert.equal(parseTrackingResponse(state(), reference, branch).total_cents, 22500);
  for (const patch of [{ branch_id: otherBranch }, { public_reference: secondReference },
    { display_status: 'FAKE' }, { total_cents: 2.5 }, { updated_at: 'invalid' }, { terminal: true }]) {
    assert.throws(() => parseTrackingResponse({ ...state(), ...patch }, reference, branch));
  }
});

test('poller never overlaps, stops terminals and discards responses after disposal', async () => {
  const timers = new Map(); let nextTimer = 0, calls = 0, resolve;
  const updates = [];
  const stop = startTrackingPoller([{ public_reference: reference, branch_id: branch }], {
    request: async () => { calls++; return new Promise(done => { resolve = done; }); },
    onUpdate: value => updates.push(value), onError: () => {}, isVisible: () => true,
    subscribeVisibility: () => () => {},
    setTimer: fn => { timers.set(++nextTimer, fn); return nextTimer; },
    clearTimer: id => timers.delete(id),
  });
  assert.equal(calls, 1);
  assert.equal(timers.size, 0);
  stop(); resolve(state('READY'));
  await new Promise(done => setImmediate(done));
  assert.equal(updates.length, 0);
  assert.equal(timers.size, 0);

  let terminalCalls = 0;
  const stopTerminal = startTrackingPoller([{ public_reference: reference, branch_id: branch }], {
    request: async () => { terminalCalls++; return state('DELIVERED'); },
    onUpdate: () => {}, onError: () => {}, isVisible: () => true,
    subscribeVisibility: () => () => {},
    setTimer: fn => { timers.set(++nextTimer, fn); return nextTimer; },
    clearTimer: id => timers.delete(id),
  });
  await new Promise(done => setImmediate(done));
  assert.equal(terminalCalls, 1); assert.equal(timers.size, 0); stopTerminal();
});

test('Retry-After survives hide/show and poller recreation without advancing time', async () => {
  let now = 1000, visible = true, calls = 0, listener, deadline = 0, timer;
  const options = {
    request: async () => { calls++; throw new exports.TrackingRequestError(429, 60000); },
    onUpdate: () => {}, onError: () => {}, isVisible: () => visible,
    subscribeVisibility: fn => { listener = fn; return () => {}; },
    setTimer: (fn, delay) => { timer = { fn, delay }; return 1; }, clearTimer: () => { timer = undefined; },
    now: () => now, getRetryUntil: () => deadline, onRetryUntil: value => { deadline = value; },
  };
  const refs = [{ public_reference: reference, branch_id: branch }];
  let stop = startTrackingPoller(refs, options);
  await new Promise(done => setImmediate(done));
  assert.equal(calls, 1); assert.equal(timer.delay, 60000);
  visible = false; listener(); visible = true; listener();
  assert.equal(calls, 1); assert.equal(timer.delay, 60000);
  stop(); stop = startTrackingPoller(refs, options);
  assert.equal(calls, 1); assert.equal(timer.delay, 60000);
  now += 60000; timer.fn();
  await new Promise(done => setImmediate(done));
  assert.equal(calls, 2); stop();
});

test('hidden pages wait, and a response arriving after visibility changes is discarded', async () => {
  let visible = false, listener, calls = 0, resolve;
  const updates = [], timers = new Map(); let counter = 0;
  const stop = startTrackingPoller([{ public_reference: reference, branch_id: branch }], {
    request: async () => { calls++; return new Promise(done => { resolve = done; }); },
    onUpdate: value => updates.push(value), onError: () => {}, isVisible: () => visible,
    subscribeVisibility: fn => { listener = fn; return () => {}; },
    setTimer: fn => { timers.set(++counter, fn); return counter; }, clearTimer: id => timers.delete(id),
  });
  assert.equal(calls, 0);
  visible = true; listener(); assert.equal(calls, 1);
  visible = false; listener(); resolve(state('READY'));
  await new Promise(done => setImmediate(done));
  assert.equal(updates.length, 0); assert.equal(timers.size, 0); stop();
});
