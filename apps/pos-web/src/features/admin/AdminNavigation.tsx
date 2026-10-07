import { useEffect, type ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { adminDestination, canOpenPosAdministration, POS_ADMIN_RETURN_CONTEXT } from '@restaurantos/api-client';
import { confirmWorkspaceNavigation } from '@restaurantos/ui';
import { usePosSession } from '../../session';

export function AdministrationAccess({children}:{children:ReactNode}) {
  const {session} = usePosSession();
  return canOpenPosAdministration(session) ? <>{children}</> : <Navigate to="/pos" replace />;
}
export function AdminModuleRedirect({module}:{module:string}) {
  const {session} = usePosSession();
  const target = adminDestination(session,module);
  useEffect(()=>{
    if (target && navigator.onLine && confirmWorkspaceNavigation()) {
      sessionStorage.setItem(POS_ADMIN_RETURN_CONTEXT, JSON.stringify({userId:session!.user.id,branchId:session!.active_branch!.id}));
      window.location.replace(target);
    }
  },[target]);
  if (!target) return <p role="alert">Tu cuenta no tiene acceso a esta función administrativa.</p>;
  return <section style={{padding:32}}><p role="status">{navigator.onLine ? 'Abriendo administración…' : 'La administración requiere conexión. Tu captura sigue guardada en caja.'}</p>
    <a href="/pos/">Volver a caja</a></section>;
}
