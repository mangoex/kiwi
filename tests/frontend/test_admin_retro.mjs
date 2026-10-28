import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync('apps/admin-web/src/App.tsx', 'utf8');
const layout = readFileSync('apps/admin-web/src/components/AdminLayout.tsx', 'utf8');
const login = readFileSync('apps/admin-web/src/features/auth/Login.tsx', 'utf8');
const styles = readFileSync('apps/admin-web/src/App.css', 'utf8');
const catalogs = readFileSync('apps/admin-web/src/premium-catalogs.css', 'utf8');
const modern = readFileSync('apps/admin-web/src/kiwi-modern-admin.css', 'utf8');

assert.match(app, /document\.documentElement\.dataset\.adminModern = 'true'/);
assert.doesNotMatch(app, /dataset\.adminRetro =/);
assert.match(app, /document\.documentElement\.removeAttribute\('data-admin-retro'\)/);
assert.match(layout, /className="admin-retro admin-layout"/);
assert.match(layout, /KiwiPOS/);
assert.match(layout, /<svg aria-hidden="true"/);
assert.doesNotMatch(layout, /🥝/u);
assert.match(login, /className="admin-retro admin-login"/);

assert.match(styles, /html\[data-admin-retro\] \{/);
assert.match(styles, /html\[data-admin-retro\] \.ui-modal-overlay/);
assert.match(styles, /html\[data-admin-retro\] :focus-visible/);
assert.match(styles, /@media \(max-width: 768px\)/);
assert.match(styles, /@media \(max-width: 390px\)/);
assert.match(styles, /@media \(min-width: 1440px\)/);
assert.match(styles, /overflow-x: auto/);
assert.doesNotMatch(styles, /filter:\s*grayscale/);
assert.match(catalogs, /html\[data-admin-retro\] \.premium-card/);
assert.match(modern, /html\[data-admin-modern\] \{/);
assert.match(modern, /color-scheme: light/);
assert.match(modern, /--color-surface: #ffffff/);
assert.match(modern, /--kiwi-primary: #16a34a/);
assert.match(modern, /--kiwi-ai-purple: #7c3aed/);

console.log('Admin modern semantic contract passed');
