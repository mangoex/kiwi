import { ApiError } from '@restaurantos/api-client';
import { QueryClient } from '@tanstack/react-query';

export function createAdminQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: shouldRetryAdminQuery } } });
}

export function shouldRetryAdminQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return false;
  return failureCount < 3;
}
