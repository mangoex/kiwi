import React, { useState } from 'react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { ShoppingCart, Users, Clock, Settings, LogOut, ChevronLeft, ChevronRight, ShieldCheck, Timer, Wallet, Leaf, UserRound, MapPin } from 'lucide-react';
import { usePosSession, clearPosSession } from '../session';
import AttendanceClockModal from '../features/attendance/AttendanceClockModal';

const PosLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(() => localStorage.getItem('pos_sidebar_collapsed') === 'true');
  const [isAttendanceOpen, setIsAttendanceOpen] = useState(false);
  const { session, hasPermission } = usePosSession();

  const navItems = [
    { path: '/pos', label: 'Punto de Venta', icon: <ShoppingCart size={22} /> },
    { path: '/customers', label: 'Clientes', icon: <Users size={22} /> },
    { path: '/history', label: 'Pedidos', icon: <Clock size={22} /> },
    { path: '__attendance__', label: 'Checador', icon: <Timer size={22} /> },
    ...(hasPermission('cash.movement.read') || hasPermission('cash.movement.withdraw') || hasPermission('cash.movement.deposit') ? [{ path: '/cash-movements', label: 'Movimientos de caja', icon: <Wallet size={22} /> }] : []),
    ...(hasPermission('branch.admin.access')
      || hasPermission('admin.manage')
      || hasPermission('purchases.read')
      || hasPermission('inventory.read')
      || hasPermission('inventory.waste')
      || hasPermission('recipes.manage')
      || hasPermission('reports.sales.read')
      || hasPermission('reports.ingredient_sales.read')
      || hasPermission('cash.user_cut.read')
      ? [{ path: '/administration', label: 'Administración', icon: <ShieldCheck size={22} /> }]
      : []),
  ];

  const isPointOfSale = location.pathname === '/' || location.pathname === '/pos' || location.pathname.startsWith('/pos/orders/');
  const canOpenAdministration = navItems.some((item) => item.path === '/administration');
  const quickActions = [
    { path: '/customers', label: 'Clientes', detail: 'Buscar y registrar', icon: <Users size={21} /> },
    { path: '/history', label: 'Pedidos', detail: 'Consultar y editar', icon: <Clock size={21} /> },
    { path: '/settings', label: 'Caja', detail: 'Turno y terminal', icon: <Settings size={21} /> },
    { path: '__attendance__', label: 'Checador', detail: 'Entrada y salida', icon: <Timer size={21} /> },
    ...(canOpenAdministration
      ? [{ path: '/administration', label: 'Administración', detail: 'Operación de sucursal', icon: <ShieldCheck size={21} /> }]
      : []),
  ];

  const setSidebarCollapsed = (collapsed: boolean) => {
    localStorage.setItem('pos_sidebar_collapsed', String(collapsed));
    setIsCollapsed(collapsed);
  };

  const openDestination = (path: string) => {
    if (path === '__attendance__') {
      setIsAttendanceOpen(true);
      return;
    }
    navigate(path);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: '#f8fafc' }}>
      {/* Light POS Sidebar */}
      <div style={{ 
        width: isCollapsed ? '80px' : '260px', 
        transition: 'width 0.3s', 
        display: 'flex', 
        flexDirection: 'column', 
        background: '#fff', 
        borderRight: '1px solid #e2e8f0',
        zIndex: 10
      }}>
        <div style={{ display: 'flex', justifyContent: isCollapsed ? 'center' : 'space-between', alignItems: 'center', padding: isCollapsed ? '24px 0' : '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '1.5rem', fontWeight: 800, color: '#10b981' }}>
            <Leaf size={25} aria-hidden="true" />
            {!isCollapsed && <span>Kiwi</span>}
          </div>
          <button 
            onClick={() => setSidebarCollapsed(true)}
            aria-label="Comprimir menú lateral"
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', padding: 0, display: isCollapsed ? 'none' : 'block' }}
          >
            <ChevronLeft size={20} />
          </button>
        </div>
        
        {isCollapsed && (
          <div style={{ textAlign: 'center', paddingBottom: '16px' }}>
            <button 
              onClick={() => setSidebarCollapsed(false)}
              aria-label="Expandir menú lateral"
              style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', padding: 0 }}
            >
              <ChevronRight size={20} />
            </button>
          </div>
        )}

        <div style={{ flex: 1, overflowY: 'auto', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {navItems.map(item => {
            const isActive = item.path === '/pos'
              ? (location.pathname === '/' || location.pathname === '/pos' || location.pathname.startsWith('/pos/'))
              : (location.pathname === item.path || location.pathname.startsWith(`${item.path}/`));
            return (
              <button
                type="button"
                aria-current={isActive ? 'page' : undefined}
                key={item.path} 
                onClick={() => openDestination(item.path)}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '16px',
                  justifyContent: isCollapsed ? 'center' : 'flex-start', 
                  padding: isCollapsed ? '12px 0' : '12px 24px',
                  cursor: 'pointer',
                  color: isActive ? '#10b981' : '#64748b',
                  background: isActive ? '#ecfdf5' : 'transparent',
                  border: 'none',
                  borderRight: isActive ? '3px solid #10b981' : '3px solid transparent',
                  width: '100%',
                  fontSize: 'inherit',
                  textAlign: 'left',
                  fontWeight: isActive ? 600 : 500,
                  transition: 'all 0.2s'
                }}
                title={isCollapsed ? item.label : undefined}
                onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = '#f1f5f9'; }}
                onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
              >
                {item.icon}
                {!isCollapsed && <span>{item.label}</span>}
              </button>
            );
          })}
        </div>
        
        {/* User profile snippet */}
        {!isCollapsed && session?.user && (
          <div style={{ padding: '12px 20px', borderTop: '1px solid #e2e8f0', background: '#f8fafc', fontSize: '0.8125rem' }}>
            <div style={{ fontWeight: 600, color: '#0f172a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              <UserRound size={15} aria-hidden="true" style={{ verticalAlign: '-2px', marginRight: 5 }} />
              {session.user.display_name}
            </div>
            <div style={{ color: '#16a34a', fontWeight: 500, marginTop: 2, fontSize: '0.75rem' }}>
              <MapPin size={14} aria-hidden="true" style={{ verticalAlign: '-2px', marginRight: 4 }} />
              {session.roles?.[0]?.name || 'Operador'} · {session.active_branch?.name || 'Sucursal'}
            </div>
          </div>
        )}

        {/* Configuración & Logout at the bottom */}
        <div style={{ padding: '12px 0', borderTop: '1px solid #e2e8f0' }}>
           <button
             type="button"
             aria-current={location.pathname === '/settings' ? 'page' : undefined}
             onClick={() => navigate('/settings')}
             style={{ 
               display: 'flex', alignItems: 'center', gap: '16px', justifyContent: isCollapsed ? 'center' : 'flex-start', 
               padding: isCollapsed ? '12px 0' : '12px 24px', cursor: 'pointer', color: location.pathname === '/settings' ? '#10b981' : '#64748b',
               background: location.pathname === '/settings' ? '#ecfdf5' : 'transparent',
               fontWeight: location.pathname === '/settings' ? 600 : 500, border: 'none', width: '100%', fontSize: 'inherit', textAlign: 'left',
             }}
             title={isCollapsed ? 'Configuración' : undefined}
             onMouseEnter={(e) => { if (location.pathname !== '/settings') e.currentTarget.style.background = '#f1f5f9'; }}
             onMouseLeave={(e) => { if (location.pathname !== '/settings') e.currentTarget.style.background = 'transparent'; }}
           >
             <Settings size={22} />
             {!isCollapsed && <span>Configuración</span>}
           </button>
           <button
              type="button"
              onClick={() => {
                clearPosSession();
                window.location.href = '/admin/login';
              }}
              style={{ 
                display: 'flex', alignItems: 'center', gap: '16px', justifyContent: isCollapsed ? 'center' : 'flex-start', 
                padding: isCollapsed ? '12px 0' : '12px 24px', cursor: 'pointer', color: '#ef4444', fontWeight: 500, border: 'none', width: '100%', fontSize: 'inherit', textAlign: 'left'
              }}
              title={isCollapsed ? 'Cerrar sesión' : undefined}
              onMouseEnter={(e) => e.currentTarget.style.background = '#fef2f2'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <LogOut size={22} />
              {!isCollapsed && <span>Cerrar sesión</span>}
            </button>
        </div>
      </div>

      <main className="pos-main-shell">
        {isPointOfSale && (
          <nav className="pos-quick-actions" aria-label="Accesos frecuentes">
            <span className="pos-quick-actions-label">Accesos frecuentes</span>
            {quickActions.map((action) => (
              <button key={action.path} type="button" onClick={() => openDestination(action.path)}>
                <span className="pos-quick-actions-icon">{action.icon}</span>
                <span>
                  <strong>{action.label}</strong>
                  <small>{action.detail}</small>
                </span>
              </button>
            ))}
          </nav>
        )}
        <div className="pos-layout-content"><Outlet /></div>
      </main>
      <AttendanceClockModal isOpen={isAttendanceOpen} onClose={() => setIsAttendanceOpen(false)} />
    </div>
  );
};

export default PosLayout;
