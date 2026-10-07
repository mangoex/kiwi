import type { AdminSession } from './adminSession';
let canonicalSession: AdminSession | null = null;
export const publishAdminSession = (session: AdminSession | null) => { canonicalSession = session; };

export interface SessionUser {
  id?: string;
  assigned_branch_id?: string;
  is_superadmin?: boolean;
  permissions?: string[];
  roles?: string[];
}

export const getSessionUser = (): SessionUser => {
  return canonicalSession ? {
    ...canonicalSession.user,
    assigned_branch_id: canonicalSession.scope.assigned_branch_id || undefined,
    permissions: Object.keys(canonicalSession.admin_capabilities).filter(code => canonicalSession!.admin_capabilities[code]),
    roles: canonicalSession.roles.map(role => role.name),
  } : {};
};

export const canSelectAnyBranch = (_user?: SessionUser) => canonicalSession?.scope.level === 'organization';

export const setCanonicalBranchId = (branchId: string) => {
  if (!branchId) {
    localStorage.removeItem('admin_branch_id');
    return;
  }
  localStorage.setItem('admin_branch_id', branchId);
};

export const resolveBranchId = (_user?: SessionUser) => canonicalSession?.active_branch.id || '';
