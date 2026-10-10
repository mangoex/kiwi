export const API_BASE_URL = "/api/v1";
import { clearCashierLocalCapture } from './cashierDrafts';
import { subscribeToOperationalUnauthorized } from './operationalOrders';

subscribeToOperationalUnauthorized(clearCashierLocalCapture);

export * from './operationalOrders';
export * from './cashierDrafts';
export * from './adminAccess';
export * from './reconciliationV2';

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

async function requestApi(endpoint: string, options: RequestInit, version: 'v1' | 'v2'): Promise<Response> {
  const token = localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
  const requestGeneration = sessionGeneration;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${version === "v2" ? "/api/v2" : API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const currentToken = localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
    if (response.status === 401 && endpoint !== '/auth/login' && token && token === currentToken && requestGeneration === sessionGeneration) {
      sessionGeneration++;
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
  if (endpoint === '/auth/login') sessionGeneration++;
  return data;
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
