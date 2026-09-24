import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const productsPath = 'apps/admin-web/src/features/catalog/ProductsList.tsx';
const capsuleTabsPath = 'apps/admin-web/src/components/ui/CapsuleTabs.tsx';
const capsuleTabsStylesPath = 'apps/admin-web/src/components/ui/CapsuleTabs.css';

assert.ok(existsSync(capsuleTabsPath), 'Debe existir el componente reutilizable CapsuleTabs');
assert.ok(existsSync(capsuleTabsStylesPath), 'CapsuleTabs debe tener estilos encapsulados para el proyecto sin Tailwind');

const productsFile = readFileSync(productsPath, 'utf8');
const capsuleTabsFile = readFileSync(capsuleTabsPath, 'utf8');

assert.match(
  productsFile,
  /<CapsuleTabs[\s\S]*items=\{PRODUCT_CONFIGURATION_TABS\}/,
  'Productos debe integrar CapsuleTabs con sus secciones de configuración',
);
assert.match(capsuleTabsFile, /ChevronLeft[\s\S]*ChevronRight/, 'CapsuleTabs debe ofrecer navegación anterior y siguiente');
assert.match(capsuleTabsFile, /role="tablist"/, 'CapsuleTabs debe exponer semántica accesible de lista de pestañas');
assert.match(capsuleTabsFile, /aria-selected=\{isActive\}/, 'CapsuleTabs debe anunciar la pestaña activa');
assert.match(capsuleTabsFile, /scrollBy/, 'CapsuleTabs debe desplazar el carril sin ocultar pestañas');
assert.match(capsuleTabsFile, /scrollIntoView/, 'CapsuleTabs debe mantener visible la pestaña activa');
assert.match(capsuleTabsFile, /items\.map/, 'CapsuleTabs debe renderizar todas las pestañas en el carril');
assert.doesNotMatch(capsuleTabsFile, /capsule-tabs__dot|Página \{/, 'CapsuleTabs no debe paginar ni ocultar pestañas');
assert.match(
  capsuleTabsFile,
  /ArrowRight[\s\S]*ArrowLeft[\s\S]*Home[\s\S]*End/,
  'CapsuleTabs debe permitir recorrer pestañas con teclado',
);

console.log('test_product_capsule_tabs.mjs PASSED');
