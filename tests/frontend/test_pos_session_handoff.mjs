import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const adminApp = readFileSync('apps/admin-web/src/App.tsx', 'utf8');
const adminLogin = readFileSync('apps/admin-web/src/features/auth/Login.tsx', 'utf8');
const adminLayout = readFileSync('apps/admin-web/src/components/AdminLayout.tsx', 'utf8');
const adminHandoff = readFileSync('apps/admin-web/src/lib/posHandoff.ts', 'utf8');
const posApp = readFileSync('apps/pos-web/src/App.tsx', 'utf8');
const combined = [adminApp, adminLogin, adminLayout, adminHandoff, posApp].join('\n');

assert.doesNotMatch(combined, /[?&]token=/, 'Session tokens must never be placed in URLs');
assert.doesNotMatch(combined, /[?&]user=/, 'User profiles must never be placed in URLs');
assert.doesNotMatch(posApp, /searchParams|get\(['"]token['"]\)/, 'POS must not read tokens from query');
assert.match(posApp, /cleanSearch\.delete\('token'\)/, 'POS must remove a legacy token query parameter');
assert.match(posApp, /cleanSearch\.delete\('user'\)/, 'POS must remove a legacy user query parameter');
assert.match(posApp, /remainingSearch/, 'POS must preserve legitimate query parameters while sanitizing');
assert.match(posApp, /window\.location\.href = adminLoginUrl\(\)/, 'Handoff recovery must use the environment-aware Admin URL');
assert.match(combined, /#handoff=/, 'Admin must transport only an opaque handoff fragment');
assert.match(posApp, /history\.replaceState[\s\S]*pos-handoffs\/exchange/, 'POS must clear the fragment before exchange');

console.log('POS session handoff semantic contract passed');
