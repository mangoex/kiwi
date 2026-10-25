import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const pos = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');
const styles = readFileSync('apps/pos-web/src/App.css', 'utf8');
const operations = readFileSync('apps/api/restaurant_os/operations.py', 'utf8');

assert.match(pos, /component_modifiers: modifier\.component_modifiers/);
assert.match(pos, /\/products\/\$\{option\.component_product_id\}\/modifiers/);
assert.match(pos, /componentMinimumsMet/);
assert.match(pos, /Opciones de \$\{option\.name\}/);
assert.match(pos, /toggleComponentModifier/);
assert.match(styles, /\.pos-sale-component-modifiers/);
assert.doesNotMatch(styles, /\.pos-sale-complement-option button \{[^}]*aspect-ratio:\s*1/);
assert.match(operations, /def _get_available_component_product/);
assert.match(operations, /component_product = _get_available_component_product/);

console.log('POS selectable component semantic checks passed');
