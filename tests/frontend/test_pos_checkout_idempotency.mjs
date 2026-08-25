import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');

assert.match(source, /checkoutIntentRef/, 'POS must preserve the checkout intention across uncertain retry');
assert.match(source, /'Idempotency-Key':\s*checkoutIntent\.key/, 'Order creation must send the stable key');
assert.match(source, /paymentKey/, 'POS must preserve a payment key with the checkout intention');
assert.match(source, /'Idempotency-Key':\s*checkoutIntent\.paymentKey/, 'Payment confirmation must send the stable key');
assert.match(source, /checkoutState\s*===\s*'submitting'/, 'Checkout must expose an in-flight state');
assert.match(source, /disabled=\{[^}]*checkoutState\s*===\s*'submitting'/, 'Confirm must block double submit');
assert.match(source, /sessionStorage\.setItem\([^,]+,\s*JSON\.stringify\(pendingCheckout\)\)/, 'POS must persist a PII-free pending checkout before order creation');
assert.match(source, /fetchApi<[^>]+>\('\/orders\/recover'/, 'POS must recover an accepted order after reload');
assert.match(source, /'Idempotency-Key':\s*pendingCheckout\.orderKey/, 'Recovery must use the original order key');
assert.match(source, /'Idempotency-Key':\s*pendingCheckout\.paymentKey/, 'Recovered payment must use the original payment key');
assert.doesNotMatch(source, /sessionStorage\.setItem\([^\n]+fingerprint/, 'POS must not persist the checkout payload fingerprint because it can contain PII');
assert.match(source, /const unresolvedCheckout = readPendingCheckout\(\);\s*if \(unresolvedCheckout\) \{[\s\S]*cobro pendiente de recuperación[\s\S]*return;/, 'Any pending checkout must block a changed or repeated sale until recovery finishes');
assert.doesNotMatch(source, /checkoutIntentRef\.current\?\.key\s*!==\s*unresolvedCheckout\.orderKey/, 'A matching in-memory key must not bypass pending checkout recovery');
assert.match(source, /UUID_PATTERN\.test\(candidate\.orderKey\)[\s\S]*UUID_PATTERN\.test\(candidate\.paymentKey\)/, 'Persisted technical keys must be validated before recovery');

console.log('POS checkout idempotency semantic contract passed');
