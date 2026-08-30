import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const layout = readFileSync('apps/admin-web/src/components/AdminLayout.tsx', 'utf8');
const assistant = readFileSync('apps/admin-web/src/features/admin-ai/AdminAssistantPanel.tsx', 'utf8');
const review = readFileSync('apps/admin-web/src/features/admin-ai/AdminProposalReview.tsx', 'utf8');

assert.match(layout, /UserRound/);
assert.match(layout, /aria-label="Abrir asistente de configuración"/);
assert.match(layout, /hasCatalogManage &&/);
assert.match(layout, /admin_ai_proposal/);
assert.match(assistant, /Revisar configuración/);
assert.match(assistant, /nunca aplica cambios por sí solo/);
assert.match(review, /Configuración actual/);
assert.match(review, /Configuración propuesta/);
assert.match(review, /Aceptar configuración/);
assert.match(review, /Idempotency-Key/);

console.log('admin AI semantic contract passed');
