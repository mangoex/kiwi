export const API_BASE_URL = "/api/v1";
import { clearCashierLocalCapture } from './cashierDrafts';
import { subscribeToOperationalUnauthorized } from './operationalOrders';
import { branchWorkspaceSecret, clearBranchWorkspace, parseSessionFinancialAccess } from './branchWorkspace';

subscribeToOperationalUnauthorized(clearCashierLocalCapture);

export * from './operationalOrders';
export * from './cashierDrafts';
export * from './adminAccess';
export * from './reconciliationV2';
export * from './branchWorkspace';

export class ApiError extends Error {
  public operationalIntentPending = false;
  constructor(public status: number, public code: string, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export function hasPendingOperationalIntent(error: unknown): boolean {
  return Boolean(error && typeof error === 'object' && 'operationalIntentPending' in error
    && error.operationalIntentPending === true);
}
function uncertainOperationalError(error: unknown): ApiError {
  const failure = error instanceof ApiError ? error : new ApiError(503,
    'operational_command_result_uncertain', 'No se pudo confirmar el resultado. Recupera la operación antes de repetirla.');
  failure.operationalIntentPending = true;
  return failure;
}

const unauthorizedListeners = new Set<() => void>();
let sessionGeneration = 0;
let readAuthorityGeneration = 0;
let readAuthorityIdentity: string | null = null;
const readAuthorityListeners = new Set<() => void>();
export function subscribeToApiReadAuthorityChange(listener: () => void): () => void {
  readAuthorityListeners.add(listener);
  return () => { readAuthorityListeners.delete(listener); };
}
/** Confirmed server scope only; never inferred from a role label or cached money. */
export function setApiReadAuthority(profile: {
  organization_id?: string;
  user: {id: string};
  active_branch: {id: string} | null;
  scope: {authorization_version?: number};
  financial_access?: unknown;
} | null): void {
  const access = profile?.financial_access === undefined ? undefined : parseSessionFinancialAccess(profile.financial_access);
  if (access && access.authorization_version !== profile?.scope.authorization_version) {
    throw new Error('financial_session_authority_changed');
  }
  const identity = profile ? JSON.stringify([
    profile.organization_id, profile.user.id, profile.active_branch?.id,
    profile.scope.authorization_version, access,
  ]) : null;
  if (identity === readAuthorityIdentity) return;
  readAuthorityIdentity = identity;
  readAuthorityGeneration++;
  for (const listener of readAuthorityListeners) listener();
}

const operationalIntentListeners = new Set<() => void>();
export function subscribeToOperationalIntentChange(listener: () => void): () => void {
  operationalIntentListeners.add(listener);
  return () => { operationalIntentListeners.delete(listener); };
}
function notifyOperationalIntents(): void {
  for (const listener of operationalIntentListeners) listener();
}

export function subscribeToUnauthorized(listener: () => void): () => void {
  unauthorizedListeners.add(listener);
  return () => { unauthorizedListeners.delete(listener); };
}

async function requestApi(endpoint: string, options: RequestInit, version: 'v1' | 'v2', notifyUnauthorized=true, operationalIntent?: string): Promise<Response> {
  const token = localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
  const requestGeneration = sessionGeneration;
  const suppliedHeaders = new Headers(options.headers);
  suppliedHeaders.delete('X-Branch-Context');
  suppliedHeaders.delete('Authorization');
  suppliedHeaders.delete('X-Operational-Intent');
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...Object.fromEntries(suppliedHeaders.entries()),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const workspace = branchWorkspaceSecret(token);
  const recovery = (endpoint === '/operational-intents' && (options.method || 'GET').toUpperCase() === 'GET')
    || /^\/operational-intents\/[^/]+\/resolve$/.test(endpoint);
  if (workspace && !endpoint.startsWith('/auth/') && !recovery) headers['X-Branch-Context'] = workspace;
  if (operationalIntent) headers['X-Operational-Intent'] = operationalIntent;

  const response = await fetch(`${version === "v2" ? "/api/v2" : API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const currentToken = localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
    if (notifyUnauthorized && response.status === 401 && endpoint !== '/auth/login' && token && token === currentToken && requestGeneration === sessionGeneration) {
      sessionGeneration++;
      setApiReadAuthority(null);
      clearBranchWorkspace();
      clearCashierLocalCapture();
      localStorage.removeItem("auth_token");
      sessionStorage.removeItem("auth_token");
      for (const listener of unauthorizedListeners) listener();
    }

    let errorData;
    try {
      errorData = await response.json();
    } catch {
      throw new ApiError(response.status, "unknown_error", "An unknown error occurred");
    }

    throw new ApiError(
      response.status,
      errorData.detail?.code || "api_error",
      errorData.detail?.message || errorData.detail || "API Error"
    );
  }

  return response;
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}, version: 'v1' | 'v2' = 'v1'): Promise<T> {
  const credential = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  const workspace = branchWorkspaceSecret(credential);
  const readGeneration = readAuthorityGeneration;
  const requestSessionGeneration = sessionGeneration;
  const readOnly = ['GET', 'HEAD'].includes((options.method || 'GET').toUpperCase());
  const assertReadContext = () => {
    const current = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    if (readOnly && (current !== credential || branchWorkspaceSecret(current) !== workspace
      || readGeneration !== readAuthorityGeneration || requestSessionGeneration !== sessionGeneration)) {
      throw new ApiError(409, 'api_read_context_changed', 'La sesión o los permisos cambiaron. Vuelve a consultar.');
    }
  };
  const durableVersion = version === 'v1' || (version === 'v2'
    && (/^\/cash\/shifts\/open$/.test(endpoint) || /^\/cash\/shifts\/[^/]+\/close-operationally$/.test(endpoint)));
  const command = workspace && durableVersion && options.method?.toUpperCase() === 'POST'
    ? operationalCommandIdentity(endpoint) : null;
  let intent: OperationalIntentReceipt | null = null;
  const assertOriginalContext = () => {
    const current = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    if (current !== credential || branchWorkspaceSecret(current) !== workspace) {
      throw uncertainOperationalError(new ApiError(409, 'operational_command_context_changed', 'La sesión cambió; recupera la operación en su contexto original.'));
    }
  };
  if (command) {
    const key = new Headers(options.headers).get('Idempotency-Key')?.trim();
    const [minimum, maximum] = command.kind.startsWith('cash.') ? [1, 180] : [12, 160];
    if (!key || key.length < minimum || key.length > maximum
      || typeof options.body !== 'string') {
      throw new ApiError(409, 'operational_command_required', 'La operación necesita su clave y cuerpo originales.');
    }
    const prepared = await requestApi('/operational-intents', {
      method: 'POST', headers: {'Idempotency-Key': key}, signal: options.signal,
      body: JSON.stringify({...command, payload: JSON.parse(options.body)}),
    }, 'v1').catch(error => {notifyOperationalIntents(); throw uncertainOperationalError(error);});
    intent = await prepared.json().catch(error => {notifyOperationalIntents(); throw uncertainOperationalError(error);}) as OperationalIntentReceipt;
    notifyOperationalIntents();
    if (!intent || !resourceIdPattern.test(intent.id) || intent.kind !== command.kind
      || !['prepared', 'applied', 'acknowledged', 'no_effect'].includes(intent.state)) {
      throw uncertainOperationalError(new ApiError(503, 'operational_command_receipt_invalid', 'No se pudo confirmar el registro de la operación.'));
    }
    assertOriginalContext();
    if (intent.state === 'no_effect') {
      throw new ApiError(409, 'operational_command_terminal', 'La operación anterior se resolvió sin efecto.');
    }
  }
  const response = await requestApi(endpoint, options, version, true, intent?.id).catch(error => {
    if (intent) {notifyOperationalIntents(); throw uncertainOperationalError(error);}
    throw error;
  });
  if (response.status === 204) {
    assertReadContext();
    return {} as T;
  }

  const data: T = await response.json().catch(error => {
    if (intent) {notifyOperationalIntents(); throw uncertainOperationalError(error);}
    throw error;
  });
  if (intent) {
    assertOriginalContext();
    try {
      // The financial response is known. Failed housekeeping leaves the server blocker intact.
      await requestApi(`/operational-intents/${intent.id}/resolve`, {method: 'POST'}, 'v1');
    } catch {
      // Recovery is available from the authenticated pending list after reconnecting.
    }
    assertOriginalContext();
    notifyOperationalIntents();
  }
  assertReadContext();
  if (/^\/operational-intents\/[^/]+\/resolve$/.test(endpoint)) notifyOperationalIntents();
  if (endpoint === '/auth/login') { sessionGeneration++; setApiReadAuthority(null); clearBranchWorkspace(); }
  return data;
}

const resourceIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export interface OperationalIntentReceipt {
  id: string;
  kind: 'order.create' | 'payment.confirm' | 'cash.movement.create' | 'cash.movement.compensate'
    | 'cash.shift.open' | 'cash.shift.close' | 'cash.shift.close.register';
  branch_id: string;
  state: 'prepared' | 'applied' | 'acknowledged' | 'no_effect';
  resource_id: string | null;
}
function operationalCommandIdentity(endpoint: string): {kind: OperationalIntentReceipt['kind']; target_id: string | null} | null {
  if (endpoint === '/orders') return {kind: 'order.create', target_id: null};
  if (endpoint === '/cash/movements') return {kind: 'cash.movement.create', target_id: null};
  if (endpoint === '/cash/shifts/open' || endpoint === '/cash-shifts/open') return {kind:'cash.shift.open', target_id:null};
  if (endpoint === '/cash-shifts/close') return {kind:'cash.shift.close.register', target_id:null};
  const close = /^\/cash\/shifts\/([^/]+)\/close-operationally$/.exec(endpoint);
  if (close && resourceIdPattern.test(close[1])) return {kind:'cash.shift.close', target_id:close[1]};
  const compensate = /^\/cash\/movements\/([^/]+)\/compensations$/.exec(endpoint);
  if (compensate && resourceIdPattern.test(compensate[1])) return {kind:'cash.movement.compensate', target_id:compensate[1]};
  const payment = /^\/orders\/([^/]+)\/payments$/.exec(endpoint);
  return payment && resourceIdPattern.test(payment[1]) ? {kind: 'payment.confirm', target_id: payment[1]} : null;
}
export async function listPendingOperationalIntents(): Promise<OperationalIntentReceipt[]> {
  return fetchApi('/operational-intents');
}
export async function resolveOperationalIntent(id: string): Promise<OperationalIntentReceipt> {
  if (!resourceIdPattern.test(id)) throw new ApiError(400, 'operational_command_reference_invalid', 'La referencia no es válida.');
  return fetchApi(`/operational-intents/${id}/resolve`, {method: 'POST'});
}

/** An optional central projection cannot expire an independently authorized gateway session. */
export async function fetchOptionalCentralSession<T>(signal?: AbortSignal): Promise<T | null> {
  try {
    const response = await requestApi('/auth/session', {signal}, 'v1', false);
    return await response.json() as T;
  } catch {
    return null;
  }
}

export async function downloadReconciliationWorkbook(branchId: string, month: number, year: number): Promise<void> {
  const params = new URLSearchParams({branch_id: branchId, month: String(month), year: String(year)});
  const response = await requestApi(`/reports/branch-reconciliation/export?${params}`, {}, 'v2');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = `Corte_Kiwi_${year}_${month}.xlsx`;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Fiscal artifacts always pass through the authenticated API, never a DTO's remote URL. */
export async function downloadFiscalInvoice(invoiceId: string, format: 'pdf' | 'xml'): Promise<void> {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(invoiceId)
    || !['pdf', 'xml'].includes(format)) {
    throw new ApiError(400, 'fiscal_document_reference_invalid', 'La referencia del documento no es válida.');
  }
  const credential = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  if (!credential) throw new ApiError(401, 'actor_required', 'Inicia sesión para descargar el documento.');
  const generation = sessionGeneration;
  const context = branchWorkspaceSecret(credential);
  const response = await requestApi(`/invoicing/invoices/${invoiceId}/${format}`, {}, 'v1');
  const blob = await response.blob();
  if (credential !== (localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token'))
    || generation !== sessionGeneration || context !== branchWorkspaceSecret(credential)) {
    throw new ApiError(409, 'fiscal_download_context_changed', 'La sesión cambió durante la descarga.');
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  try {
    link.href = url;
    link.download = `factura-${invoiceId}.${format}`;
    document.body.append(link);
    link.click();
  } finally {
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
export * from './deliveryFee';
