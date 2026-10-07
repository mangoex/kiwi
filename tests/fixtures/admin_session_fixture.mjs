// Canonical server response for isolated browser tests of a corporate administrator.
export function corporateAdminSession(user, branchId, branches = [{ id: branchId, name: 'Sucursal QA', code: 'QA', status: 'active' }]) {
  const codes = ['pos.operate', 'dashboard.read', 'admin.manage', 'catalog.manage', 'recipes.manage',
    'branch.admin.access', 'catalog.branch.manage', 'branch.staff.read', 'purchases.read', 'purchases.manage',
    'production.manage', 'inventory.read', 'inventory.waste', 'inventory.transfer.send', 'inventory.transfer.receive',
    'inventory.count.capture', 'inventory.count.review', 'inventory.count.approve', 'cash.concept.manage',
    'orders.read', 'reports.sales.read', 'reports.ingredient_sales.read', 'reports.expenses.read'];
  return { user: { ...user, status: 'active' }, roles: [{ id: 'corporate-qa', name: 'Administrador corporativo', scope: 'organization', branch_id: null }],
    permissions: codes, admin_capabilities: Object.fromEntries(codes.map(code => [code, true])),
    scope: { level: 'organization', assigned_branch_id: branchId, allowed_branch_ids: branches.map(branch => branch.id) },
    active_branch: branches.find(branch => branch.id === branchId), allowed_branches: branches };
}
