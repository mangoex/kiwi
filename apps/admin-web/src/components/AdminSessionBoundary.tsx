import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { subscribeToUnauthorized } from '@restaurantos/api-client';
import { useResetSessionQueries } from './AdminQueryProvider';
import { quarantineWorkspaceSnapshots } from '@restaurantos/ui';

export function AdminSessionBoundary() {
  const navigate = useNavigate();
  const resetSessionQueries = useResetSessionQueries();

  useEffect(() => subscribeToUnauthorized(() => {
    quarantineWorkspaceSnapshots();
    resetSessionQueries();
    localStorage.removeItem('user');
    sessionStorage.removeItem('user');
    navigate('/login', { replace: true, state: { sessionExpired: true } });
  }), [navigate, resetSessionQueries]);

  return null;
}
