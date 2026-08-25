import { fetchApi } from '@restaurantos/api-client';

export type OfflineCashStatus =
  | 'PENDING_SYNC'
  | 'CONFIRMED'
  | 'CONFLICT'
  | 'GATEWAY_UNAVAILABLE';

export type OfflineCashMovementItem = {
  id: number;
  command_id: string;
  idempotency_key: string;
  status: Exclude<OfflineCashStatus, 'GATEWAY_UNAVAILABLE'>;
  occurred_at: string;
  accepted_at: string;
  created_at: string;
  attempts: number;
  confirmed_checkpoint: number | null;
  confirmed_at: string | null;
  conflict_code: string | null;
};

export type OfflineGrantResponse = { offline_grant: string; expires_at: string };

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const GRANT_KEY = 'pos_offline_cash_grant';
const GRANT_EXPIRY_KEY = 'pos_offline_cash_grant_expires_at';
const GRANT_BRANCH_KEY = 'pos_offline_cash_grant_branch_id';
const GRANT_DEVICE_KEY = 'pos_offline_cash_grant_source_device_id';
const GRANT_GATEWAY_KEY = 'pos_offline_cash_grant_gateway_url';

export function offlineCashStatusLabel(status: OfflineCashStatus): string {
  switch (status) {
    case 'PENDING_SYNC': return 'Pendiente de sincronización';
    case 'CONFIRMED': return 'Confirmado';
    case 'CONFLICT': return 'Conflicto';
    case 'GATEWAY_UNAVAILABLE': return 'Gateway no disponible';
  }
}

export function configuredGatewayUrl(): string | null {
  const value = localStorage.getItem('pos_gateway_url')?.trim();
  if (!value) return null;
  try {
    const url = new URL(value);
    const safe = ['http:', 'https:'].includes(url.protocol)
      && ['localhost', '127.0.0.1'].includes(url.hostname);
    if (!safe || url.username || url.password || url.search || url.hash) return null;
    return url.toString().replace(/\/$/, '');
  } catch {
    return null;
  }
}

export function configuredGatewayDeviceId(): string | null {
  const value = localStorage.getItem('pos_gateway_device_id')?.trim() || '';
  return UUID_PATTERN.test(value) ? value : null;
}

export function loadUsableOfflineCashGrant(
  branchId: string,
  sourceDeviceId: string,
  gatewayUrl: string,
  now = Date.now(),
): string | null {
  try {
    const grant = sessionStorage.getItem(GRANT_KEY);
    const expiresAt = sessionStorage.getItem(GRANT_EXPIRY_KEY);
    const storedBranchId = sessionStorage.getItem(GRANT_BRANCH_KEY);
    const storedDeviceId = sessionStorage.getItem(GRANT_DEVICE_KEY);
    const storedGatewayUrl = sessionStorage.getItem(GRANT_GATEWAY_KEY);
    if (
      !grant
      || !expiresAt
      || Number.isNaN(Date.parse(expiresAt))
      || storedBranchId !== branchId
      || storedDeviceId !== sourceDeviceId
      || storedGatewayUrl !== gatewayUrl
    ) {
      clearOfflineCashGrant();
      return null;
    }
    // Renew before the last minute instead of accepting at the edge of expiration.
    if (Date.parse(expiresAt) - 60_000 <= now) {
      clearOfflineCashGrant();
      return null;
    }
    return grant;
  } catch {
    clearOfflineCashGrant();
    return null;
  }
}

export function clearOfflineCashGrant(): void {
  try {
    sessionStorage.removeItem(GRANT_KEY);
    sessionStorage.removeItem(GRANT_EXPIRY_KEY);
    sessionStorage.removeItem(GRANT_BRANCH_KEY);
    sessionStorage.removeItem(GRANT_DEVICE_KEY);
    sessionStorage.removeItem(GRANT_GATEWAY_KEY);
  } catch {
    // Storage failure must not keep a stale in-memory authorization alive.
  }
}

export async function refreshOfflineCashGrant(
  branchId: string,
  sourceDeviceId: string,
): Promise<OfflineGrantResponse> {
  const response = await fetchApi<OfflineGrantResponse>('/auth/offline-grants', {
    method: 'POST',
    body: JSON.stringify({ branch_id: branchId, source_device_id: sourceDeviceId }),
  });
  if (
    typeof response.offline_grant !== 'string'
    || response.offline_grant.length < 20
    || Number.isNaN(Date.parse(response.expires_at))
  ) {
    throw new Error('offline_grant_invalid_response');
  }
  return response;
}

export function storeOfflineCashGrant(
  response: OfflineGrantResponse,
  branchId: string,
  sourceDeviceId: string,
  gatewayUrl: string,
): string {
  try {
    sessionStorage.setItem(GRANT_KEY, response.offline_grant);
    sessionStorage.setItem(GRANT_EXPIRY_KEY, response.expires_at);
    sessionStorage.setItem(GRANT_BRANCH_KEY, branchId);
    sessionStorage.setItem(GRANT_DEVICE_KEY, sourceDeviceId);
    sessionStorage.setItem(GRANT_GATEWAY_KEY, gatewayUrl);
    return response.offline_grant;
  } catch (error) {
    clearOfflineCashGrant();
    throw error;
  }
}

export async function enqueueOfflineCashMovement(
  gatewayUrl: string,
  grant: string,
  idempotencyKey: string,
  payload: Record<string, unknown>,
): Promise<OfflineCashMovementItem> {
  const response = await fetch(`${gatewayUrl}/api/v1/local/cash/movements`, {
    method: 'POST',
    headers: {
      Authorization: `Offline ${grant}`,
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error('gateway_rejected');
  const item = await response.json() as unknown;
  if (!validOfflineItem(item)) throw new Error('gateway_invalid_response');
  return item;
}

export async function listOfflineCashMovements(
  gatewayUrl: string,
  grant: string,
): Promise<OfflineCashMovementItem[]> {
  const response = await fetch(`${gatewayUrl}/api/v1/local/cash/movements`, {
    headers: { Authorization: `Offline ${grant}` },
  });
  if (!response.ok) throw new Error('gateway_unavailable');
  const body = await response.json() as { items?: unknown };
  if (!Array.isArray(body.items) || !body.items.every(validOfflineItem)) {
    throw new Error('gateway_invalid_response');
  }
  return body.items;
}

function validOfflineItem(value: unknown): value is OfflineCashMovementItem {
  if (!value || typeof value !== 'object') return false;
  const item = value as Partial<OfflineCashMovementItem>;
  return (
    typeof item.command_id === 'string'
    && UUID_PATTERN.test(item.command_id)
    && typeof item.idempotency_key === 'string'
    && item.idempotency_key.length >= 12
    && ['PENDING_SYNC', 'CONFIRMED', 'CONFLICT'].includes(String(item.status))
    && Number.isInteger(item.attempts)
  );
}
