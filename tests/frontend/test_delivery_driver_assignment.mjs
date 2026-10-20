import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const history = readFileSync('apps/pos-web/src/features/history/History.tsx', 'utf8');

assert.match(history, /delivery_assignment/);
assert.match(history, /Asignación de repartidor/);
assert.match(history, /\/delivery\/drivers\/available/);
assert.match(history, /Repartidor seleccionado para aceptar/);
assert.match(history, /driver_id: selectedAssignmentDriverId/);
assert.match(history, /method: 'PUT'/);
assert.match(history, /\/delivery-assignment/);
assert.match(history, /Confirmar asignación/);
assert.match(history, /\['PENDING', 'ACCEPTED', 'SENT_TO_PRODUCTION', 'IN_PRODUCTION', 'READY'\]/);
assert.match(history, /selected\.status !== 'PENDING' \|\| selected\.is_public_intent === true/);

console.log('Delivery driver assignment semantic checks passed');
