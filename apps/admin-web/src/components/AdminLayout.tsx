import React from 'react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { 
  LayoutDashboard, Users, FileText, Settings, BarChart2, Bell, Search, 
  LogOut, Package, Store, Shield, Box, Scale, Carrot, Tags, MessageSquare, Briefcase
} from 'lucide-react';

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
    { path: '/', label: 'Panel Principal', icon: <LayoutDashboard size={20} /> },
    { path: '/products', label: 'Productos', icon: <Package size={20} /> },
    { path: '/categories', label: 'Categorías', icon: <Tags size={20} /> },
    { path: '/branches', label: 'Sucursales', icon: <Store size={20} /> },
    { path: '/analytics', label: 'Ventas', icon: <BarChart2 size={20} /> },
    { path: '/orders', label: 'Órdenes', icon: <FileText size={20} /> },
    { path: '/reports', label: 'Reembolsos', icon: <Briefcase size={20} /> },
    { path: '/messages', label: 'Mensajes', icon: <MessageSquare size={20} /> },
    { path: '/inventory/items', label: 'Insumos', icon: <Carrot size={20} /> },
    { path: '/settings', label: 'Configuración', icon: <Settings size={20} /> },
    { path: '/users', label: 'Usuarios', icon: <Users size={20} /> },
  ];

  return (
    <div className="admin-layout">
      {/* Dark Admin Sidebar */}
      <div className="admin-sidebar">
        <div className="admin-sidebar-logo">
          <div className="admin-sidebar-logo-icon">ki</div>
          RestaurantOS
        </div>
        
        <div style={{ flex: 1, overflowY: 'auto', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {navItems.map(item => {
            const isActive = location.pathname === item.path;
            return (
              <div 
                key={item.path} 
                className={`admin-nav-item ${isActive ? 'active' : ''}`}
                onClick={() => navigate(item.path)}
              >
                {item.icon}
                <span>{item.label}</span>
              </div>
            );
          })}
        </div>
        
        <div className="admin-sidebar-cta">
          <div style={{ position: 'relative', height: '60px', marginBottom: '12px' }}>
             {/* Kiwi icon mock */}
             <div style={{ fontSize: '3rem', position: 'absolute', bottom: 0, left: '50%', transform: 'translateX(-50%)' }}>🥝</div>
          </div>
          <h4 style={{ color: '#fff', margin: '0 0 8px 0' }}>Añadir Menús</h4>
          <p style={{ color: 'var(--admin-sidebar-text)', fontSize: '0.75rem', margin: '0 0 12px 0' }}>Administra tu menú de alimentos y bebidas</p>
          <button className="admin-btn" style={{ width: '100%' }}>Añadir Menú</button>
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
            <button style={{ background: '#fff', border: 'none', borderRadius: '50%', width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--admin-text-muted)', boxShadow: 'var(--admin-card-shadow)' }}><Settings size={18} /></button>
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
