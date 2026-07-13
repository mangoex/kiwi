import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { fetchApi, ApiError } from '@restaurantos/api-client';

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
  allowed_branch_ids: string[];
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
  business_unit: SessionBusinessUnit;
  legal_entity: { id: string; name: string };
  warehouse: { id: string; name: string } | null;
}

export interface PosSession {
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
}

// ---------------------------------------------------------------------------
// Canonical session provider (BA-002)
// ---------------------------------------------------------------------------

type SessionState =
  | { status: 'loading' }
  | { status: 'ok'; session: PosSession }
  | { status: 'error'; message: string; statusCode: number };

interface SessionContextValue {
  state: SessionState;
  session: PosSession | null;
  hasPermission: (code: string) => boolean;
  reload: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

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

export function PosSessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: 'loading' });

  const loadSession = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const session = await fetchApi<PosSession>('/auth/session');
      setState({ status: 'ok', session });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          localStorage.removeItem('auth_token');
          sessionStorage.removeItem('auth_token');
          redirectToLogin();
          return;
        }
        setState({
          status: 'error',
          message:
            err.status === 403
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
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  const session = state.status === 'ok' ? state.session : null;

  const hasPermission = useCallback(
    (code: string) => {
      if (state.status !== 'ok') return false;
      return state.session.permissions.includes(code);
    },
    [state],
  );

  const value: SessionContextValue = { state, session, hasPermission, reload: loadSession };
  return React.createElement(SessionContext.Provider, { value }, children);
}

export function usePosSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error('usePosSession must be used within a PosSessionProvider');
  }
  return ctx;
}

// ---------------------------------------------------------------------------
// Legacy helpers (still used by non-BA-002 components).
// These do NOT determine authority for BA-002 screens; the canonical session
// obtained via /auth/session is the single source of truth.
// ---------------------------------------------------------------------------

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

export const isAdministrativeUser = (user: PosSessionUser = getPosSessionUser()): boolean =>
  Boolean(
    user.is_superadmin ||
      user.permissions?.includes('admin.manage') ||
      user.permissions?.includes('branch.admin.access') ||
      user.roles?.includes('Administrador corporativo'),
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
  const branchId =
    localStorage.getItem('admin_branch_id') ||
    localStorage.getItem('pos_branch_id') ||
    user.assigned_branch_id ||
    '';
  if (branchId) setPosBranchId(branchId);
  return branchId;
};
