import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const manager = readFileSync(
  resolve(root, 'apps/admin-web/src/features/catalog/ModifierManager.tsx'),
  'utf8',
);
const products = readFileSync(
  resolve(root, 'apps/admin-web/src/features/catalog/ProductsList.tsx'),
  'utf8',
);
const compoundTools = readFileSync(
  resolve(root, 'apps/admin-web/src/features/catalog/CompoundCopyPanel.tsx'),
  'utf8',
);
const pos = readFileSync(
  resolve(root, 'apps/pos-web/src/features/pos/PointOfSale.tsx'),
  'utf8',
);

assert.match(manager, /configurationEndpoint = endpointBase \|\| `\/products\/\$\{productId\}\/modifier-configuration`/);
assert.match(manager, /fetchApi(?:<SaveResult>)?\(configurationEndpoint/);
assert.doesNotMatch(manager, /branch_id=/);
assert.match(manager, /'Idempotency-Key'/);
assert.match(manager, /expected_version/);
assert.match(manager, /included_selections/);
assert.match(manager, /component_product_id/);
assert.match(manager, /Producto componente/);
assert.match(manager, /selecciones incluidas/i);
assert.match(manager, /const blankGroup = \(\): ModifierGroup => \([\s\S]*?included_selections: 0,/);
assert.match(manager, /0 cobra cada opción desde la primera/);
assert.match(manager, /modifier_configuration_version_conflict/);
assert.match(manager, /Tu borrador se conserva/);
assert.match(manager, /mxnToCentsExact/);
assert.match(manager, /Agregar grupo de selección/);
assert.match(manager, /Eliminar grupo/);
assert.match(manager, /Eliminar opción/);
assert.match(manager, /pedidos anteriores conservan su selección original/);
assert.ok(
  manager.indexOf('<fieldset') < manager.indexOf('<CompoundSelectionPreview'),
  'el editor debe aparecer antes que la vista previa',
);
assert.ok(
  manager.indexOf('<fieldset') < manager.indexOf('<CompoundCopyPanel'),
  'el editor debe aparecer antes que la herramienta de copia',
);
assert.match(compoundTools, /fetchApi<[^>]+>\('\/catalog\/products'\)/);
assert.doesNotMatch(compoundTools, /fetchApi(?:<[^>]+>)?\('\/products'\)/);
assert.match(compoundTools, /productsQuery\.isError/);
assert.match(compoundTools, /filter\(\(product\) => product\.catalog_scope === 'organization'\)/);
assert.match(compoundTools, /if \(pending \|\| \(!uncertain && \(productsQuery\.isError/);
assert.match(compoundTools, /disabled=\{disabled \|\| pending \|\| \(!uncertain && \(catalogUnavailable/);
assert.match(compoundTools, /Calcular vista previa/);
assert.match(compoundTools, /item_name/);
assert.match(compoundTools, /centsToMxn/);
assert.doesNotMatch(compoundTools, /parseFloat|Math\.round/);
assert.doesNotMatch(products, /ModifierManager|Modificadores \/ Producto compuesto/);
assert.doesNotMatch(products, /Abrir Administrador de Modificadores/);
assert.match(pos, /group\.included_selections/);
assert.match(pos, /selectionIndex < \(group\.included_selections \|\| 0\)/);
assert.match(pos, /included \? 0 : option\.price_delta_cents/);
assert.match(pos, /Incluido/);
assert.match(pos, /modifier\.price_delta_cents > 0/);
assert.match(pos, /Recargo/);
assert.match(pos, /Sin recargo/);
