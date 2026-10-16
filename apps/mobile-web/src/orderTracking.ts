import type { PublicOrderTracking, TrackedOrderReference } from './types';

export const TRACKING_STORAGE_KEY = 'kiwi_public_tracking_v1';
const referencePattern = /^PI-[0-9A-F]{32}$/;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const terminalStatuses = new Set(['DELIVERED', 'CLOSED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'FAILED', 'RETURNED']);
const statuses = new Set(['PENDING_REVIEW', 'ACCEPTED', 'DRAFT', 'SENT_TO_PRODUCTION', 'IN_PRODUCTION', 'READY', 'IN_DELIVERY', ...terminalStatuses]);
type StorageReader = Pick<Storage, 'getItem'>;
type TrackingStorage = StorageReader & Pick<Storage, 'setItem'>;

export function isTrackingReference(value: unknown): value is TrackedOrderReference {
  if (!value || typeof value !== 'object') return false;
  const ref = value as Partial<TrackedOrderReference>;
  return typeof ref.public_reference === 'string' && referencePattern.test(ref.public_reference)
    && typeof ref.branch_id === 'string' && uuidPattern.test(ref.branch_id);
}

export function readTrackedReferences(storage: StorageReader | null, branchId?: string): {
  references: TrackedOrderReference[]; available: boolean;
} {
  try {
    if (!storage) return { references: [], available: false };
    const raw = storage.getItem(TRACKING_STORAGE_KEY);
    if (!raw) return { references: [], available: true };
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return { references: [], available: true };
    const record = parsed as { version?: unknown; references?: unknown };
    if (record.version !== 1 || !Array.isArray(record.references)) return { references: [], available: true };
    const seen = new Set<string>();
    const references = record.references.filter(isTrackingReference).filter(ref => {
      if (seen.has(ref.public_reference)) return false;
      seen.add(ref.public_reference); return !branchId || ref.branch_id === branchId;
    }).map(ref => ({ public_reference: ref.public_reference, branch_id: ref.branch_id }));
    return { references, available: true };
  } catch { return { references: [], available: false }; }
}

export function rememberTrackedReference(storage: TrackingStorage | null, ref: TrackedOrderReference): boolean {
  if (!storage || !isTrackingReference(ref)) return false;
  try {
    const existing = readTrackedReferences(storage).references.filter(item => item.public_reference !== ref.public_reference);
    storage.setItem(TRACKING_STORAGE_KEY, JSON.stringify({ version: 1, references: [
      { public_reference: ref.public_reference, branch_id: ref.branch_id }, ...existing,
    ] }));
    return true;
  } catch { return false; }
}

export function forgetTrackedReference(storage: TrackingStorage | null, branchId: string, reference: string): boolean {
  if (!storage) return false;
  try {
    const references = readTrackedReferences(storage).references.filter(ref =>
      !(ref.branch_id === branchId && ref.public_reference === reference));
    storage.setItem(TRACKING_STORAGE_KEY, JSON.stringify({ version: 1, references })); return true;
  } catch { return false; }
}

export function parseTrackingResponse(value: unknown, reference: string, branchId: string): PublicOrderTracking {
  if (!value || typeof value !== 'object') throw new Error('public_tracking_invalid_response');
  const data = value as PublicOrderTracking;
  const date = (input: unknown) => typeof input === 'string' && /^\d{4}-\d\d-\d\dT/.test(input)
    && /(?:Z|[+-]\d\d:\d\d)$/.test(input) && Number.isFinite(Date.parse(input));
  if (!isTrackingReference(data) || data.public_reference !== reference || data.branch_id !== branchId
    || !['PENDING_REVIEW', 'ACCEPTED', 'REJECTED', 'EXPIRED'].includes(data.status)
    || !statuses.has(data.display_status) || (data.operational_status !== null && !statuses.has(data.operational_status))
    || data.terminal !== terminalStatuses.has(data.display_status)
    || !Number.isSafeInteger(data.total_cents) || data.total_cents < 0
    || !Number.isSafeInteger(data.version) || data.version < 1
    || !['delivery', 'takeout', 'dine-in'].includes(data.service_type)
    || typeof data.branch_name !== 'string' || data.branch_name.length > 160
    || !(data.folio === null || (typeof data.folio === 'string' && data.folio.length <= 64))
    || !date(data.created_at) || !date(data.updated_at)) throw new Error('public_tracking_invalid_response');
  return {
    public_reference: data.public_reference, branch_id: data.branch_id, branch_name: data.branch_name,
    status: data.status, operational_status: data.operational_status, display_status: data.display_status,
    version: data.version, total_cents: data.total_cents, service_type: data.service_type,
    created_at: data.created_at, updated_at: data.updated_at, folio: data.folio, terminal: data.terminal,
  };
}

export function getTrackingPresentation(order: PublicOrderTracking): {
  title: string; description: string; step: number; steps: string[]; exception: boolean;
} {
  const delivery = order.service_type === 'delivery';
  const steps = ['Confirmado', 'Preparando', delivery ? 'En camino' : 'Listo', 'Entregado'];
  const states: Record<string, [string, string, number]> = {
    PENDING_REVIEW: ['Esperando confirmación', 'La sucursal está revisando tu solicitud.', -1],
    ACCEPTED: ['Pedido confirmado', 'La sucursal aceptó tu pedido.', 0],
    SENT_TO_PRODUCTION: ['En preparación', 'Tu pedido está en cocina.', 1],
    IN_PRODUCTION: ['En preparación', 'Tu pedido está en cocina.', 1],
    READY: [delivery ? 'Listo para salir' : 'Listo para recoger', delivery ? 'Esperando salida del repartidor.' : 'Puedes recoger tu pedido en la sucursal.', delivery ? 1 : 2],
    IN_DELIVERY: ['En camino', 'Tu pedido salió a domicilio.', 2],
    DELIVERED: ['Pedido entregado', '¡Gracias por pedir en Kiwi!', 3],
    CLOSED: ['Pedido finalizado', 'La sucursal finalizó este pedido.', -1],
    REJECTED: ['Solicitud no aceptada', 'Contacta a la sucursal si necesitas ayuda.', -1],
    CANCELLED: ['Pedido cancelado', 'Contacta a la sucursal si necesitas ayuda.', -1],
    EXPIRED: ['Solicitud expirada', 'Consulta con la sucursal antes de volver a pedir.', -1],
    FAILED: ['Problema con el pedido', 'Contacta a la sucursal para conocer el estado.', -1],
    RETURNED: ['Pedido devuelto', 'Contacta a la sucursal para conocer el estado.', -1],
  };
  const [title, description, step] = states[order.display_status] || ['Estado por confirmar', 'Actualiza el seguimiento.', -1];
  return { title, description, step, steps, exception: order.terminal && order.display_status !== 'DELIVERED' };
}

export class TrackingRequestError extends Error {
  constructor(public readonly status: number, public readonly retryAfterMs = 30000) {
    super(status === 404 ? 'No encontramos esta referencia.' : 'No pudimos actualizar el seguimiento.');
  }
}

type PollingOptions = {
  request: (ref: TrackedOrderReference, signal: AbortSignal) => Promise<PublicOrderTracking>;
  onUpdate: (state: PublicOrderTracking) => void;
  onError: (reference: string, message: string) => void;
  isVisible: () => boolean;
  subscribeVisibility: (listener: () => void) => () => void;
  setTimer: (listener: () => void, delay: number) => number;
  clearTimer: (timer: number) => void;
  now?: () => number;
  getRetryUntil?: () => number;
  onRetryUntil?: (deadline: number) => void;
};

export function startTrackingPoller(references: TrackedOrderReference[], options: PollingOptions): () => void {
  let disposed = false, busy = false, generation = 0;
  let timer: number | undefined, controller: AbortController | undefined;
  const completed = new Set<string>();
  const now = options.now || Date.now;
  let retryUntil = 0;
  const remainingBackoff = () => Math.max(retryUntil, options.getRetryUntil?.() || 0) - now();
  const clearTimer = () => { if (timer !== undefined) options.clearTimer(timer); timer = undefined; };
  const poll = async () => {
    if (disposed || busy || !options.isVisible()) return;
    const remaining = remainingBackoff();
    if (remaining > 0) {
      clearTimer(); timer = options.setTimer(() => { timer = undefined; void poll(); }, remaining);
      return;
    }
    const active = references.filter(ref => !completed.has(ref.public_reference));
    if (!active.length) return;
    busy = true; const current = generation; let delay = 5000;
    controller = new AbortController();
    try {
      for (const ref of active) {
        if (disposed || current !== generation || !options.isVisible()) break;
        try {
          const result = await options.request(ref, controller.signal);
          if (disposed || current !== generation || !options.isVisible()) break;
          options.onUpdate(result);
          if (result.terminal) completed.add(ref.public_reference);
        } catch (error) {
          if (disposed || current !== generation || !options.isVisible()) break;
          const retry = error instanceof TrackingRequestError ? error.retryAfterMs : 30000;
          delay = Math.max(delay, retry);
          retryUntil = now() + retry;
          options.onRetryUntil?.(retryUntil);
          options.onError(ref.public_reference, error instanceof TrackingRequestError
            ? error.message : 'Sin conexión. Conservamos el último estado confirmado.');
          if (error instanceof TrackingRequestError && [429, 503].includes(error.status)) break;
        }
      }
    } finally {
      busy = false;
      if (!disposed && options.isVisible() && references.some(ref => !completed.has(ref.public_reference))) {
        clearTimer(); timer = options.setTimer(() => { timer = undefined; void poll(); }, Math.max(delay, remainingBackoff()));
      }
    }
  };
  const unsubscribe = options.subscribeVisibility(() => {
    generation++; clearTimer(); controller?.abort();
    if (options.isVisible()) void poll();
  });
  void poll();
  return () => { disposed = true; generation++; clearTimer(); controller?.abort(); unsubscribe(); };
}
