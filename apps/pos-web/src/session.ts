export interface PosSessionUser {
  assigned_branch_id?: string;
  is_superadmin?: boolean;
  permissions?: string[];
  roles?: string[];
}

export const getPosSessionUser = (): PosSessionUser => {
  try {
    return JSON.parse(localStorage.getItem('user') || '{}') as PosSessionUser;
  } catch {
    return {};
  }
};

export const isAdministrativeUser = (user: PosSessionUser = getPosSessionUser()) => Boolean(
  user.is_superadmin
  || user.permissions?.includes('admin.manage')
  || user.roles?.includes('Administrador corporativo')
);

export const setPosBranchId = (branchId: string) => {
  if (!branchId) return;
  localStorage.setItem('pos_branch_id', branchId);
  localStorage.setItem('admin_branch_id', branchId);
};

export const resolvePosBranchId = (user: PosSessionUser = getPosSessionUser()) => {
  if (user.assigned_branch_id && !isAdministrativeUser(user)) {
    setPosBranchId(user.assigned_branch_id);
    return user.assigned_branch_id;
  }
  const branchId = localStorage.getItem('admin_branch_id')
    || localStorage.getItem('pos_branch_id')
    || user.assigned_branch_id
    || '';
  if (branchId) setPosBranchId(branchId);
  return branchId;
};
