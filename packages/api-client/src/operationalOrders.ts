export type OfflineOrderStatus = 'PENDING_SYNC' | 'CONFIRMED' | 'CONFLICT' | 'GATEWAY_UNAVAILABLE';

export type OperationalOrderConfig = {
  branchId: string;
  deviceId: string;
  gatewayUrl: string;
};

export type OperationalOrderGrant = {
  grant: string;
  expires_at: string;
};

export class OperationalOrderError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'OperationalOrderError';
  }
}

const OFFLINE_ORDER_ENABLED_KEY = 'pos_operational_orders_enabled';
const OFFLINE_ORDER_BRANCH_KEY = 'pos_operational_orders_branch_id';
const OFFLINE_ORDER_DEVICE_KEY = 'pos_operational_orders_device_id';
const OFFLINE_ORDER_GATEWAY_KEY = 'pos_operational_orders_gateway_url';
const OFFLINE_ORDER_GRANT_KEY = 'pos_offline_order_grant_v3';
const OFFLINE_ORDER_GRANT_EXPIRY_KEY = 'pos_offline_order_grant_v3_expires_at';
const OFFLINE_ORDER_GRANT_BRANCH_KEY = 'pos_offline_order_grant_v3_branch_id';
const OFFLINE_ORDER_GRANT_DEVICE_KEY = 'pos_offline_order_grant_v3_device_id';
const OFFLINE_ORDER_GRANT_GATEWAY_KEY = 'pos_offline_order_grant_v3_gateway_url';
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function offlineOrderStatusLabel(status: OfflineOrderStatus): string {
  switch (status) {
    case 'PENDING_SYNC': return 'Pendiente de sincronización';
    case 'CONFIRMED': return 'Confirmado';
    case 'CONFLICT': return 'Conflicto';
    case 'GATEWAY_UNAVAILABLE': return 'Gateway no disponible';
  }
}

function normalizedGatewayUrl(value: string): string | null {
  try {
    const url = new URL(value.trim());
    const safe = url.protocol === 'https:'
      || (url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname));
    if (!safe || url.username || url.password || url.search || url.hash) return null;
    return url.toString().replace(/\/$/, '');
  } catch {
    return null;
  }
}

export function loadOperationalOrderConfig(): OperationalOrderConfig | null {
  try {
    if (localStorage.getItem(OFFLINE_ORDER_ENABLED_KEY) !== 'true') return null;
    const branchId = localStorage.getItem(OFFLINE_ORDER_BRANCH_KEY)?.trim() || '';
    const deviceId = localStorage.getItem(OFFLINE_ORDER_DEVICE_KEY)?.trim() || '';
    const gatewayUrl = normalizedGatewayUrl(localStorage.getItem(OFFLINE_ORDER_GATEWAY_KEY) || '');
    if (!branchId || !UUID_PATTERN.test(deviceId) || !gatewayUrl) {
      throw new Error('operational_order_config_invalid');
    }
    return { branchId, deviceId, gatewayUrl };
  } catch (error) {
    if (error instanceof Error && error.message === 'operational_order_config_invalid') throw error;
    throw new Error('operational_order_config_unavailable');
  }
}

export function storeOperationalOrderConfig(config: OperationalOrderConfig): void {
  const gatewayUrl = normalizedGatewayUrl(config.gatewayUrl);
  if (!config.branchId.trim() || !UUID_PATTERN.test(config.deviceId) || !gatewayUrl) {
    throw new Error('operational_order_config_invalid');
  }
  let prior: OperationalOrderConfig | null = null;
  try { prior = loadOperationalOrderConfig(); } catch { clearOfflineOrderGrant(); }
  if (!prior || prior.branchId !== config.branchId || prior.deviceId !== config.deviceId || prior.gatewayUrl !== gatewayUrl) {
    clearOfflineOrderGrant();
  }
  localStorage.setItem(OFFLINE_ORDER_ENABLED_KEY, 'true');
  localStorage.setItem(OFFLINE_ORDER_BRANCH_KEY, config.branchId);
  localStorage.setItem(OFFLINE_ORDER_DEVICE_KEY, config.deviceId);
  localStorage.setItem(OFFLINE_ORDER_GATEWAY_KEY, gatewayUrl);
}

export function disableOperationalOrderMode(): void {
  try {
    localStorage.removeItem(OFFLINE_ORDER_ENABLED_KEY);
    localStorage.removeItem(OFFLINE_ORDER_BRANCH_KEY);
    localStorage.removeItem(OFFLINE_ORDER_DEVICE_KEY);
    localStorage.removeItem(OFFLINE_ORDER_GATEWAY_KEY);
  } finally {
    clearOfflineOrderGrant();
  }
}

export function clearOfflineOrderGrant(): void {
  try {
    sessionStorage.removeItem(OFFLINE_ORDER_GRANT_KEY);
    sessionStorage.removeItem(OFFLINE_ORDER_GRANT_EXPIRY_KEY);
    sessionStorage.removeItem(OFFLINE_ORDER_GRANT_BRANCH_KEY);
    sessionStorage.removeItem(OFFLINE_ORDER_GRANT_DEVICE_KEY);
    sessionStorage.removeItem(OFFLINE_ORDER_GRANT_GATEWAY_KEY);
  } catch {
    // Storage errors must not retain an authorization in memory.
  }
}

