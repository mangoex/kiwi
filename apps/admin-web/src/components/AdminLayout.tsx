import React from 'react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { Sidebar, SidebarItem } from '@restaurantos/ui';
import { LayoutDashboard, Users, FileText, Settings, BarChart2, Bell, Search, LogOut, Package, Store } from 'lucide-react';

const AdminLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    sessionStorage.removeItem('auth_token');
    navigate('/login');
  };

  const navItems = [
    { path: '/', label: 'Overview', icon: <LayoutDashboard size={20} /> },
    { path: '/products', label: 'Products & Catalog', icon: <Package size={20} /> },
    { path: '/branches', label: 'Branches', icon: <Store size={20} /> },
    { path: '/users', label: 'Users & Roles', icon: <Users size={20} /> },
    { path: '/analytics', label: 'Analytics', icon: <BarChart2 size={20} /> },
    { path: '/reports', label: 'Reports', icon: <FileText size={20} /> },
  ];

  return (
    <div className="admin-layout">
      {/* Admin Sidebar */}
      <Sidebar>
        <div style={{ padding: '12px 16px', fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-blue)', marginBottom: 24 }}>
          RestaurantOS
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 500 }}>ADMIN PANEL</div>
        </div>
        
        {navItems.map(item => (
          <div key={item.path} onClick={() => navigate(item.path)} style={{ cursor: 'pointer' }}>
            <SidebarItem 
              icon={item.icon} 
              label={item.label} 
              active={location.pathname === item.path} 
            />
          </div>
        ))}
        
        <div style={{ flex: 1 }} />
        
        <div onClick={() => navigate('/settings')} style={{ cursor: 'pointer' }}>
          <SidebarItem icon={<Settings size={20} />} label="Settings" active={location.pathname === '/settings'} />
        </div>
      </Sidebar>

      <div className="admin-main">
        {/* Topbar */}
        <header className="admin-topbar" style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div style={{ position: 'relative', width: '300px' }}>
            <Search size={18} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }} />
            <input 
              type="text" 
              placeholder="Search anything..." 
              style={{ width: '100%', padding: '10px 12px 10px 40px', borderRadius: 'var(--radius-full)', border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', outline: 'none' }}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}><Bell size={20} /></button>
            <div style={{ width: 36, height: 36, borderRadius: '50%', backgroundColor: 'var(--color-blue-light)', color: 'var(--color-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600 }}>MG</div>
            <button 
              onClick={handleLogout}
              style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-red)' }}
            >
              <LogOut size={18} />
              <span style={{ fontWeight: 500 }}>Salir</span>
            </button>
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
