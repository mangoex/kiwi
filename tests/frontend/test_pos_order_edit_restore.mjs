import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-pos-order-edit-'));

try {
  const source = join(root, 'apps/pos-web/src/features/pos/editableOrderRestore.ts');
  execFileSync(
    join(root, 'node_modules/.bin/tsc'),
    [
      '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext',
      '--outDir', temporaryDirectory, source,
    ],
    { cwd: root, stdio: 'pipe' },
  );
  const restore = await import(
    pathToFileURL(join(temporaryDirectory, 'editableOrderRestore.js')).href
  );

  const catalogProduct = {
    id: 'catalog-product',
    name: 'Producto vigente',
    sku: '100',
    category: 'BEBIDAS',
    price_cents: 5500,
    description: '',
    station: 'drinks',
  };
  const catalog = new Map([[catalogProduct.id, catalogProduct]]);

  assert.equal(
    restore.resolveEditableLineProduct(
      {
        product_id: catalogProduct.id,
        product_name: 'Nombre histórico',
        unit_price_cents: 5000,
        station: 'kitchen',
      },
      catalog,
    ),
    catalogProduct,
  );

  assert.deepEqual(
    restore.resolveEditableLineProduct(
      {
        product_id: 'historical-baguette',
        product_name: 'Baguette',
        unit_price_cents: 2600,
        station: 'kitchen',
      },
      catalog,
    ),
    {
      id: 'historical-baguette',
      name: 'Baguette',
      sku: '',
      category: 'Pedido actual',
      price_cents: 2600,
      description: '',
      station: 'kitchen',
    },
  );
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
