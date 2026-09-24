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
const commandPayload = source.match(/const payload = \{([\s\S]*?)\n      \};/)?.[1] || '';
assert.doesNotMatch(commandPayload, /tax_rate|service_dining|loyalty_accrual|barcode|open_price/, 'No se envían campos sin contrato');

console.log('test_admin_product_flow.mjs PASSED');
