import { useCallback } from 'react';
import { fetchApi, loadOperationalOrderConfig, operationalOrderRequest } from '@restaurantos/api-client';
import type { OrderRequest } from './useCashTenderPreview';

/** Same operational authority for catalog, accounts, preview and commands. No cloud fallback. */
export function useCashierOrderRequest(branchId: string, userId: string, registerId: string) {
  let config: ReturnType<typeof loadOperationalOrderConfig> = null;
  let configError = '';
  try {
    config = loadOperationalOrderConfig();
    if (config && config.branchId !== branchId) configError = 'La operación local pertenece a otra sucursal.';
  } catch (error) { configError = error instanceof Error ? error.message : 'Configuración operacional inválida.'; }
  const gatewayUrl = config?.gatewayUrl || '';
  const deviceId = config?.deviceId || '';
  const authority = JSON.stringify([userId, branchId, registerId, gatewayUrl, deviceId]);
  const request: OrderRequest = useCallback(<T,>(endpoint: string, options: RequestInit = {}) => {
    if (configError) return Promise.reject(new Error(configError));
    return gatewayUrl ? operationalOrderRequest<T>({ branchId, gatewayUrl, deviceId }, endpoint, options)
      : fetchApi<T>(endpoint, options);
  }, [branchId, gatewayUrl, deviceId, configError]);
  return { request, authority, local: Boolean(gatewayUrl), configError };
}
