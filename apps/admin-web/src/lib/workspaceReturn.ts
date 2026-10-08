export const ADMIN_WORKSPACE_RETURN_AFTER_LOGIN = 'admin_workspace_return_after_login';

export function rememberWorkspaceReturn(path: string): void {
  sessionStorage.setItem(ADMIN_WORKSPACE_RETURN_AFTER_LOGIN, path);
}

export function consumeWorkspaceReturn(): string | null {
  const path = sessionStorage.getItem(ADMIN_WORKSPACE_RETURN_AFTER_LOGIN);
  sessionStorage.removeItem(ADMIN_WORKSPACE_RETURN_AFTER_LOGIN);
  return path?.startsWith('/') && !path.startsWith('//') ? path : null;
}

export function clearWorkspaceReturn(path: string): void {
  if (sessionStorage.getItem(ADMIN_WORKSPACE_RETURN_AFTER_LOGIN) === path) {
    sessionStorage.removeItem(ADMIN_WORKSPACE_RETURN_AFTER_LOGIN);
  }
}
