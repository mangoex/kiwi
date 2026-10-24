import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import ts from 'typescript';

const helperPath = 'apps/pos-web/src/features/pos/upsellSuggestions.ts';
const posPath = 'apps/pos-web/src/features/pos/PointOfSale.tsx';

assert.ok(existsSync(helperPath), 'POS must provide a testable suggestion-dismissal helper');

const helperSource = readFileSync(helperPath, 'utf8');
const helperJavaScript = ts.transpileModule(helperSource, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { addDismissedUpsellProduct, getVisibleUpsellRecommendations } = await import(
  `data:text/javascript;base64,${Buffer.from(helperJavaScript).toString('base64')}`
);
const recommendations = [
  { product_id: 'agua', product_name: 'Agua', price_cents: 5500, reason: 'Favorito' },
  { product_id: 'jugo', product_name: 'Jugo', price_cents: 6000, reason: 'Complemento' },
  { product_id: 'te', product_name: 'Té', price_cents: 5000, reason: 'Popular' },
];
const initialDismissed = new Set();
const dismissed = addDismissedUpsellProduct(initialDismissed, 'agua');

assert.notStrictEqual(dismissed, initialDismissed, 'dismissal must not mutate React state in place');
assert.deepEqual([...initialDismissed], [], 'the previous dismissal state must remain unchanged');
assert.deepEqual(
  getVisibleUpsellRecommendations(recommendations, dismissed, 2).map((item) => item.product_id),
  ['jugo', 'te'],
  'a dismissed recommendation must stay hidden while another available recommendation fills its place',
);

const source = readFileSync(posPath, 'utf8');
assert.match(source, /aria-label=\{`Quitar sugerencia \$\{rec\.product_name\}`\}/,
  'each recommendation must expose an accessible remove control');
assert.match(source, /onClick=\{\(\) => dismissUpsellRecommendation\(rec\.product_id\)\}/,
  'the remove control must dismiss only its recommendation');
assert.match(source, /addToCart\(product\);\s*setDismissedUpsellProductIds/,
  'adding a recommendation must also hide it');
assert.match(source, /useEffect\(\(\) => \{\s*setDismissedUpsellProductIds\(new Set\(\)\);\s*\}, \[selectedCustomer\?\.id\]\)/,
  'dismissed recommendations must reset when the customer context changes');

console.log('POS upsell suggestion dismissal contract passed');
