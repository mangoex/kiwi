import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

for (const [app, base] of [['pos-web', '/pos/'], ['kds-web', '/kds/']]) {
  const worker = readFileSync(`apps/${app}/public/offline-shell-sw.js`, 'utf8');
  const main = readFileSync(`apps/${app}/src/main.tsx`, 'utf8');
  assert.match(worker, new RegExp(`'${base}'`));
  assert.match(worker, new RegExp(`'${base}index\\.html'`));
  assert.match(worker, /PRECACHE_ASSETS/);
  assert.match(worker, /request\.mode === 'navigate'/);
  assert.match(worker, /await fetch\(request\)/);
  assert.match(worker, /offline_shell_unavailable/);
  assert.match(worker, /ignoreVary: true/);
  assert.match(worker, /response\.ok/);
  assert.match(worker, /request\.headers\.has\('Authorization'\)/);
  assert.match(worker, /url\.pathname\.includes\('\/api\/'\)/);
  assert.match(main, /serviceWorker\.register/);
  assert.match(main, /document\.querySelectorAll/);
  assert.match(main, /PRECACHE_ASSETS/);
}

console.log('ORD-OFF-001 offline shell semantic contract passed');
