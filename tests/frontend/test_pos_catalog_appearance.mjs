import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const settings = readFileSync('apps/pos-web/src/features/settings/Settings.tsx', 'utf8');
const pos = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');
const css = readFileSync('apps/pos-web/src/App.css', 'utf8');
const session = readFileSync('apps/pos-web/src/session.ts', 'utf8');

assert.match(settings, /Apariencia del catálogo/);
assert.match(settings, /Mostrar iconos e imágenes en grupos y productos/);
assert.match(settings, /Los iconos del menú superior siempre permanecen visibles/);
assert.match(settings, /hasPermission\('admin\.manage'\)/);
assert.match(settings, /\/pos-catalog-appearance/);
assert.match(session, /pos_catalog_visuals_enabled: boolean/);
assert.match(settings, /const saved = await fetchApi<[\s\S]*applyCatalogAppearance\(saved\.branch_id, saved\.visuals_enabled\)/,
  'La UI aplica el valor confirmado por el servidor sin sobrescribirlo con un gateway obsoleto');
assert.match(session, /applyCatalogAppearance[\s\S]*pos_catalog_visuals_enabled: visualsEnabled/,
  'La sesión activa adopta inmediatamente la preferencia confirmada');
assert.match(session, /gatewaySession[\s\S]*centralSession[\s\S]*pos_catalog_visuals_enabled[\s\S]*return \{\.\.\.gatewaySession, admin_capabilities:undefined\}/,
  'Con gateway, la sesión usa la preferencia central si hay red y conserva el bundle si está offline');
assert.match(session, /gatewaySession[\s\S]*if \(!navigator\.onLine\) return \{\.\.\.gatewaySession, admin_capabilities:undefined\};[\s\S]*fetchApi<PosSession>/,
  'Sin conectividad, la sesión del gateway no intenta consultar la apariencia en la API central');
assert.match(session, /centralSession\.user\.id === gatewaySession\.user\.id/,
  'La navegación administrativa usa sólo capacidades centrales del mismo usuario');
assert.match(session, /CENTRAL_APPEARANCE_TIMEOUT_MS[\s\S]*AbortController[\s\S]*signal: centralController\.signal[\s\S]*clearTimeout/,
  'El overlay central está acotado y no bloquea indefinidamente la continuidad del gateway');
assert.match(pos, /pos-sale-screen--catalog-text/);
assert.match(pos, /showCatalogVisuals \? getProductIcon/);
assert.match(pos, /showCatalogVisuals && presentation === 'image'/);
assert.match(pos, /pos-sale-menu[\s\S]*getCatalogGroupIcon\(group\.id\)/,
  'El menú superior conserva sus iconos sin condición');
assert.match(css, /\.pos-sale-screen--catalog-text[\s\S]*font-size:/,
  'El modo sin visuales aumenta la jerarquía del texto central');

console.log('test_pos_catalog_appearance.mjs PASSED');
