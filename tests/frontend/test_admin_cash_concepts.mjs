import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const output = mkdtempSync(join(tmpdir(), 'restaurantos-admin-cash-concepts-'));

try {
  const source = join(root, 'apps/admin-web/src/features/cash/cashConceptState.ts');
  execFileSync(join(root, 'node_modules/.bin/tsc'), [
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', output, source,
  ], { cwd: root, stdio: 'pipe' });
  const state = await import(pathToFileURL(join(output, 'cashConceptState.js')).href);
  const form = {
    code: 'retiro_operativo', name: 'Retiro operativo', allowed_movement_type: 'withdrawal',
    valid_from: '2026-08-11T18:00',
  };
  assert.equal(state.createCashConceptPayload(form).code, 'RETIRO_OPERATIVO');
  assert.equal(Object.hasOwn(state.versionCashConceptPayload(form), 'code'), false);
  assert.equal(state.canManageCashConcepts({ permissions: ['cash.concept.manage'] }), true);
  assert.equal(state.canManageCashConcepts({ permissions: ['catalog.manage'] }), false);
  assert.equal(state.cashConceptViewState({ loading: true, error: '', conceptCount: 0 }), 'loading');
  assert.equal(state.cashConceptViewState({ loading: false, error: 'falló', conceptCount: 0 }), 'error');
  assert.equal(state.cashConceptViewState({ loading: false, error: '', conceptCount: 0 }), 'empty');
  assert.equal(state.cashConceptViewState({ loading: false, error: '', conceptCount: 1 }), 'data');
  assert.equal(state.retainSuccessMessageAfterLoad('Concepto publicado.'), 'Concepto publicado.');
  const keys = state.commandKeyStore();
  let generated = 0;
  const create = () => `key-${++generated}`;
  assert.equal(keys.get('create', create), 'key-1');
  assert.equal(keys.get('create', create), 'key-1');
  keys.clear('create');
  assert.equal(keys.get('create', create), 'key-2');
  const nativeStyleFactory = {
    prefix: 'native',
    create() { return `${this.prefix}-${++generated}`; },
  };
  assert.equal(
    keys.get('archive', () => nativeStyleFactory.create()),
    'native-3',
  );
  assert.throws(() => keys.get('broken', nativeStyleFactory.create), TypeError);

  const app = readFileSync(join(root, 'apps/admin-web/src/App.tsx'), 'utf8');
  const layout = readFileSync(join(root, 'apps/admin-web/src/components/AdminLayout.tsx'), 'utf8');
  const manager = readFileSync(join(root, 'apps/admin-web/src/features/cash/CashConceptsManager.tsx'), 'utf8');
  assert.match(app, /CashConceptManageRoute/);
  assert.match(layout, /hasCashConceptManage/);
  assert.match(manager, /loading \? <p>Cargando conceptos/);
  assert.match(manager, /No hay conceptos publicados/);
  assert.match(manager, /window\.confirm/);
  assert.match(manager, /Historial/);
  assert.match(manager, /role="status"/);
  assert.match(manager, /\(\) => crypto\.randomUUID\(\)/);
  assert.doesNotMatch(manager, /setMessage\(''\);\n    } catch/);
} finally {
  rmSync(output, { recursive: true, force: true });
}
