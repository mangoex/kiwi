import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(
  new URL('../../apps/admin-web/src/features/dashboard/ExecutiveCopilot.tsx', import.meta.url),
  'utf8',
);

assert.match(source, /import '\.\/ExecutiveCopilot\.css';/);
assert.match(source, /className="executive-copilot"/);
assert.match(source, /aria-labelledby="executive-copilot-title"/);
assert.match(source, /className="executive-copilot__scope"/);
assert.match(source, /aria-label="Consulta para el Copiloto Ejecutivo"/);
assert.match(source, /aria-live="polite"/);
assert.match(source, /className="executive-copilot__empty"/);
assert.match(source, /className="executive-copilot__suggested-actions"/);
assert.doesNotMatch(source, /background: 'linear-gradient\(135deg, #0f172a/);

const styles = readFileSync(
  new URL('../../apps/admin-web/src/features/dashboard/ExecutiveCopilot.css', import.meta.url),
  'utf8',
);

assert.match(styles, /\.executive-copilot__quick-action:focus-visible/);
assert.match(styles, /@media \(max-width: 720px\)/);
assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
assert.match(styles, /min-height: 44px/);
