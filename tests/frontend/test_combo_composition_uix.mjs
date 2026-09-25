import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const modal = readFileSync('apps/admin-web/src/features/catalog/ComboCompositionModal.tsx', 'utf8');
const styles = readFileSync('apps/admin-web/src/features/catalog/ComboCompositionModal.css', 'utf8');
const products = readFileSync('apps/admin-web/src/features/catalog/ProductsList.tsx', 'utf8');
const productStyles = readFileSync('apps/admin-web/src/features/catalog/ProductosWindow.css', 'utf8');

assert.match(modal, /import '\.\/ComboCompositionModal\.css';/);
assert.match(modal, /size="lg"/);
assert.match(modal, /contentClassName="combo-composition-modal"/);
assert.match(modal, /className="combo-composition-editor"/);
assert.match(modal, /className="combo-composition-intro"/);
assert.match(modal, /Componentes siempre incluidos/);
assert.match(modal, /Si el cliente puede elegir/);
assert.match(modal, /className="combo-composition-scope"/);
assert.match(modal, /className="combo-component-row"/);
assert.match(modal, /className="combo-composition-control"/);
assert.match(modal, /className="combo-remove-button"/);

assert.match(styles, /\.combo-composition-control\s*\{[^}]*min-height:\s*40px/s);
assert.match(styles, /\.combo-composition-control\s*\{[^}]*border-radius:\s*10px/s);
assert.match(styles, /\.combo-remove-button\s*\{[^}]*width:\s*40px[^}]*height:\s*40px/s);
assert.match(styles, /@media \(max-width:\s*640px\)/);

assert.match(products, /className="productos-fixed-combo-card"/);
assert.match(products, /Combo o paquete fijo/);
assert.match(products, /Configurar combo fijo/);
assert.match(products, /usa Producto compuesto/);
assert.match(productStyles, /\.productos-fixed-combo-card/);

// El rediseño no cambia el contrato funcional ni el comando versionado.
assert.match(modal, /fetchApi<Composition>\(`\/products\/\$\{product\.id\}\/composition`/);
assert.match(modal, /'Idempotency-Key': idempotencyKey\.current/);
assert.match(modal, /expected_version: expectedVersion/);
