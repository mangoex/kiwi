const guards = new Set<() => boolean>();
let refreshBrowserContext: (() => void) | null = null;
/** Install before the router subscribes: popstate listeners at window run in registration order. */
export function initializeWorkspaceNavigation(): void {
  if (refreshBrowserContext || typeof window === 'undefined' || !window.addEventListener) return;
  let index: number | undefined = window.history.state?.idx;
  let url = window.location.href;
  let restoring = false;
  refreshBrowserContext = () => { index = window.history.state?.idx; url = window.location.href; };
  const pop = (event: PopStateEvent) => {
    const nextIndex: number | undefined = window.history.state?.idx;
    if (restoring) { restoring = false; index = nextIndex; url = window.location.href; return; }
    if (!confirmWorkspaceNavigation()) {
      event.stopImmediatePropagation();
      if (typeof index === 'number' && typeof nextIndex === 'number' && index !== nextIndex) {
        restoring = true; window.history.go(index - nextIndex);
      } else {
        window.history.replaceState(window.history.state, '', url);
      }
      return;
    }
    index = nextIndex; url = window.location.href;
  };
  window.addEventListener('popstate', pop, true);
}
export function registerWorkspaceNavigationGuard(guard: () => boolean): () => void {
  initializeWorkspaceNavigation();
  if (!guards.size) refreshBrowserContext?.();
  guards.add(guard);
  return () => { guards.delete(guard); };
}
export function confirmWorkspaceNavigation(): boolean {
  for (const guard of guards) if (!guard()) return false;
  return true;
}
