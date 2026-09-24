import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const source = readFileSync('apps/admin-web/src/features/catalog/ProductsList.tsx', 'utf8');
assert.ok(
  existsSync('apps/admin-web/src/features/catalog/ProductTaxonomyQuickCreateModal.tsx'),
  'Productos debe contar con un diálogo de alta rápida para grupos y subgrupos',
);
const quickCreateSource = readFileSync('apps/admin-web/src/features/catalog/ProductTaxonomyQuickCreateModal.tsx', 'utf8');

assert.match(source, /\/catalog\/product-configurations/, 'Productos usa el comando canónico');
assert.match(source, /Idempotency-Key/, 'El guardado conserva una clave idempotente');
assert.match(source, /expected_updated_at/, 'La edición envía la versión observada');
assert.match(source, /value="drinks"/, 'Bebidas envía el código canónico');
assert.match(source, /value="kitchen"/, 'Cocina envía el código canónico');
assert.match(source, /value="packing"/, 'Empaque envía el código canónico');
assert.match(source, /Borrador sin guardar/, 'El alta se presenta como borrador');
assert.match(source, /pos-preview/, 'La vista previa consulta la proyección POS');
assert.match(source, /\/products\/\$\{selectedProduct!?\.id\}\/recipe/, 'La receta se consulta al backend');
assert.match(source, /beforeunload/, 'El borrador advierte antes de salir del navegador');
assert.match(source, /Hay cambios sin guardar/, 'Cambiar de registro exige descarte explícito');
assert.match(source, /recipes\.manage/, 'La receta respeta su permiso separado');
assert.match(source, /product_configuration_version_conflict/, 'Los conflictos se traducen sin anunciar éxito');
assert.doesNotMatch(source, /sampleDagNodes/, 'No se permiten recetas demostrativas');
assert.doesNotMatch(source, /Math\.random\(\)/, 'El navegador no genera SKU aleatorio');
assert.doesNotMatch(source, /La presentación familiar se conserva/, 'No se muestra una explicación interna de persistencia al operador');
assert.doesNotMatch(source, /navigate\('\/categories'\)/, 'Las altas rápidas no abandonan el borrador del producto');
assert.match(source, /aria-label="Crear grupo sin salir del producto"/, 'Grupo ofrece alta rápida contextual');
assert.match(source, /aria-label="Crear subgrupo para el grupo seleccionado"/, 'Subgrupo ofrece alta rápida contextual');
assert.match(source, /selectedCategory=\{formCategory\}/, 'El alta de subgrupo recibe el grupo elegido en el producto');
assert.match(source, /category_name: result\.group\.name[\s\S]*subgroup_value_id: ''/, 'El grupo creado queda seleccionado y limpia sólo el subgrupo anterior');
assert.match(source, /subgroup_value_id: result\.subgroup\.id/, 'El subgrupo creado queda seleccionado en el borrador');
assert.match(source, /setQueryData<Category\[]>\(\['categories'\]/, 'El grupo nuevo aparece inmediatamente antes de revalidar');
assert.match(source, /setQueryData<SubgroupCoverage>/, 'El subgrupo nuevo aparece inmediatamente antes de revalidar');
assert.match(quickCreateSource, /role="dialog"[\s\S]*aria-modal="true"/, 'El alta rápida se presenta como diálogo accesible');
assert.match(quickCreateSource, /\/categories[\s\S]*method: 'POST'/, 'El grupo se crea mediante la API canónica');
assert.match(quickCreateSource, /\/selection-group[\s\S]*method: 'POST'/, 'El selector de subgrupos se garantiza mediante la API canónica');
assert.match(quickCreateSource, /\/catalog\/category-option-groups\/\$\{groupId\}\/values[\s\S]*method: 'POST'/, 'El subgrupo se crea mediante la API canónica');
assert.match(quickCreateSource, /toLocaleUpperCase\('es-MX'\)/, 'Los nombres respetan el contrato canónico en mayúsculas');
assert.match(quickCreateSource, /Grupo seleccionado:/, 'El diálogo de subgrupo deja visible el grupo fijo');
assert.match(source, /useState<ProductConfigurationTab>\('Principal \/ Varios'\)/, 'El detalle abre en la presentación principal anterior');
for (const label of [
  'Principal / Varios',
  'Receta / Almacén ventas',
  'Precios promoción',
  'Imagen de producto',
  'Monedero electrónico',
  'Comentarios / Paquete',
  'Producto compuesto',
]) {
  assert.ok(source.includes(`label: '${label}'`), `Debe conservar la pestaña ${label}`);
}
assert.match(source, /name: selectedProduct\.name \|\| ''/, 'Seleccionar un producto carga su nombre en el detalle');
assert.match(source, /sku: selectedProduct\.sku \|\| ''/, 'Seleccionar un producto carga su clave en el detalle');
assert.match(source, /price_with_tax: priceNum/, 'Seleccionar un producto carga su precio en el detalle');
assert.match(source, /station: selectedProduct\.station \|\| ''/, 'Seleccionar un producto carga su estación en el detalle');
assert.match(
  source,
  /if \(isEditing \|\| isNew\)[\s\S]*setIsEditing\(false\)[\s\S]*setActiveTab\('Principal \/ Varios'\)[\s\S]*setSelectedProductId\(p\.id\)/,
  'Seleccionar una fila descarta la edición confirmada y muestra inmediatamente su detalle principal',
);
const commandPayload = source.match(/const payload = \{([\s\S]*?)\n      \};/)?.[1] || '';
assert.doesNotMatch(commandPayload, /tax_rate|service_dining|loyalty_accrual|barcode|open_price/, 'No se envían campos sin contrato');

console.log('test_admin_product_flow.mjs PASSED');
