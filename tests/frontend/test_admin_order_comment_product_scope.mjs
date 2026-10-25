import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const helperSource = join(
  root,
  'apps/admin-web/src/features/catalog/orderCommentProductScope.ts',
);

assert.ok(
  existsSync(helperSource),
  'RED POS-COMMENTS-001: falta el módulo puro de selección individual por producto',
);

const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-order-comment-scope-'));

try {
  execFileSync(
    process.execPath,
    [
      join(root, 'node_modules/typescript/bin/tsc'),
      '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
      '--outDir', temporaryDirectory, helperSource,
    ],
    { cwd: root, stdio: 'pipe' },
  );
  const scope = await import(
    pathToFileURL(join(temporaryDirectory, 'orderCommentProductScope.js')).href
  );

  assert.deepEqual(
    Object.keys(scope).sort(),
    [
      'assignmentImpact',
      'categorySelectionState',
      'removeProductFromAssignment',
      'toggleCategoryProducts',
      'toggleProductSelection',
    ],
  );
  assert.equal(scope.categorySelectionState(['p1', 'p2'], []), 'none');
  assert.equal(scope.categorySelectionState(['p1', 'p2'], ['p1']), 'partial');
  assert.equal(scope.categorySelectionState(['p1', 'p2'], ['p1', 'p2']), 'all');
  assert.deepEqual(scope.toggleProductSelection(['p1'], 'p2', true), ['p1', 'p2']);
  assert.deepEqual(scope.toggleProductSelection(['p1', 'p2'], 'p1', false), ['p2']);
  assert.deepEqual(
    scope.toggleCategoryProducts(['p3'], ['p1', 'p2'], true),
    ['p1', 'p2', 'p3'],
  );
  assert.deepEqual(
    scope.toggleCategoryProducts(['p1', 'p2', 'p3'], ['p1', 'p2'], false),
    ['p3'],
  );
  assert.deepEqual(
    scope.assignmentImpact(['p1', 'p2'], ['p2', 'p3']),
    { added: ['p3'], removed: ['p1'], retained: ['p2'] },
  );
  assert.deepEqual(scope.removeProductFromAssignment(['p2', 'p1', 'p2'], 'p1'), ['p2']);
  assert.equal(scope.removeProductFromAssignment(['p1'], 'p1'), null);
  assert.equal(scope.removeProductFromAssignment(['p1', 'p2'], 'missing'), null);
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}

const screen = readFileSync(
  join(root, 'apps/admin-web/src/features/catalog/VariationNotes.tsx'),
  'utf8',
);
const responsiveStyles = readFileSync(
  join(root, 'apps/admin-web/src/features/catalog/VariationNotes.css'),
  'utf8',
);

for (const contract of [
  'categorySelectionState',
  'toggleCategoryProducts',
  'toggleProductSelection',
  'assignmentImpact',
  'removeProductFromAssignment',
  'expandedCategoryIds',
  'expandedCommentIds',
  'product.product_name',
  'product.product_sku',
  'Seleccionar todos',
  'Quitar todos',
  'showArchived',
  'activeComments',
  'archiveAll',
  '/catalog/order-comments/archive-all',
  'Archivar todos los comentarios activos',
  'Mostrar archivados',
  "method: 'DELETE'",
  '/catalog/order-comments/all',
  'Eliminar todos los comentarios',
  'deleteTarget',
  'catalogMutationPending',
  '|| apply.isPending',
  '|| save.isPending',
  '|| replaceProducts.isPending',
  '|| removeProduct.isPending',
  'order-comment-action',
]) {
  assert.ok(screen.includes(contract), `VariationNotes debe integrar ${contract}`);
}

const catalogAdministration = readFileSync(
  join(root, 'apps/admin-web/src/features/catalog/CatalogAdministration.tsx'),
  'utf8',
);
assert.match(
  catalogAdministration,
  /kind === 'ingredient-extras'[\s\S]*<BranchAvailability kind=\{kind\}/,
  'La disponibilidad local heredada sólo puede seguir montada en Ingredientes adicionales',
);
assert.doesNotMatch(
  catalogAdministration,
  /\{kind !== 'products' && branchAccess && branchManage && <BranchAvailability kind=\{kind\}/,
  'Comentarios del pedido no debe montar disponibilidad local heredada',
);

assert.match(screen, /aria-expanded=/, 'Categorías y comentarios deben comunicar expansión');
assert.match(screen, /mixed/, 'La selección parcial debe comunicarse como estado mixto');
assert.match(
  screen,
  /\/catalog\/order-comments\/\$\{[^}]+\.id\}\/products[\s\S]*method:\s*'PUT'/,
  'El editor individual debe reemplazar el conjunto exacto mediante el endpoint vigente',
);
assert.match(screen, /role="alert"/, 'Los errores deben conservar un anuncio accesible');
assert.match(screen, /Quitar \$\{product\.product_name\}/, 'Cada chip debe exponer un retiro accesible');
assert.match(screen, /removeProduct\.mutate/, 'La X debe persistir el conjunto restante');
assert.match(responsiveStyles, /order-comment-product-chip__remove/, 'La X debe tener estilo propio');
assert.match(responsiveStyles, /:hover[\s\S]*:focus-visible/, 'La X debe revelarse por puntero o teclado');
assert.match(responsiveStyles, /@media \(hover: none\)/, 'La X debe permanecer visible en pantallas táctiles');
for (const contract of [
  '.order-comment-workspace .ui-button',
  '.order-comment-selector',
  '.order-comment-action',
  "input[type='checkbox']",
  'border-radius: 999px',
  'height: 40px !important',
  'width: 40px !important',
  ':focus-visible',
]) {
  assert.ok(responsiveStyles.includes(contract), `La superficie debe suavizar ${contract}`);
}
assert.match(responsiveStyles, /@media \(max-width: 760px\)/, 'La pantalla debe reordenarse en ancho reducido');
assert.match(
  responsiveStyles,
  /\.order-comment-workspace__grid\s*\{[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
  'El breakpoint angosto debe presentar una sola columna',
);

console.log('test_admin_order_comment_product_scope.mjs PASSED');
