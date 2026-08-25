import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const helper = readFileSync('apps/pos-web/src/features/cash/offlineCash.ts', 'utf8');
const movements = readFileSync('apps/pos-web/src/features/cash/CashMovements.tsx', 'utf8');

assert.match(helper, /'PENDING_SYNC'[\s\S]*'CONFIRMED'[\s\S]*'CONFLICT'/);
assert.match(helper, /\['http:', 'https:'\]\.includes\(url\.protocol\)/);
assert.match(helper, /\['localhost', '127\.0\.0\.1'\]\.includes\(url\.hostname\)/);
assert.doesNotMatch(helper, /url\.protocol === 'https:'/);
assert.doesNotMatch(helper, /expected_cash|amount_cents\s*[+\-*/]/);
assert.match(helper, /GRANT_BRANCH_KEY/);
assert.match(helper, /GRANT_DEVICE_KEY/);
assert.match(helper, /GRANT_GATEWAY_KEY/);
assert.match(helper, /storedBranchId !== branchId/);
assert.match(helper, /storedDeviceId !== sourceDeviceId/);
assert.match(helper, /storedGatewayUrl !== gatewayUrl/);
assert.match(movements, /enqueueOfflineCashMovement/);
assert.match(movements, /offlineCashStatusLabel/);
assert.match(movements, /loadUsableOfflineCashGrant\(branchId, gatewayDeviceId, gatewayUrl\)/);
assert.match(movements, /storeOfflineCashGrant/);
assert.doesNotMatch(movements, /existing => existing \?\? current/);
assert.match(movements, /item\.status/);
assert.doesNotMatch(movements, /submitCompensation[\s\S]{0,300}enqueueOfflineCashMovement/);

console.log('PCO-008 offline cash semantic contract passed');
