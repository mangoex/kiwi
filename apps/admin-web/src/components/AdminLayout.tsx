import React, { useState } from 'react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { 
  LayoutDashboard, Users, FileText, Settings, BarChart2, Bell, Search, 
  LogOut, Package, Store, Shield, Box, Scale, Carrot, Tags, MessageSquare, Briefcase,
  ChevronLeft, ChevronRight
} from 'lucide-react';

const AdminLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    sessionStorage.removeItem('auth_token');
    navigate('/login');
  };

  const navItems = [
    { path: '/', label: 'Panel Principal', icon: <LayoutDashboard size={20} /> },
    { path: '/products', label: 'Productos', icon: <Package size={20} /> },
    { path: '/categories', label: 'Categorías', icon: <Tags size={20} /> },
    { path: '/branches', label: 'Sucursales', icon: <Store size={20} /> },
    { path: '/analytics', label: 'Ventas', icon: <BarChart2 size={20} /> },
    { path: '/orders', label: 'Órdenes', icon: <FileText size={20} /> },
    { path: '/reports', label: 'Reembolsos', icon: <Briefcase size={20} /> },
    { path: '/messages', label: 'Mensajes', icon: <MessageSquare size={20} /> },
    { path: '/inventory/items', label: 'Insumos', icon: <Carrot size={20} /> },
    { path: '/users', label: 'Usuarios', icon: <Users size={20} /> },
  ];

  return (
    <div className="admin-layout">
      {/* Dark Admin Sidebar */}
      <div className="admin-sidebar" style={{ width: isCollapsed ? '80px' : '260px', transition: 'width 0.3s', display: 'flex', flexDirection: 'column' }}>
        <div className="admin-sidebar-logo" style={{ display: 'flex', justifyContent: isCollapsed ? 'center' : 'space-between', alignItems: 'center', padding: isCollapsed ? '24px 0' : '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className="admin-sidebar-logo-icon" style={{ background: 'transparent', fontSize: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              🥝
            </div>
            {!isCollapsed && <span>RestaurantOS</span>}
          </div>
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: 0, display: isCollapsed ? 'none' : 'block' }}
          >
            <ChevronLeft size={20} />
          </button>
        </div>
        
        {isCollapsed && (
          <div style={{ textAlign: 'center', paddingBottom: '16px' }}>
            <button 
              onClick={() => setIsCollapsed(false)}
              style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: 0 }}
            >
              <ChevronRight size={20} />
            </button>
          </div>
        )}

        <div style={{ flex: 1, overflowY: 'auto', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {navItems.map(item => {
            const isActive = location.pathname === item.path;
            return (
              <div 
                key={item.path} 
                className={`admin-nav-item ${isActive ? 'active' : ''}`}
                onClick={() => navigate(item.path)}
                style={{ justifyContent: isCollapsed ? 'center' : 'flex-start', padding: isCollapsed ? '12px 0' : '12px 24px' }}
                title={isCollapsed ? item.label : undefined}
              >
                {item.icon}
                {!isCollapsed && <span>{item.label}</span>}
              </div>
            );
          })}
        </div>
        
        {/* Configuración at the bottom */}
        <div style={{ padding: '12px 0', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
           <div 
             className={`admin-nav-item ${location.pathname === '/settings' ? 'active' : ''}`}
             onClick={() => navigate('/settings')}
             style={{ justifyContent: isCollapsed ? 'center' : 'flex-start', padding: isCollapsed ? '12px 0' : '12px 24px' }}
             title={isCollapsed ? 'Configuración' : undefined}
           >
             <Settings size={20} />
             {!isCollapsed && <span>Configuración</span>}
           </div>
        </div>
      </div>

      <div className="admin-main">
        {/* Topbar */}
        <header className="admin-topbar">
          <div style={{ position: 'relative' }}>
            <Search size={18} style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', color: 'var(--admin-text-muted)' }} />
            <input 
              type="text" 
              placeholder="Buscar..." 
              className="admin-search-input"
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <button style={{ background: '#fff', border: 'none', borderRadius: '50%', width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--admin-text-muted)', boxShadow: 'var(--admin-card-shadow)' }}><Bell size={18} /></button>
            <button style={{ background: '#fff', border: 'none', borderRadius: '50%', width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--admin-text-muted)', boxShadow: 'var(--admin-card-shadow)' }}><FileText size={18} /></button>
            <div style={{ width: 40, height: 40, borderRadius: '50%', backgroundColor: 'var(--admin-accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, overflow: 'hidden' }}>
              <img src="https://i.pravatar.cc/150?u=admin" alt="Admin" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <div className="admin-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
};

export default AdminLayout;
