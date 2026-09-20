import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const itemsFile = readFileSync('apps/admin-web/src/features/inventory/ItemsList.tsx', 'utf8');

// 1. Verificación de compatibilidad con asistente AI
assert.match(itemsFile, /admin_ai_selection/, 'Debe preservar el filtro de selección de Admin AI');

// 2. Verificación de estructura Master-Detail (dos columnas)
assert.match(itemsFile, /insumos-split-layout|insumos-window-layout/, 'Debe tener layout split de dos columnas');
assert.match(itemsFile, /insumos-master-panel/, 'Debe tener panel izquierdo Master (lista de insumos)');
assert.match(itemsFile, /insumos-detail-panel/, 'Debe tener panel derecho Detail (ficha y datos)');

// 3. Verificación de columnas de la tabla Master
assert.match(itemsFile, /Clave|SKU/, 'Debe incluir columna Clave/SKU en la tabla');
assert.match(itemsFile, /Descripción|Nombre/, 'Debe incluir columna Descripción en la tabla');
assert.match(itemsFile, /Costo/, 'Debe incluir columna Costo en la tabla');
assert.match(itemsFile, /Unidad/, 'Debe incluir columna Unidad en la tabla');

// 4. Verificación de barra de herramientas superior retro
assert.match(itemsFile, /insumos-toolbar/, 'Debe contener la barra de herramientas de acciones');
assert.match(itemsFile, /Nuevo/, 'Debe incluir acción Nuevo');
assert.match(itemsFile, /Guardar/, 'Debe incluir acción Guardar');
assert.match(itemsFile, /Deshacer|Cancelar/, 'Debe incluir acción Deshacer/Cancelar');
assert.match(itemsFile, /Editar/, 'Debe incluir acción Editar');

// 5. Verificación de accesos rápidos a catálogos subordinados ([+] botones)
assert.match(itemsFile, /openCategoryModal|isCategoryModalOpen/, 'Debe permitir abrir modal rápido de Grupos/Categorías');
assert.match(itemsFile, /openUnitModal|isUnitModalOpen/, 'Debe permitir abrir modal rápido de Unidades de medida');

// 6. Verificación de sub-tabla de Presentaciones vinculadas
assert.match(itemsFile, /Presentaciones/i, 'Debe incluir sección de presentaciones de compra');
assert.match(itemsFile, /purchase-presentations/, 'Debe consultar presentaciones de compra');
assert.match(itemsFile, /openPresentationModal|isPresentationModalOpen/, 'Debe permitir abrir modal para agregar presentación');

// 7. Verificación de consultas inversas y umbrales (PRD-FR-240 y PRD-FR-241)
assert.match(itemsFile, /RecipeUsagesModal/, 'Debe conservar acceso a recetas que usan el insumo');
assert.match(itemsFile, /inventory\/thresholds/, 'Debe ofrecer acceso directo a umbrales de stock');

// 8. Invariante: Los costos derivados deben ser de sólo lectura en el formulario
assert.doesNotMatch(itemsFile, /onChange=.*average_unit_cost/, 'El costo promedio no debe ser editable directamente');
assert.doesNotMatch(itemsFile, /onChange=.*last_unit_cost/, 'El último costo no debe ser editable directamente');

console.log('Admin Insumos Master-Detail semantic contract passed');
