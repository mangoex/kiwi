import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const categories = readFileSync('apps/admin-web/src/features/catalog/CategoriesList.tsx', 'utf8');
const products = readFileSync('apps/admin-web/src/features/catalog/ProductsList.tsx', 'utf8');
const categoryNavigation = readFileSync('apps/admin-web/src/components/CategorySubNav.tsx', 'utf8');
const app = readFileSync('apps/admin-web/src/App.tsx', 'utf8');
const pos = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');

assert.match(categories, /Grupos y subgrupos/, 'La administración debe usar el lenguaje operativo acordado');
assert.match(categories, /group-subgroup-workspace/, 'La pantalla debe integrar lista maestra y detalle');
assert.match(categories, /\/categories\/\$\{selectedCategoryId\}\/selection-group/, 'La estación debe leer subgrupos canónicos');
assert.match(categories, /category-option-groups[\s\S]*assignments/, 'La cobertura debe persistir asignaciones explícitas');
assert.match(categories, /Productos del grupo/, 'La cobertura de productos debe estar visible en la misma estación');
assert.doesNotMatch(categories, /Nombre del nivel/, 'La UI primaria no debe pedir el nombre técnico del nivel');
assert.doesNotMatch(categories, /Código interno/, 'La UI primaria no debe pedir el código técnico del selector');
assert.doesNotMatch(categories, /Estado del nivel/, 'La UI primaria no debe exponer la máquina de estados técnica');
assert.doesNotMatch(categories, /Guardar configuración/, 'No debe existir una segunda acción redundante para el estado del selector');
assert.match(categories, /Mostrar subgrupos en POS/, 'La publicación debe expresarse con una sola acción operativa');
assert.match(categories, /Nombre del subgrupo/, 'La captura primaria debe solicitar únicamente el nombre visible');

assert.doesNotMatch(products, /INITIAL_SUBGROUPS/, 'Productos no debe conservar un catálogo de subgrupos simulado');
assert.doesNotMatch(products, /setSubgroups\(/, 'Productos no debe crear subgrupos sólo en memoria');
assert.match(products, /category-option-coverage/, 'Productos debe consultar la cobertura canónica del grupo seleccionado');
assert.match(products, /category-option-groups[\s\S]*assignments/, 'Guardar Producto debe persistir la asignación canónica');
assert.match(products, /subgroup_value_id/, 'El formulario debe conservar el ID estable del subgrupo, no su etiqueta');

assert.doesNotMatch(categoryNavigation, /label: 'Selector previo'/, 'La navegación no debe presentar un catálogo paralelo');
assert.match(app, /path="category-options"[\s\S]*Navigate[\s\S]*categories/, 'La ruta heredada debe converger en la estación integrada');
assert.match(pos, />Grupos</, 'El POS debe presentar el nivel de categorías como Grupos');
assert.match(pos, /Subgrupos/, 'El POS debe presentar el selector previo como Subgrupos');

console.log('test_admin_group_subgroup_workspace.mjs PASSED');
