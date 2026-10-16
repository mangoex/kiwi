import { confirmWorkspaceNavigation } from '@restaurantos/ui';
import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import {
  fetchApi,
  fetchOptionalCentralSession,
  ApiError,
  clearOfflineOrderGrant,
  clearCashierLocalCapture,
  loadOperationalOrderConfig,
  operationalOrderRequest,
  beginBranchWorkspaceRequest,
  isCurrentBranchWorkspaceRequest,
  ensureBranchWorkspace,
  installBranchWorkspace,
  hydrateBranchWorkspace,
  clearBranchWorkspace,
  branchSelectionIntent,
  clearBranchSelectionIntent,
  readBranchSelectionIntent,
  type BranchWorkspaceProfile,
} from '@restaurantos/api-client';

// ---------------------------------------------------------------------------
// Canonical session types (BA-002)
// ---------------------------------------------------------------------------

export interface SessionRole {
  id: string;
  name: string;
  scope: string;
  branch_id: string | null;
}

export interface SessionScope {
  level: 'organization' | 'branch';
  assigned_branch_id: string | null;
  home_branch_id: string | null;
  allowed_branch_ids: string[];
  can_select_branch: boolean;
  branch_selection_block_reason?: 'single_branch' | 'rollout_disabled' | 'permission_denied' | null;
  authorization_version: number;
}

export interface PosModuleAvailability {
  uber_eats: boolean;
  didi_food: boolean;
  rappi: boolean;
  invoicing: boolean;
}

export interface SessionBusinessUnit {
  id: string;
  name: string;
  code: string;
  unit_type: string;
}

export interface SessionActiveBranch {
  id: string;
  name: string;
  code: string;
  timezone: string;
  status: string;
  pos_catalog_visuals_enabled: boolean;
  business_unit: SessionBusinessUnit;
  legal_entity: { id: string; name: string };
  warehouse: { id: string; name: string } | null;
}

export interface PosSession extends BranchWorkspaceProfile {
  admin_capabilities?: Record<string, boolean>;
  user: {
    id: string;
    email: string;
    display_name: string;
    status: string;
  };
  roles: SessionRole[];
  permissions: string[];
  scope: SessionScope;
  active_branch: SessionActiveBranch | null;
  allowed_branches: { id: string; name: string; code: string; status: string }[];
  pos_modules: PosModuleAvailability;
}

// ---------------------------------------------------------------------------
// Canonical session provider (BA-002)
// ---------------------------------------------------------------------------

type SessionState =
  | { status: 'loading' }
  | { status: 'ok'; session: PosSession; validating?:boolean; notice?:string }
  | { status: 'error'; message: string; statusCode: number };

interface SessionContextValue {
  state: SessionState;
  session: PosSession | null;
  hasPermission: (code: string) => boolean;
  reload: () => void;
  applyCatalogAppearance: (branchId: string, visualsEnabled: boolean) => void;
  selectBranch: (branchId: string) => Promise<boolean>;
}

const SessionContext = createContext<SessionContextValue | null>(null);
const CENTRAL_APPEARANCE_TIMEOUT_MS = 1500;
const currentCredential = () => localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');

function redirectToLogin() {
  const isDev =
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    (window.location.port !== '' &&
      window.location.port !== '80' &&
      window.location.port !== '443');
  const loginUrl = isDev ? 'http://localhost:3002/admin/login' : '/admin/login';
  window.location.href = loginUrl;
}

export function setPosBranchId(branchId: string) {
  if (!branchId) return;
  localStorage.setItem('pos_branch_id', branchId);
  localStorage.setItem('admin_branch_id', branchId);
}

/**
 * Clear all POS session artifacts. Called on logout or 401.
 */
