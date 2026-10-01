export const API_BASE_URL = "/api/v1";

export * from './operationalOrders';

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

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
  const requestGeneration = sessionGeneration;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const currentToken = localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
    if (response.status === 401 && endpoint !== '/auth/login' && token && token === currentToken && requestGeneration === sessionGeneration) {
      sessionGeneration++;
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

  if (response.status === 204) {
    return {} as T;
  }

  const data: T = await response.json();
  if (endpoint === '/auth/login') sessionGeneration++;
  return data;
}
