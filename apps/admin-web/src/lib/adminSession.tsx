import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { useLocation, useNavigate, Navigate } from 'react-router-dom';
import { ApiError, fetchApi, hasAdminCapability, canAccessAdminRoute, type AdministrativeSession } from '@restaurantos/api-client';
import { confirmWorkspaceNavigation, quarantineWorkspaceSnapshots } from '@restaurantos/ui';
import { useResetSessionQueries } from '../components/AdminQueryProvider';
import { publishAdminSession, setCanonicalBranchId } from './branchContext';

export interface AdminSession extends AdministrativeSession {
  organization_id?: string;
  user: { id: string; email: string; display_name: string; status: string };
  roles: { id: string; name: string; scope: string; branch_id: string | null }[];
  permissions: string[];
  scope: { level: 'branch' | 'organization'; allowed_branch_ids: string[]; assigned_branch_id: string | null };
  active_branch: { id: string; name: string; code: string };
  admin_capabilities: Record<string, boolean>;
  allowed_branches: {id:string;name:string;code:string;status:string}[];
}
const Context = createContext<{session:AdminSession; selectBranch:(id:string)=>Promise<void>} | null>(null);
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
    && JSON.stringify(previous.scope) === JSON.stringify(next.scope)
    && JSON.stringify(Object.entries(previous.admin_capabilities).sort())
      === JSON.stringify(Object.entries(next.admin_capabilities).sort());
}

export function AdminSessionProvider({children}:{children:ReactNode}) {
  const location = useLocation();
  const navigate = useNavigate();
  const resetQueries = useResetSessionQueries();
  const [state, setState] = useState<{session?:AdminSession; error?:string; routeKey?:string; validating?:boolean}>({});
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
    const routeKey = route.current;
    const requested = new URLSearchParams(window.location.search).get('branch_id')
      ?? confirmed.current?.active_branch.id ?? localStorage.getItem('admin_branch_id') ?? undefined;
    const previous = confirmed.current;
    const preserve = keepWorkspace && previous && credential === confirmedCredential.current
      && routeKey === confirmedRoute.current && requested === previous.active_branch.id;
    const discardContext = () => {
      publishAdminSession(null); quarantineWorkspaceSnapshots(); resetQueries(); revision.current++;
    };
    if (preserve) setState(current=>({...current,validating:true}));
    else {discardContext();setState({});}
    try {
      if (!navigator.onLine) throw new Error('La administración requiere conexión. Puedes volver al POS para continuar la operación local.');
      if (!credential) throw new ApiError(401, 'actor_required', 'Inicia sesión para continuar.');
      const session = await fetchApi<AdminSession>(`/auth/session${requested ? `?branch_id=${encodeURIComponent(requested)}` : ''}`, {signal:controller.signal});
      if (controller.signal.aborted || credential !== token() || routeKey !== route.current) return;
      if (!session.admin_capabilities || !Array.isArray(session.allowed_branches) || !session.active_branch || !session.scope.allowed_branch_ids.includes(session.active_branch.id)
        || (requested && session.active_branch.id !== requested)) {
        throw new Error('El servidor no confirmó la sucursal y las capacidades de esta sesión.');
      }
      if (preserve && !sameAdministrativeAuthority(previous,session)) discardContext();
      confirmed.current = session;
      confirmedCredential.current = credential; confirmedRoute.current = routeKey;
      setCanonicalBranchId(session.active_branch.id); publishAdminSession(session);
      setState({session,routeKey});
    } catch (error) {
      if (controller.signal.aborted || credential !== token()) return;
      if (preserve) discardContext();
      confirmed.current = null;
      confirmedCredential.current = null;
      setState({error:error instanceof Error ? error.message : 'No se pudo validar la sesión.'});
    }
  }, [resetQueries]);
  useEffect(() => {
    void load();
    return () => { request.current?.abort(); publishAdminSession(null); };
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
  const selectBranch = async (id:string) => {
    if (!confirmWorkspaceNavigation()) return;
    if (session.scope.level !== 'organization' || !session.scope.allowed_branch_ids.includes(id)) return;
    const query = new URLSearchParams(location.search); query.set('branch_id',id);
    navigate({pathname:location.pathname,search:query.toString()},{replace:true});
  };
  return <Context.Provider value={{session,selectBranch}}>
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
