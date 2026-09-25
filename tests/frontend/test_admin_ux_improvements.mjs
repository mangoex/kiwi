import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const itemsFile = readFileSync('apps/admin-web/src/features/inventory/ItemsList.tsx', 'utf8');
const productsFile = readFileSync('apps/admin-web/src/features/catalog/ProductsList.tsx', 'utf8');

// UX-001: Badges de Costeo en Insumos (Solo lectura y semánticos)
assert.match(itemsFile, /Badge variant="default"/i, 'Debe usar un componente Badge o equivalente semántico visual para mostrar el Costo Promedio/Último Costo');

// UX-002: Botones [+] in-line en Insumos (Alta sin perder contexto)
assert.match(itemsFile, /<Plus size=\{16\} \/>/i, 'Debe incluir un boton con icono Plus adyacente al selector de categoría');

// UX-003: el editor no simula canales de venta que no puede persistir ni aplicar en POS.
assert.doesNotMatch(
  productsFile,
  /service_dining|service_delivery|service_quick|affects_guest_count|Utilizar en Servicio|Afecta comensales en servicio rápido/,
  'No debe presentar modalidades de servicio ni conteo rápido sin contrato canónico',
);

console.log('test_admin_ux_improvements.mjs PASSED');
