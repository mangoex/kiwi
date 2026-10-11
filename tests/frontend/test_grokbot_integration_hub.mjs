import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const hub = readFileSync('apps/admin-web/src/features/integrations/IntegrationsHub.tsx', 'utf8');

assert.match(hub, /GROKBOT/);
assert.match(hub, /VITE_GROKBOT_AGENT_TOOLS_ENABLED/);
assert.match(hub, /grokBotAgentToolsEnabled && <div/);
assert.match(hub, /Administrador Kiwi/);
assert.match(hub, /Un solo asistente coordina cuatro especialistas/);
assert.match(hub, /administrator/);
assert.match(hub, /kitchen/);
assert.match(hub, /inventory/);
assert.match(hub, /purchasing/);
assert.match(hub, /integrations\/grokbot\/config/);
assert.match(hub, /rotate-secret/);
assert.match(hub, /Deshabilitado por defecto/);
assert.match(hub, /client_secret/);
assert.match(hub, /Se mostrará una sola vez/);
assert.match(hub, /expected_authorization_version/);
assert.match(hub, /window\.confirm/);
assert.match(hub, /Ya lo guardé; ocultar/);

console.log('GrokBot integration hub semantic contract passed');
