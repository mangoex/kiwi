const guards = new Set<() => boolean>();
export function registerWorkspaceNavigationGuard(guard: () => boolean): () => void {
  guards.add(guard);
  return () => { guards.delete(guard); };
}
export function confirmWorkspaceNavigation(): boolean {
  for (const guard of guards) if (!guard()) return false;
  return true;
}
