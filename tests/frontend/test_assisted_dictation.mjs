import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';

const root = resolve('.');
const output = mkdtempSync(join(tmpdir(), 'dictation-'));

try {
  execFileSync(process.execPath, [
    join(root, 'node_modules/typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
    '--outDir', output, join(root, 'apps/pos-web/src/features/pos/assistedDictation.ts'),
  ]);
  const dictation = await import(`file://${join(output, 'assistedDictation.js')}`);

  assert.equal(dictation.appendDictationText('hola', ' mundo'), 'hola mundo');
  assert.equal(dictation.appendDictationText('x'.repeat(999), ' dos'), 'x'.repeat(999));
  assert.equal(dictation.shouldRestartDictation(2999, 0, false), true);
  assert.equal(dictation.shouldRestartDictation(3000, 0, false), false);
  assert.equal(dictation.shouldRestartDictation(1, 0, true), false);
  assert.equal(
    dictation.appendDictationText(dictation.appendDictationText('primera', ' frase'), ' segunda'),
    'primera frase segunda',
  );
} finally {
  rmSync(output, { recursive: true, force: true });
}
