/** Durable corporate intent; no credentials or inferred quantities are stored. */
export interface CorporateAuthority { organization_id: string; actor_id: string; }
export interface CorporateIntent {
  version: 1;
  authority: CorporateAuthority;
  endpoint: string;
  key: string;
  body: string;
}
export const corporateIntentKey = (authority: CorporateAuthority): string =>
  `corporate-intent:v1:${authority.organization_id}:${authority.actor_id}`;

const microQuantity = (value: string): bigint | null => {
  if (!/^\d{1,12}(?:\.\d{1,6})?$/.test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  return BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, '0'));
};

export function explicitReceiptQuantity(value: string | undefined, pending: string): string {
  const entered = value?.trim() || '';
  const quantity = microQuantity(entered);
  const remaining = microQuantity(pending);
  if (quantity === null || quantity <= 0n || remaining === null || quantity > remaining) {
    throw new Error('Captura una cantidad positiva que no supere el pendiente, con hasta seis decimales.');
  }
  return entered;
}

export function pendingBaseQuantity(ordered: string, received: string): string {
  const total = microQuantity(ordered);
  const done = microQuantity(received);
  if (total === null || done === null || done > total) return 'Dato inválido';
  const pending = total - done;
  return `${pending / 1000000n}.${String(pending % 1000000n).padStart(6, '0')}`;
}

export function readCorporateIntent(storage: Pick<Storage, 'getItem'>,
  authority: CorporateAuthority): CorporateIntent | null {
  const raw = storage.getItem(corporateIntentKey(authority));
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== 'object') throw new Error();
    const intent = value as CorporateIntent;
    if (Object.keys(intent).sort().join() !== 'authority,body,endpoint,key,version'
      || intent.version !== 1 || !intent.authority
      || Object.keys(intent.authority).sort().join() !== 'actor_id,organization_id'
      || intent.authority.organization_id !== authority.organization_id
      || intent.authority.actor_id !== authority.actor_id
      || !authority.organization_id || !authority.actor_id
      || typeof intent.key !== 'string' || !intent.key || intent.key.length > 180
      || typeof intent.body !== 'string' || new TextEncoder().encode(intent.body).length > 262144
      || typeof intent.endpoint !== 'string'
      || !/^\/corporate-purchases(?:\/[\w-]+\/(?:approve|cancel|receipts))?$/.test(intent.endpoint)) {
      throw new Error();
    }
    const payload: unknown = JSON.parse(intent.body);
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error();
    return intent;
  } catch {
    throw new Error('El intento pendiente no se pudo validar. Revisa su resultado antes de operar otra vez.');
  }
}

export function createCorporateIntent(storage: Pick<Storage, 'getItem' | 'setItem'>,
  authority: CorporateAuthority, endpoint: string, body: string, key: string): CorporateIntent {
  if (readCorporateIntent(storage, authority)) {
    throw new Error('Recupera la operación pendiente antes de iniciar otra.');
  }
  const intent: CorporateIntent = { version: 1, authority: { ...authority }, endpoint, body, key };
  // Validate through the same reader before touching persistent storage.
  readCorporateIntent({ getItem: () => JSON.stringify(intent) }, authority);
  storage.setItem(corporateIntentKey(authority), JSON.stringify(intent));
  return intent;
}

export function definitiveCorporateRejection(status: number, code: string): boolean {
  return [400, 409, 422].includes(status)
    && code !== 'corporate_purchase_idempotency_conflict';
}
