// Memory-only quarantine for an interrupted authenticated session. Never stores credentials.
const captures = new Map<string, () => unknown | null>();
const snapshots = new Map<string, unknown>();

export function registerWorkspaceSnapshot(key: string, capture: () => unknown | null): () => void {
  captures.set(key, capture);
  return () => { if (captures.get(key) === capture) captures.delete(key); };
}

export function quarantineWorkspaceSnapshots(): void {
  for (const [key, capture] of captures) {
    const value = capture();
    if (value !== null) snapshots.set(key, structuredClone(value));
  }
}

export function readWorkspaceSnapshot<T>(key: string): T | undefined {
  const value = snapshots.get(key);
  return value === undefined ? undefined : structuredClone(value) as T;
}

export function discardWorkspaceSnapshot(key: string): void {
  snapshots.delete(key);
}