export function clearPosSession() {
  clearBranchWorkspace();
  clearCashierLocalCapture();
  clearOfflineOrderGrant();
  localStorage.removeItem('pos_branch_id');
  localStorage.removeItem('admin_branch_id');
  localStorage.removeItem('auth_token');
  localStorage.removeItem('user');
  sessionStorage.removeItem('auth_token');
  sessionStorage.removeItem('pos_pending_checkout_v1');
    sessionStorage.removeItem('pos_cashier_order_action_v1');
  sessionStorage.removeItem('pos_cashier_payment_v1');
  sessionStorage.removeItem('pos_offline_cash_grant');
  sessionStorage.removeItem('pos_offline_cash_grant_expires_at');
  sessionStorage.removeItem('pos_offline_cash_grant_branch_id');
  sessionStorage.removeItem('pos_offline_cash_grant_source_device_id');
  sessionStorage.removeItem('pos_offline_cash_grant_gateway_url');
}

/**
 * Returns the branch_id previously validated and written by PosSessionProvider.
 * Does NOT read localStorage.user, assigned_branch_id, or role names.
 * If no validated branch_id exists, returns empty string.
 */
export function resolvePosBranchId(): string {
  return localStorage.getItem('pos_branch_id') || '';
}

async function fetchCanonicalSession(signal?: AbortSignal): Promise<PosSession> {
  const endpoint = '/auth/session';
  const operationalConfig = loadOperationalOrderConfig();
  if (operationalConfig) {
    const gatewaySession = await operationalOrderRequest<PosSession>(operationalConfig, endpoint, {signal});
    if (gatewaySession.active_branch?.id !== operationalConfig.branchId) {
      throw new ApiError(403,'offline_order_branch_mismatch','La sesión local no corresponde a la sucursal de este dispositivo.');
    }
    if (!navigator.onLine) return {...gatewaySession, admin_capabilities:undefined};
    const centralController = new AbortController();
    const abortCentral = () => centralController.abort();
    signal?.addEventListener('abort', abortCentral, {once:true});
    const centralTimeout = window.setTimeout(
      () => centralController.abort(),
      CENTRAL_APPEARANCE_TIMEOUT_MS,
    );
    try {
      const centralSession = await fetchOptionalCentralSession<PosSession>(centralController.signal);
      if (
        gatewaySession.active_branch?.id
        && centralSession?.active_branch?.id === gatewaySession.active_branch.id
        && centralSession.user.id === gatewaySession.user.id
      ) {
        return {
          ...gatewaySession,
          admin_capabilities: centralSession.admin_capabilities,
          active_branch: {
            ...gatewaySession.active_branch,
            pos_catalog_visuals_enabled:
              centralSession.active_branch.pos_catalog_visuals_enabled !== false,
          },
        };
      }
    } catch {
      // Offline continuity keeps the last signed bundle value until renewal.
    } finally {
      window.clearTimeout(centralTimeout);
      signal?.removeEventListener('abort', abortCentral);
    }
    return {...gatewaySession, admin_capabilities:undefined};
  }
  return fetchApi<PosSession>(endpoint, {signal});
}

