import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync('apps/pos-web/src/features/reports/PCO007Reports.tsx', 'utf8');
assert.match(source, /'loading' \| 'empty' \| 'data' \| 'incomplete' \| 'error'/);
assert.match(source, /localDayUtcBounds/);
assert.match(source, /timeZone/);
assert.match(source, /reports\/ingredient-sales/);
assert.match(source, /reports\/expenses/);
assert.match(source, /next_cursor/);
assert.match(source, /overflowX: 'auto'/);
assert.match(source, /padding: 12/);
assert.match(source, /fontVariantNumeric: 'tabular-nums'/);
assert.doesNotMatch(source, /JSON\.stringify\(value\)/);
assert.doesNotMatch(source, /setUTCHours/);
console.log('PCO-007 reports semantic contract passed');
