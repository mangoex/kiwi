/** Server-projected capabilities; absent projection fails closed, including old offline bundles. */
export interface AdministrativeSession {
  user?: {id:string};
  admin_capabilities?: Record<string, boolean>;
  active_branch: { id: string } | null;
  scope: { allowed_branch_ids: string[]; level: string };
}
export const hasAdminCapability = (session: AdministrativeSession | null, code: string): boolean =>
  session?.admin_capabilities?.[code] === true;
const routeRules: Record<string, string[][]> = {
  '/': [['dashboard.read']],
  '/products': [['catalog.manage'], ['recipes.manage'], ['branch.admin.access']],
  '/variations': [['catalog.manage'], ['branch.admin.access', 'catalog.branch.manage']],
  '/ingredient-extras': [['catalog.manage'], ['branch.admin.access', 'catalog.branch.manage']],
  '/recipes': [['recipes.manage']], '/recipes/bulk': [['recipes.manage']],
  '/categories': [['catalog.manage']], '/category-options': [['catalog.manage']],
  '/category-priorities': [['catalog.manage']], '/warehouses': [['catalog.manage']],
  '/inventory/items': [['inventory.read']], '/inventory/units': [['inventory.read']],
  '/inventory/thresholds': [['catalog.manage']], '/production': [['production.manage']],
  '/inventory/waste': [['inventory.read']], '/inventory/transfers': [['inventory.read']],
  '/inventory/counts': [['inventory.count.capture'], ['inventory.count.review']],
  '/purchases': [['purchases.read']], '/suppliers': [['purchases.read']],
  '/purchase-presentations': [['purchases.read']],
  '/branches': [['admin.manage']], '/drivers': [['admin.manage']], '/integrations': [['admin.manage']],
  '/cash-concepts': [['cash.concept.manage']], '/reports': [['admin.manage']],
  '/analytics': [['dashboard.read']], '/users': [['admin.manage']], '/roles': [['admin.manage']],
  '/customers': [['orders.read']], '/imports': [['admin.manage']],
};
const hubRoutes: Record<string, string[]> = {
  '/catalog': ['/products','/recipes','/categories','/variations','/ingredient-extras','/category-priorities'],
  '/inventory': ['/inventory/items','/production','/inventory/waste','/inventory/transfers','/inventory/counts','/inventory/units','/warehouses','/inventory/thresholds'],
  '/purchasing': ['/purchases','/suppliers','/purchase-presentations'],
  '/branches-hub': ['/branches','/drivers','/integrations','/cash-concepts'],
  '/reports-hub': ['/reports','/analytics'], '/admin-access-hub': ['/users','/roles','/customers','/imports'],
};
export function canAccessAdminRoute(session: AdministrativeSession | null, path: string): boolean {
  if (!session?.active_branch || !session.scope.allowed_branch_ids.includes(session.active_branch.id)) return false;
  if (hubRoutes[path]) return hubRoutes[path].some(route => canAccessAdminRoute(session, route));
  return (routeRules[path] || []).some(codes => codes.every(code => hasAdminCapability(session, code)));
}
export const adminModules: Record<string, string> = {
  products:'/products', variations:'/variations', 'ingredient-extras':'/ingredient-extras',
  inventory:'/inventory', suppliers:'/suppliers', purchases:'/purchases', production:'/production',
  waste:'/inventory/waste', transfers:'/inventory/transfers', counts:'/inventory/counts',
};
export function canOpenPosAdministration(session: AdministrativeSession | null): boolean {
  return Object.values(adminModules).some(path => canAccessAdminRoute(session, path))
    || ['branch.staff.read','reports.sales.read','reports.ingredient_sales.read','reports.expenses.read']
      .some(code => hasAdminCapability(session, code));
}
export function adminDestination(session: AdministrativeSession | null, module: string): string | null {
  const path = adminModules[module];
  return path && canAccessAdminRoute(session, path)
    ? `/admin${path}?branch_id=${encodeURIComponent(session!.active_branch!.id)}&from=pos` : null;
}
export const POS_ADMIN_RETURN_CONTEXT = 'pos_admin_return_context_v1';
export interface PosAdminReturnContext {userId:string;branchId:string}
export function posReturnDestination(session: AdministrativeSession | null, entry?:PosAdminReturnContext | null): string | null {
  if (!session) return null;
  // This is a requested navigation context. POS revalidates the branch and pos.operate itself.
  const original = entry?.userId === session.user?.id && session.scope.allowed_branch_ids.includes(entry!.branchId)
    ? entry!.branchId : null;
  const branch = original || (hasAdminCapability(session,'pos.operate') ? session.active_branch?.id : null);
  return branch && session.scope.allowed_branch_ids.includes(branch)
    ? `/pos/?branch_id=${encodeURIComponent(branch)}` : null;
}
