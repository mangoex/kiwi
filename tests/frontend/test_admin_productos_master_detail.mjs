import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const products = readFileSync('apps/admin-web/src/features/catalog/ProductsList.tsx', 'utf8');

// 1. Split Layout Master-Detail structure
assert.match(products, /productos-window-container/);
assert.match(products, /productos-split-layout/);
assert.match(products, /productos-master-panel/);
assert.match(products, /productos-detail-panel/);
assert.match(products, /productos-table/);

// 2. Toolbar Actions
assert.match(products, /productos-toolbar/);
assert.match(products, /Nuevo/);
assert.match(products, /Guardar/);
assert.match(products, /Deshacer/);
assert.match(products, /Editar/);
assert.match(products, /Eliminar/);

// 3. Tab Strip & All 7 Tabs from reference image
assert.match(products, /<CapsuleTabs/);
assert.match(products, /items=\{PRODUCT_CONFIGURATION_TABS\}/);
assert.match(products, /Principal \/ Varios/);
assert.match(products, /label: 'Receta'/);
assert.match(products, /Precios promoción/);
assert.match(products, /Imagen de producto/);
assert.match(products, /Monedero electrónico/);
assert.match(products, /Comentarios de preparación \/ Paquete/);
assert.match(products, /Producto compuesto/);

// 4. Subgrupos integrados al detalle y administrados desde su catálogo canónico
assert.match(products, /category-option-coverage/);
assert.match(products, /Crear grupo sin salir del producto/);
assert.match(products, /Crear subgrupo para el grupo seleccionado/);

// 5. Preservation of Essential Tools and Invariants
assert.match(products, /ComboCompositionModal/);
assert.match(products, /Composición fija/);
assert.match(products, /ModifierManager/);
assert.match(products, /ProductOnboardingAiModal/);
assert.match(products, /Alta Guiada con IA/);

// 6. La receta canónica permanece integrada al producto seleccionado
assert.match(products, /import \{ RecipeManager, type RecipeWorkspaceItem \}/);
assert.match(products, /<RecipeManager/);

// 7. Search and Query Param Integration (Legacy import & Navigation)
assert.match(products, /useSearchParams/);
assert.match(products, /searchParams\.get\('search'\)/);
assert.match(products, /filteredProducts\.map/);

// 8. Safe Money and Error Handling
assert.match(products, /formatMoney/);
assert.match(products, /ProductosErrorBoundary/);

console.log('test_admin_productos_master_detail.mjs PASSED');
