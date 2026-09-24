import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const manager = readFileSync(
  resolve(root, 'apps/admin-web/src/features/catalog/ModifierManager.tsx'),
  'utf8',
);
const styles = readFileSync(
  resolve(root, 'apps/admin-web/src/features/catalog/ModifierManager.css'),
  'utf8',
);
const products = readFileSync(
  resolve(root, 'apps/admin-web/src/features/catalog/ProductsList.tsx'),
  'utf8',
);

assert.match(manager, /import '\.\/ModifierManager\.css';/);
assert.match(manager, /className="modifier-manager"/);
assert.match(manager, /className="modifier-group-card"/);
assert.match(manager, /className="modifier-group-fields"/);
assert.match(manager, /className="modifier-option-row"/);
assert.match(manager, /className="modifier-row-actions"/);
assert.match(manager, /className="modifier-control"/);
assert.match(manager, /className="modifier-add-button modifier-add-button--option"/);
assert.match(manager, /className="modifier-add-button modifier-add-button--group"/);

assert.match(styles, /\.modifier-control\s*\{[^}]*min-height:\s*40px/s);
assert.match(styles, /\.modifier-control\s*\{[^}]*border-radius:\s*10px/s);
assert.match(styles, /\.modifier-row-action\s*\{[^}]*width:\s*38px[^}]*height:\s*38px/s);
assert.match(styles, /\.modifier-add-button\s*\{[^}]*align-self:\s*flex-start/s);
assert.match(styles, /\.modifier-add-button\s*\{[^}]*width:\s*fit-content/s);
assert.match(styles, /@media \(max-width:\s*760px\)/);

assert.match(products, /className="productos-compound-intro"/);
assert.match(products, /className="productos-compound-preview"/);
