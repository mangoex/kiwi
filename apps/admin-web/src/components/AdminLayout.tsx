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
    { path: '/', label: 'Dashboard', icon: <LayoutDashboard size={20} /> },
    { path: '/products', label: 'Products', icon: <Package size={20} /> },
    { path: '/categories', label: 'Category', icon: <Tags size={20} /> },
    { path: '/branches', label: 'Brands (Branches)', icon: <Store size={20} /> },
    { path: '/analytics', label: 'Sales', icon: <BarChart2 size={20} /> },
    { path: '/orders', label: 'Order', icon: <FileText size={20} /> },
    { path: '/reports', label: 'Refunds', icon: <Briefcase size={20} /> },
    { path: '/messages', label: 'Message', icon: <MessageSquare size={20} /> },
    { path: '/inventory/items', label: 'Insumos', icon: <Carrot size={20} /> },
    { path: '/settings', label: 'Preferences Settings', icon: <Settings size={20} /> },
    { path: '/users', label: 'Profile Settings', icon: <Users size={20} /> },
  ];

  return (
    <div className="admin-layout">
      {/* Dark Admin Sidebar */}
      <div className="admin-sidebar">
        <div className="admin-sidebar-logo">
          <div className="admin-sidebar-logo-icon">ph</div>
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
             {/* Burger icon mock */}
             <div style={{ fontSize: '3rem', position: 'absolute', bottom: 0, left: '50%', transform: 'translateX(-50%)' }}>🍔</div>
          </div>
          <h4 style={{ color: '#fff', margin: '0 0 8px 0' }}>Add Menus</h4>
          <p style={{ color: 'var(--admin-sidebar-text)', fontSize: '0.75rem', margin: '0 0 12px 0' }}>Manage your food and beverages menus</p>
          <button className="admin-btn" style={{ width: '100%' }}>Add Menu</button>
        </div>
      </div>

      <div className="admin-main">
        {/* Topbar */}
        <header className="admin-topbar">
          <div style={{ position: 'relative' }}>
            <Search size={18} style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', color: 'var(--admin-text-muted)' }} />
            <input 
              type="text" 
              placeholder="Search" 
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
