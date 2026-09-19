import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const clientPath = 'packages/api-client/src/operationalOrders.ts';
assert.ok(existsSync(clientPath), 'Operational order transport must be isolated from fetchApi.');

const client = readFileSync(clientPath, 'utf8');
const pos = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');
const kds = readFileSync('apps/kds-web/src/features/orders/KitchenBoard.tsx', 'utf8');
const posSession = readFileSync('apps/pos-web/src/session.ts', 'utf8');
const posMain = readFileSync('apps/pos-web/src/main.tsx', 'utf8');
const kdsMain = readFileSync('apps/kds-web/src/main.tsx', 'utf8');

assert.match(client, /OFFLINE_ORDER_GRANT_KEY/);
assert.match(client, /OFFLINE_ORDER_GRANT_BRANCH_KEY/);
assert.match(client, /OFFLINE_ORDER_GRANT_DEVICE_KEY/);
assert.match(client, /OFFLINE_ORDER_GRANT_GATEWAY_KEY/);
assert.match(client, /readGatewayOperationalStatus/);
assert.match(client, /\/api\/v1\/local\/orders\/status/);
assert.match(client, /\/api\/v1\/local\/order-api/);
assert.match(client, /sessionStorage\.setItem/);
assert.match(client, /Date\.parse\(expiresAt\) <= now/);
assert.match(client, /storedBranchId !== config\.branchId/);
assert.match(client, /storedDeviceId !== config\.deviceId/);
assert.match(client, /storedGatewayUrl !== config\.gatewayUrl/);
assert.match(client, /clearOfflineOrderGrant/);
assert.match(client, /GATEWAY_UNAVAILABLE/);
assert.match(client, /PENDING_SYNC/);
assert.match(client, /CONFIRMED/);
assert.match(client, /CONFLICT/);
assert.match(client, /operationalOrderRequest/);
assert.match(client, /getOperationalOrderCommandStatus/);
assert.match(client, /\/orders\/commands\//);
assert.doesNotMatch(client, /fetchApi\(/, 'Local transport must not reuse the cloud Bearer client.');
assert.doesNotMatch(client, /Bearer \$\{/, 'Local transport must only present Offline grants.');
assert.match(client, /headers\.set\('Authorization', `Offline \$\{grant\}`\)/, 'Caller headers may not replace the offline authorization.');

assert.match(pos, /operationalOrderRequest/);
assert.match(pos, /offlineOrderStatusLabel/);
assert.match(pos, /getOperationalOrderCommandStatus/);
assert.match(pos, /pendingOfflineCommandId/);
assert.match(pos, /'Idempotency-Key':\s*checkoutIntent\.key/);
assert.match(pos, /'Idempotency-Key':\s*checkoutIntent\.paymentKey/);
assert.doesNotMatch(pos, /fetchApi[\s\S]{0,240}'\/orders'[\s\S]{0,240}operationalOrderRequest/, 'POS must select one command destination, never retry the cloud after gateway ambiguity.');

assert.match(kds, /operationalOrderRequest/);
assert.match(kds, /operationalOrderRequest<KdsSession>\(config, '\/auth\/session'\)/);
assert.match(kds, /offline_order_branch_mismatch/);
assert.match(kds, /crypto\.randomUUID\(\)/);
assert.match(kds, /Idempotency-Key/);
assert.match(kds, /offlineOrderStatusLabel/);

assert.match(posMain, /serviceWorker\.register/);
assert.match(kdsMain, /serviceWorker\.register/);
assert.doesNotMatch(posMain, /auth_token/);
assert.doesNotMatch(kdsMain, /auth_token/);
assert.match(posSession, /operationalOrderRequest<PosSession>\(operationalConfig, endpoint\)/);
assert.match(posSession, /offline_order_branch_mismatch/);

console.log('ORD-OFF-001 operational order browser boundary semantic contract passed');
