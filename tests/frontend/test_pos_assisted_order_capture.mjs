import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const output = mkdtempSync(join(tmpdir(), 'restaurantos-pos-assisted-order-'));
try {
  const source = join(root, 'apps/pos-web/src/features/pos/assistedOrderDraft.ts');
  execFileSync(process.execPath, [join(root, 'node_modules/typescript/bin/tsc'), '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext', '--outDir', output, source]);
  const draftApi = await import(pathToFileURL(join(output, 'assistedOrderDraft.js')).href);
  const option = { id: 'bread-a', name: 'Pan integral', price_delta_cents: 0, kind: 'modifier' };
  const question = { line_index: 0, group_id: 'bread', prompt: 'Elige pan', minimum_selections: 1, maximum_selections: 1, options: [option] };
  const draft = { customer_name: '', phone: '', order_type: 'takeout', lines: [{ product_id: 'p1', product_name: 'Producto', quantity: 1, selected_options: [] }], questions: [question], status: 'needs_input', model: 'none' };
  assert.equal(draftApi.isAssistedDraftComplete(draft), false);
  const selected = draftApi.toggleAssistedOption(draft, question, option);
  assert.equal(draftApi.selectedForQuestion(selected, question).length, 1);
  assert.equal(draftApi.isAssistedDraftComplete(selected), true);
  assert.equal(selected.status, 'ready');
  assert.equal(draftApi.toggleAssistedOption(selected, question, option).status, 'needs_input');
} finally {
  rmSync(output, { recursive: true, force: true });
}
