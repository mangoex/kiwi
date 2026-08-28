import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');

assert.match(source, /Captura asistida/, 'POS must expose the accessible assisted capture control');
assert.match(source, /assistedOrderInterpreter/, 'POS must use the local deterministic interpreter');
assert.match(source, /<Modal isOpen=\{assistedCaptureOpen\}/, 'POS must show the shared keyboard-accessible review modal');
assert.match(source, /SpeechRecognition|webkitSpeechRecognition/, 'voice capture must be progressive enhancement only');
assert.match(source, /VITE_POS_ASSISTED_DICTATION_ENABLED === 'true'/, 'browser-mediated dictation must remain disabled unless explicitly configured');
assert.match(source, /\/products\/\$\{productId\}\/modifiers/, 'preview must resolve instructions against effective product modifiers');
assert.match(source, /addToCart\(product, modifiers, comments, \[\], line\.quantity\)/, 'resolved comments, modifiers and quantity must reach the editable cart');
assert.match(source, /setSelectedCustomer\(null\)/, 'a new assisted phone must clear stale customer identity before exact lookup');
assert.match(source, /setCart\(/, 'only the existing editable cart state may receive resolved lines');
assert.doesNotMatch(source, /assisted[\s\S]{0,200}fetchApi\([^)]*['"]\/(?:orders|payments)/i, 'assisted capture must not create orders or payments');
assert.doesNotMatch(source, /localStorage\.setItem\([^\n]*(?:assisted|draft|phone|ownerName)/i, 'assisted PII must not persist locally');
assert.doesNotMatch(source, /sessionStorage\.setItem\([^\n]*(?:assisted|draft|phone|ownerName)/i, 'assisted PII must not persist in session storage');

console.log('POS assisted order capture semantic contract passed');
