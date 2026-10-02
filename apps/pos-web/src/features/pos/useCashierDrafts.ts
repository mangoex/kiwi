import { useEffect, useRef, useState } from 'react';
import { cashierDraftStorageKey, holdCashierDraft, readCashierDrafts, restoreHeldCashierDraft,
  saveActiveCashierDraft, subscribeToUnauthorized, subscribeToOperationalUnauthorized, type CashierDraft, type CashierDraftScope, type DraftLine } from '@restaurantos/api-client';

/** Persistent browser capture with one writer per cashier/register/authority. */
export function useCashierDrafts<T extends DraftLine>(
  scope: CashierDraftScope | null, enabled: boolean, payload: Omit<CashierDraft<T>, 'id' | 'paymentKey' | 'createdAt'> | null,
  onRestore: (draft: CashierDraft<T> | null) => void, checkoutUncertain: () => boolean,
) {
  const identity = scope ? cashierDraftStorageKey(scope) : '';
  const [readyIdentity, setReadyIdentity] = useState('');
  const [held, setHeld] = useState<CashierDraft<T>[]>([]);
  const [error, setError] = useState('');
  const [captureBlocked, setCaptureBlocked] = useState(false);
  const restoreRef = useRef(onRestore); restoreRef.current = onRestore;
  const payloadRef = useRef(payload); payloadRef.current = payload;
  const scopeRef = useRef(scope); scopeRef.current = scope;
  const uncertainRef = useRef(checkoutUncertain); uncertainRef.current = checkoutUncertain;
  const draftIdentityRef = useRef<{ id: string; paymentKey: string; createdAt: string }>({ id: crypto.randomUUID(), paymentKey: crypto.randomUUID(), createdAt: new Date().toISOString() });
  const mountedScopeRef = useRef('');
  const serialized = JSON.stringify(payload);

  useEffect(() => {
    if (!enabled || !scope || !identity) return;
    let mounted = true;
    let release: (() => void) | undefined;
    let released = false;
    const invalidate = () => {
      mountedScopeRef.current = ''; released = true; release?.();
      setCaptureBlocked(true); setError('La sesión cambió. Vuelve a abrir el POS con tu cuenta.');
    };
    const storageChanged = (event: StorageEvent) => { if (event.key === 'auth_token') invalidate(); };
    const unsubscribe = subscribeToUnauthorized(invalidate);
    const unsubscribeOperational = subscribeToOperationalUnauthorized(invalidate);
    window.addEventListener('storage', storageChanged);
    mountedScopeRef.current = '';
    setError(''); setCaptureBlocked(false);
    if (!navigator.locks) {
      setError('Este navegador no permite conservar capturas con seguridad. Usa una versión compatible.');
      setCaptureBlocked(true);
      return () => { unsubscribe(); unsubscribeOperational(); window.removeEventListener('storage', storageChanged); };
    }
    void navigator.locks.request(identity, { ifAvailable: true }, async (lock) => {
      if (!mounted) return;
      if (!lock) {
        setError('Esta caja tiene una captura abierta en otra pestaña. Continúa allí o ciérrala para recuperarla aquí.');
        setCaptureBlocked(true); return;
      }
      try {
        const book = readCashierDrafts<T>(localStorage, scope);
        if (book.active) {
          draftIdentityRef.current = { id: book.active.id, paymentKey: book.active.paymentKey, createdAt: book.active.createdAt };
          restoreRef.current(book.active);
        } else {
          draftIdentityRef.current = { id: crypto.randomUUID(), paymentKey: crypto.randomUUID(), createdAt: new Date().toISOString() };
          restoreRef.current(null);
        }
        setHeld(book.held);
        mountedScopeRef.current = identity;
        setReadyIdentity(identity);
        await new Promise<void>((resolve) => { release = resolve; if (released) resolve(); });
      } catch (reason) {
        if (mounted) { setError(reason instanceof Error ? reason.message : 'No se pudo recuperar la captura.'); setCaptureBlocked(true); }
      }
    }).catch((reason: unknown) => {
      if (mounted) { setError(reason instanceof Error ? reason.message : 'No se pudo abrir el almacenamiento.'); setCaptureBlocked(true); }
    });
    return () => { mounted = false; released = true; release?.(); mountedScopeRef.current = '';
      unsubscribe(); unsubscribeOperational(); window.removeEventListener('storage', storageChanged); };
  }, [identity, enabled]);

  const ready = enabled && Boolean(identity) && readyIdentity === identity && mountedScopeRef.current === identity;
  const flush = () => {
    if (!ready || !scopeRef.current) throw new Error('Espera a recuperar la captura de esta caja.');
    saveActiveCashierDraft(localStorage, scopeRef.current, payloadRef.current
      ? { ...payloadRef.current, ...draftIdentityRef.current } : null);
  };
  useEffect(() => {
    if (!ready) return;
    try { if (uncertainRef.current()) return; flush(); setError(''); } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No se pudo conservar la captura.');
    }
  }, [serialized, ready, identity]);

  const hold = () => {
    if (uncertainRef.current()) throw new Error('Resuelve la confirmación pendiente antes de dejar en espera.');
    flush();
    holdCashierDraft(localStorage, scopeRef.current!);
    setHeld(readCashierDrafts<T>(localStorage, scopeRef.current!).held);
    draftIdentityRef.current = { id: crypto.randomUUID(), paymentKey: crypto.randomUUID(), createdAt: new Date().toISOString() };
    restoreRef.current(null);
  };
  const restore = (id: string) => {
    if (uncertainRef.current()) throw new Error('Resuelve la confirmación pendiente antes de recuperar otra captura.');
    flush();
    const draft = restoreHeldCashierDraft<T>(localStorage, scopeRef.current!, id);
    draftIdentityRef.current = { id: draft.id, paymentKey: draft.paymentKey, createdAt: draft.createdAt };
    setHeld(readCashierDrafts<T>(localStorage, scopeRef.current!).held);
    restoreRef.current(draft);
  };
  const clearActive = () => {
    if (!scopeRef.current || mountedScopeRef.current !== identity
      || cashierDraftStorageKey(scopeRef.current) !== identity) throw new Error('El contexto cambió. No se retiró ninguna captura de otra caja.');
    saveActiveCashierDraft(localStorage, scopeRef.current, null);
    draftIdentityRef.current = { id: crypto.randomUUID(), paymentKey: crypto.randomUUID(), createdAt: new Date().toISOString() };
  };
  return { ready, held, error, captureBlocked, hold, restore, clearActive, identity: draftIdentityRef.current };
}
