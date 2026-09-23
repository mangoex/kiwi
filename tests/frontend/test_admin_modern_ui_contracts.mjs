import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

console.log('--- Verificando Contratos UI/UX y Sistema de Diseño (KiwiPOS Admin) ---');

// 1. Verificar existencia de componentes atómicos del Sistema de Diseño
const fastTabPath = 'apps/admin-web/src/components/FastTabDrawer.tsx';
const dagTreePath = 'apps/admin-web/src/components/DagTreeView.tsx';
const copilotPath = 'apps/admin-web/src/components/KiwiCopilotWidget.tsx';
const metricPath = 'apps/admin-web/src/components/MetricDataViz.tsx';

assert.ok(existsSync(fastTabPath), 'El componente FastTabDrawer debe existir');
assert.ok(existsSync(dagTreePath), 'El componente DagTreeView debe existir');
assert.ok(existsSync(copilotPath), 'El componente KiwiCopilotWidget debe existir');
assert.ok(existsSync(metricPath), 'El componente MetricDataViz debe existir');

// 2. Verificar contenido y contratos de FastTabDrawer (Cero Modales)
const fastTabContent = readFileSync(fastTabPath, 'utf8');
assert.match(fastTabContent, /FastTabDrawer/, 'Debe exportar FastTabDrawer');
assert.match(fastTabContent, /AccordionSection|FastTabAccordion/, 'Debe soportar acordeones contextuales (FastTabs)');
assert.match(fastTabContent, /w-\[460px\]|max-w-md|w-full sm:w-\[460px\]/, 'Debe tener ancho adecuado de slide-over');
assert.doesNotMatch(fastTabContent, /<dialog|<Modal.*isOpen.*centered/i, 'No debe usar modales centradas bloqueantes');

// 3. Verificar contenido de DagTreeView (BOM recursivo y modificadores)
const dagTreeContent = readFileSync(dagTreePath, 'utf8');
assert.match(dagTreeContent, /DagTreeView|DagNodeItem/, 'Debe exportar componentes de árbol DAG');
assert.match(dagTreeContent, /cost|costo/i, 'Debe recalcular o mostrar costos por nodo');
assert.match(dagTreeContent, /merma/i, 'Debe mostrar porcentaje o factor de merma');
assert.match(dagTreeContent, /modifier|modificador/i, 'Debe integrar modificadores de secuencia embebidos en el árbol');

// 4. Verificar KiwiCopilotWidget (Morado AI + Human-in-the-loop)
const copilotContent = readFileSync(copilotPath, 'utf8');
assert.match(copilotContent, /KiwiCopilotWidget|AdminCopilotWidget/, 'Debe exportar KiwiCopilotWidget');
assert.match(copilotContent, /human-in-the-loop|confirm|confirmación/i, 'Debe implementar paso de confirmación humana');
assert.match(copilotContent, /voice|mic|micrófono/i, 'Debe contemplar disparador o soporte para voz');
assert.match(copilotContent, /violet|purple|#7c3aed|#6b21a8/, 'Debe usar el acento Morado de IA');

// 5. Verificar integración en ProductsList
const productsPath = 'apps/admin-web/src/features/catalog/ProductsList.tsx';
const productsContent = readFileSync(productsPath, 'utf8');
assert.match(productsContent, /FastTabDrawer|FastTab/, 'ProductsList debe integrar el panel FastTab');
assert.match(productsContent, /selectedProduct|selectedRowId|selectedItem/, 'ProductsList debe manejar selección contextual de fila');
assert.match(productsContent, /bg-violet-50|bg-purple-50|border-violet|border-purple/, 'Fila seleccionada debe tener resaltado lavanda');

// 6. Verificar integración en SuppliersList (Proveedores y CXP)
const suppliersPath = 'apps/admin-web/src/features/purchasing/SuppliersList.tsx';
const suppliersContent = readFileSync(suppliersPath, 'utf8');
assert.match(suppliersContent, /FastTabDrawer|FastTab/, 'SuppliersList debe integrar el panel FastTab');
assert.match(suppliersContent, /saldo|balance|vencimiento|plazo/i, 'SuppliersList debe mostrar métricas de CXP y plazos');

console.log('✔ Todos los contratos del Sistema de Diseño UI/UX pasaron satisfactoriamente.');
