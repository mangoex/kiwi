import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { useLocation, Navigate } from 'react-router-dom';
import { ApiError, fetchApi, hasAdminCapability, canAccessAdminRoute, type AdministrativeSession } from '@restaurantos/api-client';
import { beginBranchWorkspaceRequest, ensureBranchWorkspace, clearBranchWorkspace, type BranchWorkspaceProfile } from '@restaurantos/api-client';
import { quarantineWorkspaceSnapshots } from '@restaurantos/ui';
import { useResetSessionQueries } from '../components/AdminQueryProvider';
import { publishAdminSession, setCanonicalBranchId } from './branchContext';

export interface AdminSession extends AdministrativeSession, Omit<BranchWorkspaceProfile,'scope'|'active_branch'|'user'> {
  organization_id?: string;
  user: { id: string; email: string; display_name: string; status: string };
  roles: { id: string; name: string; scope: string; branch_id: string | null }[];
  permissions: string[];
  scope: { level: 'branch' | 'organization'; allowed_branch_ids: string[]; assigned_branch_id: string | null; authorization_version?:number };
  active_branch: { id: string; name: string; code: string; timezone: string };
  admin_capabilities: Record<string, boolean>;
  allowed_branches: {id:string;name:string;code:string;status:string}[];
}
export type ConfigurationScope =
  | {kind:'organization'; branch_id:null}
  | {kind:'branch'; branch_id:string};

interface AdminSessionContext {
  session: AdminSession;
  assertCurrentAuthority: () => void;
  configurationScope: ConfigurationScope;
  selectConfigurationScope: (scope: ConfigurationScope) => void;
  dashboardBranchId: string | null;
  selectDashboardBranch: (branchId: string | null) => void;
}

const Context = createContext<AdminSessionContext | null>(null);
export function useAdminSession() {
  const value = useContext(Context);
  if (!value) throw new Error('Admin requires a validated canonical session');
  return value;
}
export function useAdminPermission(code: string) {
  return hasAdminCapability(useAdminSession().session, code);
}
const token = () => localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
export function sameAdministrativeAuthority(previous:AdminSession, next:AdminSession): boolean {
  return previous.user.id === next.user.id
    && previous.organization_id === next.organization_id
    && previous.active_branch.id === next.active_branch.id
    && previous.branch_workspace_context_id === next.branch_workspace_context_id
    && JSON.stringify(previous.scope) === JSON.stringify(next.scope)
    && JSON.stringify(Object.entries(previous.admin_capabilities).sort())
      === JSON.stringify(Object.entries(next.admin_capabilities).sort());
}

