import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchPublicOrderTracking } from '../api';
import { forgetTrackedReference, isTrackingReference, readTrackedReferences, rememberTrackedReference, startTrackingPoller, TRACKING_STORAGE_KEY } from '../orderTracking';
import type { PublicOrderTracking, TrackedOrderReference } from '../types';

function storage(): Storage | null {
  try { return window.localStorage; } catch { return null; }
}

export function usePublicOrderTracking(branchId?: string) {
  const [references, setReferences] = useState<TrackedOrderReference[]>(() => readTrackedReferences(storage()).references);
  const [storageAvailable, setStorageAvailable] = useState(() => readTrackedReferences(storage()).available);
  const [states, setStates] = useState<Record<string, PublicOrderTracking>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [checkedAt, setCheckedAt] = useState<Record<string, string>>({});
  const [selectedReference, setSelectedReference] = useState<string | null>(null);
  const completed = useRef(new Set<string>());
  const retryUntil = useRef(0);
  const scopedReferences = useMemo(() => references.filter(ref => ref.branch_id === branchId), [references, branchId]);
  const reference = scopedReferences.some(ref => ref.public_reference === selectedReference)
    ? selectedReference : scopedReferences[0]?.public_reference || null;

  useEffect(() => {
    const synchronize = (event: StorageEvent) => {
      if (event.key !== null && event.key !== TRACKING_STORAGE_KEY) return;
      const loaded = readTrackedReferences(storage());
      setStorageAvailable(loaded.available);
      if (loaded.available) setReferences(current => JSON.stringify(current) === JSON.stringify(loaded.references)
        ? current : loaded.references);
    };
    window.addEventListener('storage', synchronize);
    return () => window.removeEventListener('storage', synchronize);
  }, []);

  useEffect(() => startTrackingPoller(scopedReferences.filter(ref => !completed.current.has(ref.public_reference)), {
    request: fetchPublicOrderTracking,
    onUpdate: state => {
      if (state.terminal) completed.current.add(state.public_reference);
      setStates(current => ({ ...current, [state.public_reference]: state }));
      setErrors(current => ({ ...current, [state.public_reference]: '' }));
      setCheckedAt(current => ({ ...current, [state.public_reference]: new Date().toISOString() }));
    },
    onError: (ref, message) => setErrors(current => ({ ...current, [ref]: message })),
    isVisible: () => document.visibilityState !== 'hidden',
    subscribeVisibility: listener => {
      document.addEventListener('visibilitychange', listener);
      return () => document.removeEventListener('visibilitychange', listener);
    },
    setTimer: (listener, delay) => window.setTimeout(listener, delay),
    clearTimer: timer => window.clearTimeout(timer),
    getRetryUntil: () => retryUntil.current,
    onRetryUntil: deadline => { retryUntil.current = deadline; },
  }), [scopedReferences]);

  const remember = useCallback((publicReference: string, submittedBranchId: string) => {
    const ref = { public_reference: publicReference, branch_id: submittedBranchId };
    if (!isTrackingReference(ref)) return;
    setStorageAvailable(rememberTrackedReference(storage(), ref));
    setReferences(current => [ref, ...current.filter(item => item.public_reference !== publicReference)]);
    setSelectedReference(publicReference);
  }, []);
  const dismiss = useCallback((publicReference: string) => {
    if (!branchId) return;
    setStorageAvailable(forgetTrackedReference(storage(), branchId, publicReference));
    setReferences(current => current.filter(ref => !(ref.branch_id === branchId && ref.public_reference === publicReference)));
  }, [branchId]);

  return { references: scopedReferences, states, errors, checkedAt, storageAvailable,
    selectedReference: reference, select: setSelectedReference, remember, dismiss };
}

export type OrderTrackingState = ReturnType<typeof usePublicOrderTracking>;
