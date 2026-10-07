import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const pos = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');
const main = readFileSync('apps/pos-web/src/main.tsx', 'utf8');
const neutral = readFileSync('packages/ui/src/styles/neutral.css', 'utf8');

// The approved neutral baseline replaces the former distinct solid/pastel acceptance criterion.
assert.match(main, /import ["']@restaurantos\/ui\/styles\/neutral\.css["']/);
assert.match(pos, /pos-sale-palette--\$\{activeMenuGroup\}/);
assert.match(pos, /pos-sale-menu-group--\$\{group\.id\}/);
assert.doesNotMatch(pos, /pos-sale-palette--\$\{activeCategory/);
assert.match(neutral, /color-scheme:\s*only light/);
assert.match(neutral, /filter:\s*grayscale\(1\)/);

const center = neutral.match(/\.pos-sale-screen\s*\{([^}]*)\}/s);
assert.ok(center, 'All catalog group identities receive the neutral baseline');
for (const token of ['surface', 'card', 'visual', 'border', 'ink', 'accent']) {
  const value = center[1].match(new RegExp(`--catalog-pastel-${token}:\\s*#([0-9a-f]{3}|[0-9a-f]{6})\\s*;`, 'i'));
  assert.ok(value, `${token} must have an explicit neutral tone`);
  const channels = value[1].length === 3 ? [...value[1]] : value[1].match(/../g);
  assert.equal(new Set(channels).size, 1, `${token} must have equal RGB channels`);
}
const menu = neutral.match(/\.pos-sale-menu button\s*\{([^}]*)\}/s);
assert.ok(menu);
assert.match(menu[1], /background:\s*#fff/);
assert.match(menu[1], /color:\s*#303030/);
assert.match(neutral, /\.pos-sale-menu button:hover\s*\{[^}]*background:\s*#f5f5f5[^}]*color:\s*#202020/s,
  'Hover retains dark readable text on its clear surface');
assert.match(neutral, /\.pos-sale-menu button\.active\s*\{[^}]*border-color:\s*#303030[^}]*box-shadow:/s,
  'Selection remains explicit through border and inset line');
assert.match(pos, /aria-pressed=\{isActive\}/);
console.log('test_pos_catalog_color_palette.mjs PASSED (approved neutral baseline)');
