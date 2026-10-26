import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const pos = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');
const styles = readFileSync('apps/pos-web/src/App.css', 'utf8');
const operations = readFileSync('apps/api/restaurant_os/operations.py', 'utf8');

assert.match(pos, /component_modifiers: modifier\.component_modifiers/);
assert.match(pos, /\/products\/\$\{option\.component_product_id\}\/modifiers/);
assert.match(pos, /componentMinimumsMet/);
assert.match(pos, /Opciones de \$\{activeComponentOption\.name\}/);
assert.match(pos, /toggleComponentModifier/);
assert.match(pos, /activeComponentOptionId/, 'POS debe separar la selección del componente de su vista de personalización');
assert.match(pos, /componentDrilldownAfterToggle/, 'Elegir un componente debe abrir sus modificadores hijos');
assert.match(pos, /openModifierGroup/, 'Tocar Ensalada o Baguette debe volver a las opciones de ese grupo');
assert.match(pos, /pos-sale-component-option-grid/, 'Los modificadores hijos deben mostrarse como una cuadrícula');
assert.match(pos, /pos-sale-component-option-card/, 'Pan y queso deben ser tarjetas táctiles, no una lista');
assert.match(styles, /\.pos-sale-component-modifiers/);
assert.match(styles, /\.pos-sale-component-option-grid/);
assert.match(styles, /\.pos-sale-component-option-card/);
assert.doesNotMatch(styles, /\.pos-sale-complement-option button \{[^}]*aspect-ratio:\s*1/);
assert.doesNotMatch(pos, /type=\{childGroup\.maximum_selections === 1 \? 'radio' : 'checkbox'\}/, 'La personalización hija no debe volver a listas de radio o checkbox');
assert.match(operations, /def _get_available_component_product/);
assert.match(operations, /component_product = _get_available_component_product/);

console.log('POS selectable component semantic checks passed');
