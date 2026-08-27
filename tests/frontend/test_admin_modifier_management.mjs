import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const source = readFileSync(
  resolve(root, 'apps/admin-web/src/features/catalog/ModifierManager.tsx'),
  'utf8',
);

assert.match(source, /editingGroupId \? 'PATCH' : 'POST'/);
assert.match(source, /editingOptionId \? 'PATCH' : 'POST'/);
assert.match(source, /fetchApi\(`\/products\/\$\{productId\}\/modifier-groups`\)/);
assert.doesNotMatch(source, /branch_id=/);
assert.match(source, /fetchApi\(`\/modifier-groups\/\$\{groupId\}`[^]*method: 'DELETE'/);
assert.match(source, /fetchApi\(`\/modifier-options\/\$\{optionId\}`[^]*method: 'DELETE'/);
assert.match(source, />Editar grupo</);
assert.match(source, />Eliminar grupo</);
assert.match(source, />Editar</);
assert.match(source, />Eliminar</);
assert.match(source, /pedidos históricos se conservarán/);
assert.match(source, /!option\.variation_kind && option\.effect_type !== 'preset_instruction'/);
assert.match(source, /option\.catalog_price_delta_cents \?\? option\.price_delta_cents/);
