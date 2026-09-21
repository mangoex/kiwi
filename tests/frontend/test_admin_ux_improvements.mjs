import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const itemsFile = readFileSync('apps/admin-web/src/features/inventory/ItemsList.tsx', 'utf8');
const productsFile = readFileSync('apps/admin-web/src/features/catalog/ProductsList.tsx', 'utf8');

// UX-001: Badges de Costeo en Insumos (Solo lectura y semánticos)
assert.match(itemsFile, /Badge variant="default"/i, 'Debe usar un componente Badge o equivalente semántico visual para mostrar el Costo Promedio/Último Costo');

// UX-002: Botones [+] in-line en Insumos (Alta sin perder contexto)
assert.match(itemsFile, /<Plus size=\{16\} \/>/i, 'Debe incluir un boton con icono Plus adyacente al selector de categoría');

// UX-003: Icon Toggles para Canales de Venta en Productos (Comedor, Domicilio, Rápido)
assert.match(productsFile, /ToggleSwitch.*Comedor/i, 'Debe usar un ToggleSwitch para el servicio Comedor en vez de checkbox');
assert.match(productsFile, /ToggleSwitch.*Domicilio/i, 'Debe usar un ToggleSwitch para el servicio Domicilio en vez de checkbox');
assert.match(productsFile, /ToggleSwitch.*Rápido/i, 'Debe usar un ToggleSwitch para el servicio Rápido en vez de checkbox');

// UX-004: Barra Sticky de KPIs en Recetas (Productos)
assert.match(productsFile, /sticky-kpi-bar/i, 'Debe contener un contenedor sticky-kpi-bar en la pestaña de Recetas');

// UX-005: Autocompletado In-line (Typeahead) en Recetas
assert.match(productsFile, /Typeahead|Combobox|Autocomplete/i, 'Debe usar un componente de autocompletado para buscar insumos in-line en la receta');

console.log('test_admin_ux_improvements.mjs PASSED');
