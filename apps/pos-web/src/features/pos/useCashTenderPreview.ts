import { useEffect, useRef, useState } from 'react';

export interface CashTender {
  received_cents: number;
  change_cents: number;
  shortfall_cents: number;
  can_confirm: boolean;
}
export interface PaymentPreview {
  total_cents: number;
  cash_tender?: CashTender;
}
export type OrderRequest = <T>(endpoint: string, options?: RequestInit) => Promise<T>;

/** Results belong to the exact input and authority, never a previous received amount. */
export function useCashTenderPreview(
  request: OrderRequest, authority: string, endpoint: string,
  payload: Record<string, unknown> | null,
) {
  const requestRef = useRef(request);
  requestRef.current = request;
  const body = payload === null ? '' : JSON.stringify(payload);
  const identity = JSON.stringify([authority, endpoint, body]);
  const [result, setResult] = useState<{ identity: string; data?: PaymentPreview; error?: string } | null>(null);
  useEffect(() => {
    if (!body) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void requestRef.current<PaymentPreview>(endpoint, {
        method: 'POST', body, signal: controller.signal,
      }).then((data) => {
        if (!controller.signal.aborted) setResult({ identity, data });
      }).catch((error: unknown) => {
        if (!controller.signal.aborted) setResult({ identity,
          error: error instanceof Error ? error.message : 'No fue posible calcular el cambio.' });
      });
    }, 180);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [identity, body, endpoint]);
  return result?.identity === identity ? result : null;
}
