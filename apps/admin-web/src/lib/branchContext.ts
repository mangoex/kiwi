export interface SessionUser {
  assigned_branch_id?: string;
  is_superadmin?: boolean;
  permissions?: string[];
  roles?: string[];
}

export const getSessionUser = (): SessionUser => {
  try {
    return JSON.parse(localStorage.getItem('user') || '{}') as SessionUser;
  } catch {
    return {};
  }
};

export const canSelectAnyBranch = (user: SessionUser = getSessionUser()) => Boolean(
  user.is_superadmin
  || user.permissions?.includes('admin.manage')
  || user.roles?.includes('Administrador corporativo')
);

export const setCanonicalBranchId = (branchId: string) => {
  if (!branchId) {
    localStorage.removeItem('admin_branch_id');
    localStorage.removeItem('pos_branch_id');
    return;
  }
  localStorage.setItem('admin_branch_id', branchId);
  localStorage.setItem('pos_branch_id', branchId);
};

export const resolveBranchId = (user: SessionUser = getSessionUser()) => {
  if (user.assigned_branch_id && !canSelectAnyBranch(user)) {
    setCanonicalBranchId(user.assigned_branch_id);
    return user.assigned_branch_id;
  }
  return localStorage.getItem('admin_branch_id')
    || localStorage.getItem('pos_branch_id')
    || user.assigned_branch_id
    || '';
};
