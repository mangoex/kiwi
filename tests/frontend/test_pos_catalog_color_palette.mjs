import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const pos = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');
const css = readFileSync('apps/pos-web/src/App.css', 'utf8');
const groups = ['all', 'food', 'drinks', 'other', 'favorites'];

const luminance = (hex) => {
  const channels = [0, 2, 4]
    .map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255)
    .map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
};
const contrast = (left, right) => {
  const [lighter, darker] = [luminance(left), luminance(right)].sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
};
const solidColors = [];

assert.match(pos, /pos-sale-palette--\$\{activeMenuGroup\}/,
  'La paleta central debe derivarse del ID canónico superior activo');
assert.match(pos, /pos-sale-menu-group--\$\{group\.id\}/,
  'Cada botón superior debe publicar su identidad de paleta');

for (const group of groups) {
  const solidRule = css.match(new RegExp(`\\.pos-sale-menu-group--${group}\\s*\\{[^}]*--menu-solid:\\s*#([0-9a-f]{6})`, 'i'));
  assert.ok(solidRule,
    `${group} debe tener tono sólido explícito`);
  solidColors.push(solidRule[1].toLowerCase());
  assert.ok(contrast(solidRule[1], 'ffffff') >= 4.5,
    `${group} debe conservar contraste AA con texto blanco`);
  const pastelRule = css.match(new RegExp(`\\.pos-sale-palette--${group}\\s*\\{[^}]*--catalog-pastel-surface:\\s*#([0-9a-f]{6})[^}]*--catalog-pastel-card:\\s*#[0-9a-f]{6}[^}]*--catalog-pastel-visual:\\s*#[0-9a-f]{6}[^}]*--catalog-pastel-border:\\s*#[0-9a-f]{6}[^}]*--catalog-pastel-ink:\\s*#([0-9a-f]{6})`, 'i'));
  assert.ok(pastelRule,
    `${group} debe tener superficie pastel explícita`);
  assert.ok(contrast(pastelRule[1], pastelRule[2]) >= 4.5,
    `${group} debe conservar contraste AA entre superficie pastel y texto`);
}

assert.equal(new Set(solidColors).size, groups.length,
  'Cada opción superior debe conservar un color sólido distinto');
const baseButtonRule = css.match(/\.pos-sale-menu button\s*\{([^}]*)\}/s);
assert.ok(baseButtonRule, 'Debe existir la regla base del botón superior');
assert.doesNotMatch(baseButtonRule[1], /--menu-solid:/,
  'La regla base no debe sobrescribir el color propio de cada opción');
assert.match(css, /\.pos-sale-menu button\s*\{[^}]*background: var\(--menu-solid\)[^}]*color: #fff/s,
  'Los tonos sólidos conservan texto e icono blancos');
assert.match(css, /\.pos-sale-menu button\.active\s*\{[^}]*box-shadow:/s,
  'El estado activo usa una señal adicional al color');
assert.match(css, /\.pos-sale-category-panel\s*\{[^}]*background: var\(--catalog-pastel-surface\)/s);
assert.match(css, /\.pos-sale-category-card\s*\{[^}]*background: var\(--catalog-pastel-card\)/s);
assert.match(css, /\.pos-sale-product-card\s*\{[^}]*background: var\(--catalog-pastel-card\)/s);
assert.doesNotMatch(pos, /pos-sale-palette--\$\{activeCategory/,
  'La paleta no se deriva del nombre libre de la categoría');

console.log('test_pos_catalog_color_palette.mjs PASSED');
