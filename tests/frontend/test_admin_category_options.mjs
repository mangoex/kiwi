import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-admin-category-options-'));

try {
  const source = join(root, 'apps/admin-web/src/features/catalog/categoryOptionEditorState.ts');
  execFileSync(join(root, 'node_modules/.bin/tsc'), [
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', temporaryDirectory, source,
  ], { cwd: root, stdio: 'pipe' });
  const editor = await import(pathToFileURL(join(temporaryDirectory, 'categoryOptionEditorState.js')).href);
  const activeGroup = { id: 'size', code: 'size', name: 'Tamaño', status: 'active' };
  const archivedSameGroup = { id: 'size', code: 'size', name: 'Nuevo tamaño', status: 'archived' };
  assert.deepEqual(editor.categoryOptionEditorState(activeGroup), {
    code: 'size', name: 'Tamaño', status: 'active',
  });
  assert.deepEqual(editor.categoryOptionEditorState(null), {
    code: '', name: '', status: 'inactive',
  });
  assert.notEqual(editor.categoryOptionEditorHydrationKey(activeGroup), editor.categoryOptionEditorHydrationKey(archivedSameGroup));
  assert.deepEqual(editor.categoryOptionEditorState(archivedSameGroup), {
    code: 'size', name: 'Nuevo tamaño', status: 'archived',
  });
  assert.deepEqual(editor.categoryOptionValueEditorState({
    id: 'small', code: 'small', name: 'Chica', display_order: 10, status: 'active',
  }), {
    id: 'small', code: 'small', name: 'Chica', displayOrder: 10, status: 'active',
  });
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