export function loadUsableOfflineOrderGrant(config: OperationalOrderConfig, now = Date.now()): string | null {
  try {
    const grant = sessionStorage.getItem(OFFLINE_ORDER_GRANT_KEY);
    const expiresAt = sessionStorage.getItem(OFFLINE_ORDER_GRANT_EXPIRY_KEY);
    const storedBranchId = sessionStorage.getItem(OFFLINE_ORDER_GRANT_BRANCH_KEY);
    const storedDeviceId = sessionStorage.getItem(OFFLINE_ORDER_GRANT_DEVICE_KEY);
    const storedGatewayUrl = sessionStorage.getItem(OFFLINE_ORDER_GRANT_GATEWAY_KEY);
    if (!grant || !expiresAt || Number.isNaN(Date.parse(expiresAt))
      || storedBranchId !== config.branchId
      || storedDeviceId !== config.deviceId
      || storedGatewayUrl !== config.gatewayUrl) {
      clearOfflineOrderGrant();
      return null;
    }
    if (Date.parse(expiresAt) <= now) {
      clearOfflineOrderGrant();
      return null;
    }
    return grant;
  } catch {
    clearOfflineOrderGrant();
    return null;
  }
}

export function storeOfflineOrderGrant(grant: OperationalOrderGrant, config: OperationalOrderConfig): string {
  if (typeof grant.grant !== 'string' || grant.grant.length < 20 || Number.isNaN(Date.parse(grant.expires_at))) {
    throw new Error('offline_order_grant_invalid_response');
  }
  const expiryMs = Date.parse(grant.expires_at) - Date.now();
  if (expiryMs <= 0 || expiryMs > 2 * 60 * 60_000) {
    throw new Error('offline_order_grant_invalid_expiry');
  }
  try {
    sessionStorage.setItem(OFFLINE_ORDER_GRANT_KEY, grant.grant);
    sessionStorage.setItem(OFFLINE_ORDER_GRANT_EXPIRY_KEY, grant.expires_at);
    sessionStorage.setItem(OFFLINE_ORDER_GRANT_BRANCH_KEY, config.branchId);
    sessionStorage.setItem(OFFLINE_ORDER_GRANT_DEVICE_KEY, config.deviceId);
    sessionStorage.setItem(OFFLINE_ORDER_GRANT_GATEWAY_KEY, config.gatewayUrl);
    return grant.grant;
  } catch (error) {
    clearOfflineOrderGrant();
    throw error;
  }
}

export type GatewayOperationalStatus = {
  ready: boolean;
  organization_id: string;
  branch_id: string;
  device_id: string;
  bundle_id: string;
  bundle_hash: string;
  lease_epoch: number;
};

export async function readGatewayOperationalStatus(gatewayUrl: string): Promise<GatewayOperationalStatus> {
  const normalized = normalizedGatewayUrl(gatewayUrl);
  if (!normalized) throw new Error('operational_order_gateway_invalid');
  let response: Response;
  try {
    response = await fetch(`${normalized}/api/v1/local/orders/status`);
  } catch {
    throw new OperationalOrderError(0, 'gateway_unavailable', 'Gateway no disponible.');
  }
  if (!response.ok) throw new OperationalOrderError(response.status, 'gateway_rejected', 'El gateway no confirmó su estado operacional.');
  const status = await response.json() as Partial<GatewayOperationalStatus>;
  if (!status.ready || typeof status.branch_id !== 'string' || !UUID_PATTERN.test(String(status.device_id))
    || !UUID_PATTERN.test(String(status.bundle_id)) || !Number.isInteger(status.lease_epoch) || Number(status.lease_epoch) < 1) {
    throw new Error('operational_order_gateway_not_ready');
  }
  return status as GatewayOperationalStatus;
}

export async function operationalOrderRequest<T>(
  config: OperationalOrderConfig,
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  if (!endpoint.startsWith('/') || endpoint.startsWith('//')) {
    throw new Error('operational_order_endpoint_invalid');
  }
  const grant = loadUsableOfflineOrderGrant(config);
  if (!grant) throw new OperationalOrderError(401, 'offline_order_grant_required', 'Se requiere una autorización operacional vigente.');
  let response: Response;
  try {
    const headers = new Headers(options.headers);
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    headers.set('Authorization', `Offline ${grant}`);
    response = await fetch(`${config.gatewayUrl}/api/v1/local/order-api${endpoint}`, {
      ...options,
      headers,
    });
  } catch {
    throw new OperationalOrderError(0, 'gateway_unavailable', 'Gateway no disponible. Conserva la misma clave para reintentar.');
  }
  if (!response.ok) {
    let body: { detail?: { code?: string; message?: string } | string } | undefined;
    try { body = await response.json() as typeof body; } catch { /* stable gateway error below */ }
    const detail = body?.detail;
    throw new OperationalOrderError(
      response.status,
      typeof detail === 'object' && detail?.code ? detail.code : 'gateway_rejected',
      typeof detail === 'object' && detail?.message ? detail.message : typeof detail === 'string' ? detail : 'El gateway rechazó el comando.',
    );
  }
  if (response.status === 204) return {} as T;
  return response.json() as Promise<T>;
}

export type OperationalOrderCommandStatus = {
  _offline: {
    command_id: string;
    status: Exclude<OfflineOrderStatus, 'GATEWAY_UNAVAILABLE'>;
    checkpoint?: number;
    code?: string;
  };
};

export function getOperationalOrderCommandStatus(
  config: OperationalOrderConfig,
  commandId: string,
): Promise<OperationalOrderCommandStatus> {
  if (!UUID_PATTERN.test(commandId)) throw new Error('operational_order_command_id_invalid');
  return operationalOrderRequest<OperationalOrderCommandStatus>(
    config,
    `/orders/commands/${encodeURIComponent(commandId)}`,
  );
}
