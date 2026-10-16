import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const history = readFileSync('apps/pos-web/src/features/history/History.tsx', 'utf8');
const styles = readFileSync('apps/pos-web/src/App.css', 'utf8');

assert.match(history, /serviceType === 'delivery'/);
assert.match(history, />Repartidor</);
assert.match(history, /driver-cash-settlements\/drivers/);
assert.match(history, /params\.set\('driver_id', driverId\)/);
assert.match(history, /settlement_eligible/);
assert.match(history, /type="checkbox"/);
assert.match(history, /Seleccionar todos los pedidos elegibles cargados/);
assert.match(history, /Recibir efectivo del repartidor/);
assert.match(history, /driver-cash-settlements/);
assert.match(history, /'Idempotency-Key'/);
assert.match(history, /selectedSettlementTotal/);
assert.match(history, /!localOrders/);
assert.match(styles, /orders-history-settlement/);
assert.match(history, /orders-history-settlement-modal/);
assert.match(styles, /orders-history-settlement-modal \{ background: #fff/);

console.log('Driver cash settlement semantic checks passed');
