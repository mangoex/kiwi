import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const source = readFileSync(
  join(root, 'apps/kds-web/src/features/orders/KitchenBoard.tsx'),
  'utf8',
);

assert.match(source, /fetchApi<KdsSession>\('\/auth\/session'\)/);
assert.match(source, /permissions\.includes\('kds\.tasks\.operate'\)/);
assert.match(source, /`\/kds\/tasks\?branch_id=\$\{encodeURIComponent\(branchId\)\}`/);
assert.match(source, /fetchApi\(`\/kds\/tasks\/\$\{encodeURIComponent\(task\.id\)\}\/transition`/);
assert.match(source, /JSON\.stringify\(\{ status: nextStatus, branch_id: branch\?\.id \}\)/);
assert.match(source, /viewState === 'loading'/);
assert.match(source, /role="alert"/);
assert.match(source, /columnTasks\.length === 0/);
assert.doesNotMatch(source, /#10(?:39|41|42)/);
assert.doesNotMatch(source, /Ensalada Saludable|Smoothie Tropical|Corte Ahumado/);
