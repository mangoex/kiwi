import { useEffect, useState } from 'react';
export type WorkspaceRequest = <T>(path: string, options?: RequestInit) => Promise<T>;
export function usePythonPreview<T>(request: WorkspaceRequest, path: string, payload: unknown, enabled = true) {
  const body = JSON.stringify(payload);
  const identity = path + body;
  const [result, setResult] = useState<{ identity: string; data?: T; error?: string }>({ identity: '' });
  useEffect(() => {
    if (!enabled) { setResult({ identity: '' }); return; }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void request<T>(path, { method: 'POST', body, signal: controller.signal })
        .then(data => { if (!controller.signal.aborted) setResult({ identity, data }); })
        .catch((error: unknown) => { if (!controller.signal.aborted) setResult({ identity, error: error instanceof Error ? error.message : 'No se pudo consultar el cálculo.' }); });
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [request, path, body, identity, enabled]);
  const current = enabled && result.identity === identity ? result : undefined;
  return { data: current?.data, error: current?.error, pending: enabled && !current };
}
