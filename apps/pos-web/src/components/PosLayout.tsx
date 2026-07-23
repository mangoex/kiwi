import React, { useState } from 'react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { ShoppingCart, Users, Clock, Settings, LogOut, ChevronLeft, ChevronRight, ShieldCheck } from 'lucide-react';
import { usePosSession, clearPosSession } from '../session';

const PosLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { hasPermission } = usePosSession();

  const navItems = [
    { path: '/pos', label: 'Punto de Venta', icon: <ShoppingCart size={22} /> },
    { path: '/customers', label: 'Clientes', icon: <Users size={22} /> },
    { path: '/history', label: 'Pedidos', icon: <Clock size={22} /> },
    ...(hasPermission('branch.admin.access') ? [{ path: '/administration', label: 'Administración', icon: <ShieldCheck size={22} /> }] : []),
  ];

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
            <span>🥝</span>
            {!isCollapsed && <span>Kiwi</span>}
          </div>
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', padding: 0, display: isCollapsed ? 'none' : 'block' }}
          >
            <ChevronLeft size={20} />
          </button>
        </div>
        
        {isCollapsed && (
          <div style={{ textAlign: 'center', paddingBottom: '16px' }}>
            <button 
              onClick={() => setIsCollapsed(false)}
              style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', padding: 0 }}
            >
              <ChevronRight size={20} />
            </button>
          </div>
        )}

        <div style={{ flex: 1, overflowY: 'auto', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {navItems.map(item => {
            const isActive = location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
            return (
              <div 
                key={item.path} 
                onClick={() => navigate(item.path)}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '16px',
                  justifyContent: isCollapsed ? 'center' : 'flex-start', 
                  padding: isCollapsed ? '12px 0' : '12px 24px',
                  cursor: 'pointer',
                  color: isActive ? '#10b981' : '#64748b',
                  background: isActive ? '#ecfdf5' : 'transparent',
                  borderRight: isActive ? '3px solid #10b981' : '3px solid transparent',
                  fontWeight: isActive ? 600 : 500,
                  transition: 'all 0.2s'
                }}
                title={isCollapsed ? item.label : undefined}
                onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = '#f1f5f9'; }}
                onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
              >
                {item.icon}
                {!isCollapsed && <span>{item.label}</span>}
              </div>
            );
          })}
        </div>
        
        {/* Configuración & Logout at the bottom */}
        <div style={{ padding: '12px 0', borderTop: '1px solid #e2e8f0' }}>
           <div 
             onClick={() => navigate('/settings')}
             style={{ 
               display: 'flex', alignItems: 'center', gap: '16px', justifyContent: isCollapsed ? 'center' : 'flex-start', 
               padding: isCollapsed ? '12px 0' : '12px 24px', cursor: 'pointer', color: location.pathname === '/settings' ? '#10b981' : '#64748b',
               background: location.pathname === '/settings' ? '#ecfdf5' : 'transparent',
               fontWeight: location.pathname === '/settings' ? 600 : 500,
             }}
             title={isCollapsed ? 'Configuración' : undefined}
             onMouseEnter={(e) => { if (location.pathname !== '/settings') e.currentTarget.style.background = '#f1f5f9'; }}
             onMouseLeave={(e) => { if (location.pathname !== '/settings') e.currentTarget.style.background = 'transparent'; }}
           >
             <Settings size={22} />
             {!isCollapsed && <span>Configuración</span>}
           </div>
           <div 
              onClick={() => {
                clearPosSession();
                window.location.href = '/admin/login';
              }}
              style={{ 
                display: 'flex', alignItems: 'center', gap: '16px', justifyContent: isCollapsed ? 'center' : 'flex-start', 
                padding: isCollapsed ? '12px 0' : '12px 24px', cursor: 'pointer', color: '#ef4444', fontWeight: 500
              }}
              title={isCollapsed ? 'Cerrar sesión' : undefined}
              onMouseEnter={(e) => e.currentTarget.style.background = '#fef2f2'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <LogOut size={22} />
              {!isCollapsed && <span>Cerrar sesión</span>}
            </div>
        </div>
      </div>

      <main style={{ flex: 1, overflow: 'auto' }}>
        <Outlet />
      </main>
    </div>
  );
};

export default PosLayout;
