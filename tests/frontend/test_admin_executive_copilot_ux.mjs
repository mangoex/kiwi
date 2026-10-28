import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';

const source = readFileSync(
  new URL('../../apps/admin-web/src/features/dashboard/ExecutiveCopilot.tsx', import.meta.url),
  'utf8',
);

assert.match(source, /import '\.\/ExecutiveCopilot\.css';/);
assert.match(source, /className="executive-copilot"/);
assert.match(source, /aria-labelledby="executive-copilot-title"/);
assert.match(source, /className="executive-copilot__scope"/);
assert.match(source, /aria-label="Consulta para el Copiloto Ejecutivo"/);
assert.match(source, /aria-live="polite"/);
assert.match(source, /className="executive-copilot__empty"/);
assert.match(source, /className="executive-copilot__suggested-actions"/);
assert.doesNotMatch(source, /background: 'linear-gradient\(135deg, #0f172a/);

const styles = readFileSync(
  new URL('../../apps/admin-web/src/features/dashboard/ExecutiveCopilot.css', import.meta.url),
  'utf8',
);

assert.match(styles, /\.executive-copilot__quick-action:focus-visible/);
assert.match(styles, /@media \(max-width: 720px\)/);
assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
assert.match(styles, /min-height: 44px/);

// Exercise delayed responses and cancellation, including a transport that ignores AbortSignal.
const ts = createRequire(import.meta.url)('typescript');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React },
}).outputText;
function mount(branchId) {
  const state = [];
  const pending = [];
  const cleanup = [];
  const exports = {};
  const react = {
    createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
    useState: (initial) => {
      const index = state.push(initial) - 1;
      return [initial, value => { state[index] = value; }];
    },
    useRef: value => ({ current: value }),
    useEffect: effect => cleanup.push(effect()),
  };
  vm.runInNewContext(compiled, {
    exports, AbortController, console,
    require: name => {
      if (name === 'react') return { __esModule: true, default: react, ...react };
      if (name === '@restaurantos/api-client') return {
        fetchApi: (path, options) => new Promise((resolve, reject) => {
          pending.push({ path, options, resolve, reject });
        }),
      };
      return {};
    },
  });
  const tree = exports.ExecutiveCopilot({ selectedBranchId: branchId });
  const nodes = [];
  const visit = node => {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) return node.forEach(visit);
    nodes.push(node);
    visit(node.props?.children);
  };
  visit(tree);
  const ask = () => nodes.find(node => node.type === 'button'
    && node.props.className === 'executive-copilot__quick-action').props.onClick();
  return { state, pending, ask, unmount: () => cleanup.forEach(fn => fn?.()) };
}

const a = mount('branch-a');
const first = a.ask();
assert.equal(JSON.parse(a.pending[0].options.body).branch_id, 'branch-a');
assert.ok(a.pending[0].options.signal, 'Executive requests must support cancellation');
const second = a.ask();
assert.equal(a.pending[0].options.signal.aborted, true);
a.pending[1].resolve({ answer: 'latest' });
await second;
a.pending[0].resolve({ answer: 'stale' });
await first;
assert.equal(a.state[2].answer, 'latest', 'A late superseded result must not overwrite the latest');

const beforeUnmount = a.ask();
a.unmount();
assert.equal(a.pending[2].options.signal.aborted, true);
const b = mount('branch-b');
assert.equal(b.state[2], null, 'A new branch starts without results from the old branch');
a.pending[2].resolve({ answer: 'late branch-a' });
await beforeUnmount;
assert.equal(a.state[2].answer, 'latest', 'Unmounted component must ignore a late response');
assert.equal(b.state[2], null);
const rejected = b.ask();
b.unmount();
b.pending[0].reject(new Error('late transport error'));
await rejected;
assert.equal(b.state[3], null, 'An aborted request must not publish a stale error');
