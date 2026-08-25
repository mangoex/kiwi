import { fetchApi } from '@restaurantos/api-client';

interface PosHandoffResponse {
  handoff_code: string;
  target_app: 'pos';
  expires_in_seconds: number;
}

export async function redirectToPos(route: string): Promise<void> {
  const handoff = await fetchApi<PosHandoffResponse>('/auth/pos-handoffs', { method: 'POST' });
  const normalizedRoute = route.replace(/^\/+|\/+$/g, '') || 'pos';
  const isDev = window.location.hostname === 'localhost'
    || window.location.hostname === '127.0.0.1'
    || (window.location.port !== '' && window.location.port !== '80' && window.location.port !== '443');
  const target = isDev
    ? `http://localhost:3001/pos/${normalizedRoute}`
    : `/pos/${normalizedRoute}`;
  window.location.assign(`${target}#handoff=${encodeURIComponent(handoff.handoff_code)}`);
}
