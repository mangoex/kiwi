import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync('apps/admin-web/src/features/catalog/ProductsList.tsx', 'utf8');

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
