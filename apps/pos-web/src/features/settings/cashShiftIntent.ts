export interface ShiftIntent {
  action: 'open'|'close'; key: string; resource?: string; payload: Record<string,unknown>;
}
export interface ShiftIntentScope { organization: string; actor: string; branch: string; register: string }
const keyFor = (scope: ShiftIntentScope) => `pos_cash_shift_intent_v2:${JSON.stringify(scope)}`;
const sameKeys = (value: object, keys: string[]) => Object.keys(value).sort().join('|') === keys.sort().join('|');
function validate(value: unknown, scope: ShiftIntentScope): ShiftIntent {
  if(!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Intención de caja inválida.');
  const command = value as ShiftIntent;
  if(!sameKeys(command, command.action === 'open' ? ['action','key','payload'] : ['action','key','payload','resource'])
    || typeof command.key !== 'string' || command.key.length < 1 || command.key.length > 180
    || !command.payload || typeof command.payload !== 'object' || Array.isArray(command.payload)) throw new Error('Intención de caja inválida.');
  if(command.action === 'open') {
    if(!sameKeys(command.payload,['branch_id','register_id','opening_cash_cents'])
      || command.payload.branch_id !== scope.branch || command.payload.register_id !== scope.register
      || !Number.isSafeInteger(command.payload.opening_cash_cents) || Number(command.payload.opening_cash_cents) < 0) throw new Error('Intención de caja fuera de alcance.');
  } else if(command.action !== 'close' || typeof command.resource !== 'string' || !command.resource
    || Object.keys(command.payload).length) throw new Error('Intención de caja inválida.');
  return command;
}
export function loadShiftIntent(scope: ShiftIntentScope): ShiftIntent|null {
  const raw = sessionStorage.getItem(keyFor(scope));
  return raw === null ? null : validate(JSON.parse(raw),scope);
}
export function saveShiftIntent(scope: ShiftIntentScope, command: ShiftIntent): void {
  validate(command,scope);
  const existing = loadShiftIntent(scope);
  if(existing && JSON.stringify(existing) !== JSON.stringify(command)) throw new Error('Resuelve primero la operación de caja pendiente.');
  const raw = JSON.stringify(command);
  sessionStorage.setItem(keyFor(scope),raw);
  if(sessionStorage.getItem(keyFor(scope)) !== raw) throw new Error('No se pudo conservar la solicitud.');
}
export function clearShiftIntent(scope: ShiftIntentScope, key: string): void {
  if(loadShiftIntent(scope)?.key === key) sessionStorage.removeItem(keyFor(scope));
}
