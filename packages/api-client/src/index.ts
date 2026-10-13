export const API_BASE_URL = "/api/v1";
import { clearCashierLocalCapture } from './cashierDrafts';
import { subscribeToOperationalUnauthorized } from './operationalOrders';
import { branchWorkspaceSecret, clearBranchWorkspace } from './branchWorkspace';

subscribeToOperationalUnauthorized(clearCashierLocalCapture);

export * from './operationalOrders';
export * from './cashierDrafts';
export * from './adminAccess';
export * from './reconciliationV2';
export * from './branchWorkspace';

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

const unauthorizedListeners = new Set<() => void>();
let sessionGeneration = 0;

export function subscribeToUnauthorized(listener: () => void): () => void {
  unauthorizedListeners.add(listener);
  return () => { unauthorizedListeners.delete(listener); };
}

async function requestApi(endpoint: string, options: RequestInit, version: 'v1' | 'v2', notifyUnauthorized=true): Promise<Response> {
  const token = localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
  const requestGeneration = sessionGeneration;
  const suppliedHeaders = new Headers(options.headers);
  suppliedHeaders.delete('X-Branch-Context');
  suppliedHeaders.delete('Authorization');
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...Object.fromEntries(suppliedHeaders.entries()),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const workspace = branchWorkspaceSecret(token);
  if (workspace && !endpoint.startsWith('/auth/')) headers['X-Branch-Context'] = workspace;

  const response = await fetch(`${version === "v2" ? "/api/v2" : API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const currentToken = localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
    if (notifyUnauthorized && response.status === 401 && endpoint !== '/auth/login' && token && token === currentToken && requestGeneration === sessionGeneration) {
      sessionGeneration++;
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
  const response = await requestApi(endpoint, options, version);
  if (response.status === 204) {
    return {} as T;
  }

  const data: T = await response.json();
  if (endpoint === '/auth/login') { sessionGeneration++; clearBranchWorkspace(); }
  return data;
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