export function AdminSessionProvider({children}:{children:ReactNode}) {
  const location = useLocation();
  const resetQueries = useResetSessionQueries();
  const [state, setState] = useState<{session?:AdminSession; error?:string; routeKey?:string; validating?:boolean}>({});
  const [configurationScope, setConfigurationScope] = useState<ConfigurationScope>({
    kind: 'organization', branch_id: null,
  });
  const [dashboardBranchId, setDashboardBranchId] = useState<string | null>(null);
  const route = useRef(location.key); route.current = location.key;
  const request = useRef<AbortController | null>(null);
  const confirmed = useRef<AdminSession | null>(null);
  const confirmedCredential = useRef<string | null>(null);
  const confirmedRoute = useRef('');
  const revision = useRef(0);
  const load = useCallback(async (keepWorkspace=false) => {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    const credential = token();
    const workspaceRequest = beginBranchWorkspaceRequest(credential || '');
    const routeKey = route.current;
    const requested = new URLSearchParams(window.location.search).get('branch_id')?.trim() || undefined;
    const previous = confirmed.current;
    const preserve = keepWorkspace && previous && credential === confirmedCredential.current
      && routeKey === confirmedRoute.current
      && (!requested || requested === previous.active_branch.id);
    const discardContext = () => {
      publishAdminSession(null); quarantineWorkspaceSnapshots(); resetQueries(); revision.current++;
    };
    if (preserve) setState(current=>({...current,validating:true}));
    else {discardContext();setState({});}
    try {
      if (!navigator.onLine) throw new Error('La administración requiere conexión. Puedes volver al POS para continuar la operación local.');
      if (!credential) throw new ApiError(401, 'actor_required', 'Inicia sesión para continuar.');
      let session = await fetchApi<AdminSession>('/auth/session', {signal:controller.signal});
      if (controller.signal.aborted || credential !== token() || routeKey !== route.current) return;
      if (!session.admin_capabilities || !Array.isArray(session.allowed_branches) || !session.active_branch || typeof session.active_branch.timezone !== 'string' || !session.active_branch.timezone.trim() || !session.scope.allowed_branch_ids.includes(session.active_branch.id)
        || (requested && session.active_branch.id !== requested)) {
        throw new Error('El servidor no confirmó la sucursal y las capacidades de esta sesión.');
      }
      const documentWorkspace = ['/purchases', '/expenses'].includes(location.pathname.replace(/\/+$/, '').toLowerCase())
        && ['purchases.manage', 'expenses.manage', 'expenses.cancel'].some(code => session.admin_capabilities[code]);
      if (documentWorkspace || ['pos.operate', 'invoicing.read', 'invoicing.issue', 'invoicing.cancel', 'invoicing.receipt.create']
        .some(code => session.admin_capabilities[code])) session = await ensureBranchWorkspace(session,workspaceRequest,token,
        body => fetchApi<AdminSession>('/auth/branch-context-reissues', {
          method:'POST',signal:controller.signal,headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify(body),
        }));
      else clearBranchWorkspace();
      if (controller.signal.aborted || credential !== token() || routeKey !== route.current) return;
      if (preserve && !sameAdministrativeAuthority(previous,session)) discardContext();
      confirmed.current = session;
      confirmedCredential.current = credential; confirmedRoute.current = routeKey;
      setCanonicalBranchId(session.active_branch.id); publishAdminSession(session);
      if (session.scope.level !== 'organization') {
        setConfigurationScope({kind:'branch',branch_id:session.active_branch.id});
        setDashboardBranchId(session.active_branch.id);
      } else if (!previous || previous.user.id !== session.user.id || previous.organization_id !== session.organization_id) {
        setConfigurationScope({kind:'organization',branch_id:null});
        setDashboardBranchId(null);
      } else {
        setConfigurationScope((current) => current.kind === 'branch'
          && !session.scope.allowed_branch_ids.includes(current.branch_id)
          ? {kind:'organization',branch_id:null}
          : current);
        setDashboardBranchId((current) => current
          && !session.scope.allowed_branch_ids.includes(current)
          ? null
          : current);
      }
      setState({session,routeKey});
    } catch (error) {
      if (controller.signal.aborted || credential !== token()) return;
      if (preserve) discardContext();
      confirmed.current = null;
      confirmedCredential.current = null;
      setState({error:error instanceof Error ? error.message : 'No se pudo validar la sesión.'});
    }
  }, [resetQueries, location.pathname]);
  useEffect(() => {
    void load();
    return () => { request.current?.abort(); clearBranchWorkspace(); publishAdminSession(null); };
  }, [load, location.key]);
  useEffect(() => {
    const revalidate = () => { void load(true); };
    const storage = (event:StorageEvent) => { if (event.key === 'auth_token') revalidate(); };
    window.addEventListener('focus', revalidate); window.addEventListener('online', revalidate);
    window.addEventListener('storage', storage);
    return () => { window.removeEventListener('focus', revalidate); window.removeEventListener('online', revalidate); window.removeEventListener('storage', storage); };
  }, [load]);
  if (!token()) return <Navigate to="/login" replace />;
  if (!state.session || state.routeKey !== location.key) return <main style={{padding:32}}><h1>Administración</h1>
    <p role={state.error ? 'alert' : 'status'}>{state.error || 'Validando sesión y sucursal…'}</p>
    {state.error && <><button onClick={() => { void load(); }}>Reintentar</button> <a href="/pos/">Volver al POS</a></>}
  </main>;
  const session = state.session;
  const assertCurrentAuthority = () => {
    if (!confirmedCredential.current || token() !== confirmedCredential.current
      || !confirmed.current || !sameAdministrativeAuthority(session, confirmed.current)) {
      throw new Error('La sesión cambió. Recupera la operación desde la cuenta original.');
    }
  };
  const selectConfigurationScope = (scope:ConfigurationScope) => {
    if (scope.kind === 'organization') {
      setConfigurationScope({kind:'organization',branch_id:null});
      return;
    }
    if (session.scope.level !== 'organization' || !session.scope.allowed_branch_ids.includes(scope.branch_id)) {
      throw new ApiError(403, 'permission_denied', 'La sucursal no está autorizada para configurar.');
    }
    setConfigurationScope(scope);
  };
  const selectDashboardBranch = (branchId:string | null) => {
    if (branchId === null) {
      if (session.scope.level !== 'organization') {
        throw new ApiError(403, 'permission_denied', 'Tu cuenta sólo puede consultar su sucursal asignada.');
      }
      setDashboardBranchId(null);
      return;
    }
    if (session.scope.level !== 'organization' || !session.scope.allowed_branch_ids.includes(branchId)) {
      throw new ApiError(403, 'permission_denied', 'La sucursal no está autorizada para el panel.');
    }
    setDashboardBranchId(branchId);
  };
  return <Context.Provider value={{session,assertCurrentAuthority,configurationScope,selectConfigurationScope,dashboardBranchId,selectDashboardBranch}}>
    {state.validating && <p role="status">Validando sesión y sucursal…</p>}
    <div key={`${session.user.id}:${session.active_branch.id}:${revision.current}`} inert={Boolean(state.validating)} aria-busy={Boolean(state.validating)}>{children}</div>
  </Context.Provider>;
}

export function AdminRouteGuard({children}:{children:ReactNode}) {
  const {session} = useAdminSession();
  const {pathname} = useLocation();
  if (!canAccessAdminRoute(session, pathname)) return <section role="alert" style={{padding:32}}>
    <h1>Acceso no autorizado</h1><p>Tu cuenta no tiene permiso para consultar esta función.</p>
  </section>;
  return <>{children}</>;
}
