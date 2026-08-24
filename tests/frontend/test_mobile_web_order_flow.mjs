import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { cpSync, mkdtempSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const require = createRequire(import.meta.url);
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const temporaryDirectory = mkdtempSync(join(tmpdir(), 'restaurantos-mobile-web-'));

let buildWhatsAppLink;

try {
  const source = join(root, 'apps/mobile-web/src/api.ts');
  const envDts = join(root, 'apps/mobile-web/src/vite-env.d.ts');
  execFileSync(
    process.execPath,
    [
      join(root, 'node_modules/typescript/bin/tsc'),
      '--target', 'ES2022',
      '--module', 'CommonJS',
      '--skipLibCheck',
      '--outDir', temporaryDirectory,
      envDts,
      source,
    ],
    { cwd: root, stdio: 'pipe' },
  );
  cpSync(join(root, 'apps/mobile-web/src/assets'), join(temporaryDirectory, 'assets'), { recursive: true, force: true });
  require.extensions['.jpg'] = (module, filename) => { module.exports = filename; };
  require.extensions['.png'] = (module, filename) => { module.exports = filename; };
  const mobileApi = require(join(temporaryDirectory, 'api.js'));
  buildWhatsAppLink = mobileApi.buildWhatsAppLink;
} catch (err) {
  rmSync(temporaryDirectory, { recursive: true, force: true });
  throw err;
}

process.on('exit', () => {
  rmSync(temporaryDirectory, { recursive: true, force: true });
});

test('Mobile Order WhatsApp link format for takeaway', () => {
  const info = {
    name: 'Carlos Ruiz',
    phone: '5511223344',
    order_type: 'takeaway',
    address_street: '',
    address_number: '',
    address_neighborhood: '',
    address_notes: '',
    payment_method: 'cash',
    cash_amount: '200',
    order_notes: 'Sin cubiertos',
  };

  const items = [
    {
      cart_id: 'item-1',
      product: { id: 'prod-1', name: 'Jugo Verde', price_cents: 6500 },
      quantity: 2,
      notes: 'Sin popote',
      line_total_cents: 13000,
    },
  ];

  const total = 13000;
  const link = buildWhatsAppLink('KIWI-5001', info, items, total);

  assert.ok(link.startsWith('https://wa.me/5215500000000?text='));
  const decoded = decodeURIComponent(link.replace('https://wa.me/5215500000000?text=', ''));

  assert.match(decoded, /#KIWI-5001/);
  assert.match(decoded, /Carlos Ruiz/);
  assert.match(decoded, /Para Recoger en Sucursal/);
  assert.match(decoded, /2x Jugo Verde/);
  assert.match(decoded, /\$130\.00 MXN/);
  assert.match(decoded, /Sin popote/);
  assert.match(decoded, /Paga con: \$200/);
});

test('Mobile Order WhatsApp link format for delivery with address', () => {
  const info = {
    name: 'Mariana Lopez',
    phone: '5599887766',
    order_type: 'delivery',
    address_street: 'Calle Roble',
    address_number: '450 Int 2',
    address_neighborhood: 'Col. Roma',
    address_notes: 'Edificio gris',
    payment_method: 'card',
    order_notes: '',
  };

  const items = [
    {
      cart_id: 'item-2',
      product: { id: 'prod-2', name: 'Sando Kyoto Pollo BBQ', price_cents: 12000 },
      quantity: 1,
      notes: '',
      line_total_cents: 12000,
    },
    {
      cart_id: 'item-3',
      product: { id: 'prod-3', name: 'Smoothie Rosa', price_cents: 9000 },
      quantity: 1,
      notes: '',
      line_total_cents: 9000,
    },
  ];

  const total = 21000;
  const link = buildWhatsAppLink('KIWI-8822', info, items, total);
  const decoded = decodeURIComponent(link.replace('https://wa.me/5215500000000?text=', ''));

  assert.match(decoded, /#KIWI-8822/);
  assert.match(decoded, /Mariana Lopez/);
  assert.match(decoded, /Envío a Domicilio/);
  assert.match(decoded, /Calle Roble #450 Int 2, Col\. Roma/);
  assert.match(decoded, /Tarjeta \(Al recibir\)/);
  assert.match(decoded, /\$210\.00 MXN/);
});
