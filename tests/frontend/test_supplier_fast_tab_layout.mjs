import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const drawer = readFileSync('apps/admin-web/src/components/FastTabDrawer.tsx', 'utf8');
const suppliers = readFileSync('apps/admin-web/src/features/purchasing/SuppliersList.tsx', 'utf8');
const styles = readFileSync('apps/admin-web/src/kiwi-modern-admin.css', 'utf8');

assert.match(drawer, /size\?:\s*'standard'\s*\|\s*'wide'/, 'FastTab debe permitir un ancho amplio explícito');
assert.match(drawer, /data-size=\{size\}/, 'FastTab debe exponer el ancho elegido al CSS');
assert.match(drawer, /fast-tab-drawer__body/, 'FastTab debe identificar su región desplazable');
assert.match(styles, /\.fast-tab-drawer__body\s*\{[^}]*min-height:\s*0[^}]*overflow-y:\s*auto/s, 'El cuerpo debe poder encogerse y desplazarse verticalmente');
assert.match(styles, /\.fast-tab-drawer\[data-size="wide"\]\s*\{[^}]*width:\s*680px/s, 'El panel amplio debe aprovechar el espacio de escritorio');
assert.match(suppliers, /<FastTabDrawer[\s\S]*?size="wide"/, 'CXP debe usar el panel amplio');

const readOnlySectionsStart = suppliers.indexOf('FastTab 2: Cartera de Facturas');
const editableFieldsetEnd = suppliers.indexOf('</fieldset>');
assert.ok(editableFieldsetEnd > -1 && editableFieldsetEnd < readOnlySectionsStart, 'Sólo el formulario editable debe quedar dentro del fieldset deshabilitable');

assert.doesNotMatch(suppliers, /F-9081|F-9204|A-9842|Flujo Semanal Compensado|Simulated enrichment/, 'La ficha no debe presentar deuda o trazabilidad de demostración');
assert.doesNotMatch(suppliers, /s\.credit_days\s*\|\|\s*15/, 'Abrir la ficha no debe sustituir un crédito cero');
assert.doesNotMatch(suppliers, /\.catch\(\(\) => \[\]/, 'Un error de consulta no debe convertirse en un catálogo vacío');

console.log('Supplier FastTab remains complete, scrollable, and interactive in read-only mode');
