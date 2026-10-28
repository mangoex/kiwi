import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const pos = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');
const main = readFileSync('apps/pos-web/src/main.tsx', 'utf8');
const css = readFileSync('apps/pos-web/src/App.css', 'utf8');
const neutral = readFileSync('packages/ui/src/styles/neutral.css', 'utf8');
const groups = ['all', 'food', 'drinks', 'other', 'favorites'];

const luminance = (hex) => {
  const channels = [0, 2, 4]
    .map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255)
    .map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4));
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
};
const contrast = (left, right) => {
  const [lighter, darker] = [luminance(left), luminance(right)].sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
};

// The approved baseline maintains a clear light theme without monochrome/grayscale wash.
assert.match(main, /import ["']@restaurantos\/ui\/styles\/neutral\.css["']/);
assert.match(pos, /pos-sale-palette--\$\{activeMenuGroup\}/);
assert.match(pos, /pos-sale-menu-group--\$\{group\.id\}/);
assert.doesNotMatch(pos, /pos-sale-palette--\$\{activeCategory/);

assert.match(neutral, /color-scheme:\s*only light/);
assert.doesNotMatch(neutral, /filter:\s*grayscale/, 'Grayscale condition must be removed to allow full-color photos and UI assets');

// Semantic tokens are colored and distinct (not gray #303030)
assert.match(neutral, /--color-green:\s*#10b981/);
assert.match(neutral, /--color-orange:\s*#f59e0b/);
assert.match(neutral, /--color-blue:\s*#3b82f6/);
assert.match(neutral, /--color-red:\s*#ef4444/);
assert.match(neutral, /--kiwi-primary:\s*#16a34a/);

// The Mimenu branding change deliberately uses white category buttons, retaining AA contrast
// and an explicit active border. Per-group colors remain on the catalog's pastel surfaces.
for (const state of ['', ':hover', '.active']) {
  const selector = `.pos-sale-menu button${state}`.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const rule = css.match(new RegExp(`${selector}\\s*\\{([^}]+)\\}`));
  assert.ok(rule, `Falta el estado del botón ${state || 'normal'}`);
  const background = rule[1].match(/background:\s*#([0-9a-f]{6})/i);
  const foreground = rule[1].match(/(?:^|[;\n])\s*color:\s*#([0-9a-f]{6})/i);
  assert.ok(background && foreground, 'El estado debe declarar sus colores');
  assert.ok(contrast(background[1], foreground[1]) >= 4.5, 'Cada estado conserva contraste AA');
  if (state === '.active') assert.match(rule[1], /border:\s*2px solid #10b981/);
}
for (const group of groups) {
  const pastelRule = css.match(new RegExp(`\\.pos-sale-palette--${group}\\s*\\{[^}]*--catalog-pastel-surface:\\s*#([0-9a-f]{6})[^}]*--catalog-pastel-card:\\s*#[0-9a-f]{6}[^}]*--catalog-pastel-visual:\\s*#[0-9a-f]{6}[^}]*--catalog-pastel-border:\\s*#[0-9a-f]{6}[^}]*--catalog-pastel-ink:\\s*#([0-9a-f]{6})`, 'i'));
  assert.ok(pastelRule, `${group} debe tener superficie pastel explícita`);
  assert.ok(contrast(pastelRule[1], pastelRule[2]) >= 4.5, `${group} debe conservar contraste AA entre superficie pastel y texto`);
}

assert.match(css, /\.pos-sale-menu button:focus-visible\s*\{[^}]*outline:\s*3px solid/s);
assert.match(pos, /aria-pressed=\{isActive\}/);
console.log('test_pos_catalog_color_palette.mjs PASSED (clean light theme with full color assets, grayscale removed)');
