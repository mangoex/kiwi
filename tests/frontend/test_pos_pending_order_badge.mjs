import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const layout = readFileSync(resolve(root, 'apps/pos-web/src/components/PosLayout.tsx'), 'utf8');
const history = readFileSync(resolve(root, 'apps/pos-web/src/features/history/History.tsx'), 'utf8');
const styles = readFileSync(resolve(root, 'apps/pos-web/src/App.css'), 'utf8');

assert.ok(layout.includes("/orders/pending-count?branch_id=${encodeURIComponent(branchId)}"));
assert.ok(layout.includes('PENDING_ORDER_REFRESH_MS = 15_000'));
assert.ok(layout.includes("window.addEventListener('focus', refreshOnFocus)"));
assert.ok(layout.includes("window.addEventListener('pos:pending-orders-changed', refreshOnOrderChange)"));
assert.ok(layout.includes('pendingOrderCount > 0'));
assert.ok(layout.includes('pedidos por aceptar'));
assert.ok(history.includes("window.dispatchEvent(new Event('pos:pending-orders-changed'))"));
assert.ok(styles.includes('.pos-nav-pending-badge'));
assert.ok(styles.includes('.pos-nav-icon-wrap'));

console.log('POS pending-order badge semantic contract passed.');
