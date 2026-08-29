import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync('apps/pos-web/src/features/pos/PointOfSale.tsx', 'utf8');

assert.match(source, /aria-label="Abrir Pedido asistido"/, 'POS must expose the accessible assisted capture control');
assert.match(source, /assistedOrderDraft/, 'POS must use the current deterministic draft contract');
assert.match(source, /<Modal isOpen=\{assistedCaptureOpen\}/, 'POS must show the shared keyboard-accessible review modal');
assert.match(source, /SpeechRecognition|webkitSpeechRecognition/, 'voice capture must be progressive enhancement only');
assert.match(source, /SpeechRecognition/, 'browser-mediated dictation must remain capability based without a build flag');
assert.doesNotMatch(source, /VITE_POS_ASSISTED_DICTATION_ENABLED/);
assert.match(source, /assistedRecognitionRef\.current !== recognition/, 'stale recognition callbacks must be ignored');
assert.match(source, /\/orders\/assisted-draft/, 'preview must request the current canonical draft');
assert.match(source, /isAssistedDraftComplete/, 'only a complete canonical draft may apply');
assert.match(source, /selected_options/, 'canonical selected options must feed the editable cart');
assert.match(source, /addToCart\(product, modifiers, comments, \[\], line\.quantity\)/, 'resolved comments, modifiers and quantity must reach the editable cart');
assert.match(source, /setSelectedCustomer\(null\)/, 'a new assisted phone must clear stale customer identity before exact lookup');
assert.match(source, /setCart\(/, 'only the existing editable cart state may receive resolved lines');
assert.doesNotMatch(source, /assisted[\s\S]{0,200}fetchApi\([^)]*['"]\/(?:orders|payments)/i, 'assisted capture must not create orders or payments');
assert.doesNotMatch(source, /localStorage\.setItem\([^\n]*(?:assisted|draft|phone|ownerName)/i, 'assisted PII must not persist locally');
assert.doesNotMatch(source, /sessionStorage\.setItem\([^\n]*(?:assisted|draft|phone|ownerName)/i, 'assisted PII must not persist in session storage');

console.log('POS assisted order capture semantic contract passed');