export function PosSessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: 'loading' });
  const request = useRef<AbortController | null>(null);
  const confirmedCredential = useRef<string | null>(null);

  const applySession = useCallback((session: PosSession) => {
    // Apply the canonical active_branch before publishing the session,
    // so any stale local branch_id is replaced unconditionally.
    if (session.active_branch?.id) {
      setPosBranchId(session.active_branch.id);
    } else {
      localStorage.removeItem('pos_branch_id');
      localStorage.removeItem('admin_branch_id');
    }
    setState({ status: 'ok', session });
  }, []);

  const loadSession = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    const credential = currentCredential();
    if (loadOperationalOrderConfig()) clearBranchWorkspace();
    const ticket = beginBranchWorkspaceRequest(credential || '');
    confirmedCredential.current = null;
    setState({ status: 'loading' });
    try {
      if (!credential) throw new ApiError(401, 'actor_required', 'Inicia sesión para continuar.');
      let profile = await fetchCanonicalSession(controller.signal);
      if (controller.signal.aborted || !isCurrentBranchWorkspaceRequest(ticket, currentCredential())) return;
      const pending = !loadOperationalOrderConfig() && readBranchSelectionIntent(profile);
      if (pending) {
        const recovered = await fetchApi<PosSession>('/auth/branch-selections', {
          method:'POST', signal:controller.signal, headers:{'Idempotency-Key':pending.idempotencyKey},
          body:JSON.stringify({target_branch_id:pending.targetBranchId,expected_authorization_version:pending.authorizationVersion}),
        });
        if (recovered.user.id !== profile.user.id || recovered.organization_id !== profile.organization_id
          || recovered.active_branch?.id !== pending.targetBranchId
          || !installBranchWorkspace(recovered,ticket,currentCredential())) {
          throw new ApiError(409,'branch_context_mismatch','No se pudo confirmar el cambio pendiente de sucursal.');
        }
        clearBranchSelectionIntent(profile);
        profile = recovered;
      }
      const session = loadOperationalOrderConfig() ? profile : await ensureBranchWorkspace(
        profile, ticket, currentCredential,
        body => fetchApi<PosSession>('/auth/branch-context-reissues', {
          method: 'POST', signal: controller.signal,
          headers: {'Idempotency-Key': crypto.randomUUID()}, body: JSON.stringify(body),
        }),
      );
      if (controller.signal.aborted || !isCurrentBranchWorkspaceRequest(ticket, currentCredential())) return;
      confirmedCredential.current = credential;
      applySession({...session, branch_workspace_context:null});
    } catch (err) {
      if (controller.signal.aborted || request.current !== controller
        || (currentCredential() && credential !== currentCredential())) return;
      if (err instanceof ApiError) {
        if (err.status === 401) {
          clearPosSession();
          redirectToLogin();
          return;
        }
        setState({
          status: 'error',
          message:
            err.code === 'branch_switch_uncertain_command'
              ? 'Recupera las operaciones pendientes para continuar con tu sucursal.'
              : err.status === 403
              ? 'Tu cuenta no tiene acceso a esta operación.'
              : err.message,
          statusCode: err.status,
        });
        return;
      }
      setState({
        status: 'error',
        message: 'No se pudo conectar con el servidor.',
        statusCode: 0,
      });
    }
  }, [applySession]);

  const selectBranch = useCallback(
    async (branchId: string) => {
      if (!confirmWorkspaceNavigation()) return false;
      if (loadOperationalOrderConfig()) {
        throw new ApiError(409, 'offline_branch_fixed', 'La operación local permanece en su sucursal autorizada.');
      }
      const credential = currentCredential();
      if (!credential || credential !== confirmedCredential.current) {
        throw new ApiError(403, 'session_changed', 'La sesión cambió. Vuelve a validar antes de seleccionar.');
      }
      if (state.status !== 'ok' || !state.session.scope.can_select_branch) {
        throw new ApiError(403, 'permission_denied', 'No puedes cambiar de sucursal.');
      }
      if (!state.session.permissions.includes('pos.branch.select')) {
        throw new ApiError(403, 'permission_denied', 'No tienes permiso para cambiar de sucursal.');
      }
      if (!state.session.scope.allowed_branch_ids.includes(branchId)) {
        throw new ApiError(403, 'permission_denied', 'La sucursal no está autorizada.');
      }

      const intent = branchSelectionIntent(state.session, branchId);
      request.current?.abort();
      const controller = new AbortController(); request.current = controller;
      const ticket = beginBranchWorkspaceRequest(credential);
      setState({...state,validating:true,notice:undefined});
      // The current canonical session stays active if validation fails.
      let nextSession: PosSession;
      try {
        nextSession = await fetchApi<PosSession>('/auth/branch-selections', {
          method: 'POST',
          signal: controller.signal,
          headers: { 'Idempotency-Key': intent.idempotencyKey },
          body: JSON.stringify({
            target_branch_id: intent.targetBranchId,
            expected_authorization_version: intent.authorizationVersion,
          }),
        });
      } catch (error) {
        if (error instanceof ApiError && error.status === 401 && !currentCredential()) {
          clearPosSession();
          redirectToLogin();
        }
        if (error instanceof ApiError && error.status < 500) {
          clearBranchSelectionIntent(state.session);
        }
        if (request.current === controller && credential === currentCredential()) {
          const blockers: Record<string, string> = {
            branch_switch_open_shift: 'No puedes cambiar de sucursal mientras tu turno está abierto. Continúa y ciérralo aquí.',
            branch_switch_uncertain_command: 'Recupera el resultado de las operaciones pendientes antes de cambiar de sucursal.',
            branch_switch_offline_grant: 'La autorización offline de esta sucursal sigue vigente. Espera su drenado antes de cambiar.',
            branch_switch_pending_reconciliation: 'Sincroniza las operaciones locales pendientes antes de cambiar de sucursal.',
          };
          if (error instanceof ApiError && blockers[error.code]
            && hydrateBranchWorkspace(state.session,ticket,currentCredential())) {
            setState({...state,validating:false,notice:blockers[error.code]});
          } else {
            setState({status:'error',message:'No se confirmó el cambio de sucursal. Reintenta para recuperar el mismo comando.',statusCode:error instanceof ApiError ? error.status : 0});
          }
        }
        throw error;
      }
      if (controller.signal.aborted || !isCurrentBranchWorkspaceRequest(ticket, currentCredential())
        || nextSession.user.id !== state.session.user.id
        || nextSession.organization_id !== state.session.organization_id
        || nextSession.active_branch?.id !== branchId
        || !installBranchWorkspace(nextSession, ticket, currentCredential())) {
        if (request.current === controller && credential === currentCredential()) {
          setState({status:'error',message:'La respuesta de selección ya no es vigente. Revalida la sesión.',statusCode:409});
        }
        throw new ApiError(
          409,
          'branch_context_mismatch',
          'El servidor no confirmó la sucursal seleccionada.',
        );
      }
      clearOfflineOrderGrant();
      clearBranchSelectionIntent(state.session);
      confirmedCredential.current = credential;
      nextSession = {...nextSession,branch_workspace_context:null};
      applySession(nextSession);
      return true;
    },
    [applySession, state],
  );

  useEffect(() => {
    void loadSession();
    return () => { request.current?.abort(); clearBranchWorkspace(); };
  }, [loadSession]);

  useEffect(() => {
    const revalidate = () => { void loadSession(); };
    const storage = (event: StorageEvent) => { if (event.key === 'auth_token') revalidate(); };
    window.addEventListener('focus', revalidate);
    window.addEventListener('storage', storage);
    return () => {
      window.removeEventListener('focus', revalidate);
      window.removeEventListener('storage', storage);
    };
  }, [loadSession]);

  const session = state.status === 'ok' ? state.session : null;

  const hasPermission = useCallback(
    (code: string) => {
      if (state.status !== 'ok') return false;
      return state.session.permissions.includes(code);
    },
    [state],
  );

  const applyCatalogAppearance = useCallback((branchId: string, visualsEnabled: boolean) => {
    setState((current) => {
      if (current.status !== 'ok' || current.session.active_branch?.id !== branchId) {
        return current;
      }
      return {
        ...current,
        session: {
          ...current.session,
          active_branch: {
            ...current.session.active_branch,
            pos_catalog_visuals_enabled: visualsEnabled,
          },
        },
      };
    });
  }, []);

  const value: SessionContextValue = {
    state,
    session,
    hasPermission,
    reload: () => void loadSession(),
    applyCatalogAppearance,
    selectBranch,
  };
  return React.createElement(SessionContext.Provider, { value }, children);
}

export function usePosSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error('usePosSession must be used within a PosSessionProvider');
  }
  return ctx;
}
