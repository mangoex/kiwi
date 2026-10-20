import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, symlinkSync, writeFileSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, resolve } from 'node:path';
import test from 'node:test';

const root = process.cwd();
// Stay inside the repository so compiled React resolves the workspace dependencies.
mkdirSync(join(root, 'output'), { recursive: true });
const scratch = mkdtempSync(join(root, 'output', 'mobile-profile-test-'));
const require = createRequire(join(root, 'apps/mobile-web/package.json'));
symlinkSync(join(root, 'apps/mobile-web/node_modules'), join(scratch, 'node_modules'), 'junction');
let profileModule, navigation, client;
try {
  execFileSync(process.execPath, [join(root, 'node_modules/typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'CommonJS', '--jsx', 'react-jsx',
    '--esModuleInterop', '--skipLibCheck', '--outDir', scratch,
    'apps/mobile-web/src/components/CustomerProfile.tsx',
    'apps/mobile-web/src/components/BottomNav.tsx'], { cwd: root, stdio: 'pipe' });
  writeFileSync(join(scratch, 'package.json'), '{"type":"commonjs"}');
  writeFileSync(join(scratch, 'components/CustomerProfile.css'), '');
  require.extensions['.css'] = () => {};
  profileModule = require(join(scratch, 'components/CustomerProfile.js'));
  navigation = require(join(scratch, 'components/BottomNav.js'));
  client = require(join(scratch, 'customerProfile.js'));
} catch (error) { cleanup(); throw error; }
function cleanup() {
  assert.ok(resolve(scratch).startsWith(resolve(root, 'output') + '\\') || resolve(scratch).startsWith(resolve(root, 'output') + '/'));
  rmSync(scratch, { recursive: true, force: true });
}
process.on('exit', cleanup);
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const profile = { id: 'customer-a', name: 'Ana', phone: '+526691234567', email: null,
  birthday_day: 29, birthday_month: 2, birthday_year: null, addresses: [], complete: true };

test('Registration precedes menu and requires a telephone code without exposing CRM data', () => {
  const html = renderToStaticMarkup(React.createElement(profileModule.CustomerAccess, {
    publicKey: 'key', profile: null, onSaved() {},
  }));
  assert.match(html, /Recibir código/);
  assert.match(html, /autoComplete="tel-national"/);
  assert.doesNotMatch(html, /value="Ana"|customer-a["<>]/);
});

test('Profile renders partial birthday, optional year, delivery email and address controls', () => {
  const html = renderToStaticMarkup(React.createElement(profileModule.ProfileEditor, {
    publicKey: 'key', profile, onSaved() {},
  }));
  assert.match(html, /Año \(opcional\)/);
  assert.match(html, /value="29"/);
  assert.match(html, /obligatorio para delivery/);
  assert.match(html, /Completar domicilio de entrega/);
  assert.match(html, /Teléfono verificado/);
});

test('Mobile bottom navigation exposes profile', () => {
  const html = renderToStaticMarkup(React.createElement(navigation.BottomNav, {
    currentTab: 'profile', cartCount: 0, favoritesCount: 0, onSelectTab() {},
  }));
  assert.match(html, /Mi perfil/);
});

test('Self-service client uses same-origin cookie, no-store and CSRF header', async () => {
  let sent;
  globalThis.fetch = async (url, options) => {
    sent = { url, ...options }; return { ok: true, json: async () => profile };
  };
  assert.equal((await client.customerRequest('key', 'profile', { name: 'Ana' }, 'PUT')).name, 'Ana');
  assert.equal(sent.credentials, 'same-origin');
  assert.equal(sent.cache, 'no-store');
  assert.equal(sent.headers['X-Mobile-Request'], '1');
  assert.equal(sent.url, '/api/v1/mobile/branches/key/profile');
});

test('HTTP failures remain failures and explain identity collisions without exposing candidates', async () => {
  globalThis.fetch = async () => ({ ok: false, status: 409, json: async () => ({ detail: { code: 'mobile_customer_ambiguous' } }) });
  await assert.rejects(client.customerRequest('key', 'access/verify', {}), error => {
    assert.match(client.accessErrorMessage(error), /revisión/); return error.status === 409;
  });
});
