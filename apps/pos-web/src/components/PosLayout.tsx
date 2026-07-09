import React from 'react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { Sidebar, SidebarItem } from '@restaurantos/ui';
import { Home, Package, ShoppingCart, Users, Clock, Settings, LogOut } from 'lucide-react';

const PosLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { path: '/dashboard', label: 'Panel Principal', icon: <Home size={22} /> },
    { path: '/inventory', label: 'Inventario', icon: <Package size={22} /> },
    { path: '/pos', label: 'Punto de Venta', icon: <ShoppingCart size={22} /> },
    { path: '/customers', label: 'Clientes', icon: <Users size={22} /> },
    { path: '/history', label: 'Historial', icon: <Clock size={22} /> },
  ];

  return (
    <div className="pos-layout">
      {/* Left Sidebar Menu */}
      <Sidebar>
        <div style={{ padding: '24px 16px', fontSize: '1.5rem', fontWeight: 800, color: 'var(--primary)', letterSpacing: '-0.5px' }}>
          Resto<span style={{color: 'var(--text-main)'}}>OS</span>
        </div>
        
        <div style={{ marginTop: 16 }}>
          {navItems.map((item) => (
            <SidebarItem
              key={item.path}
              icon={item.icon}
              label={item.label}
              active={location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path))}
              onClick={() => navigate(item.path)}
            />
          ))}
        </div>
        
        <div style={{ flex: 1 }} />
        
        <SidebarItem 
          icon={<Settings size={22} />} 
          label="Configuración" 
          active={location.pathname === '/settings'}
          onClick={() => navigate('/settings')}
        />
        <SidebarItem 
          icon={<LogOut size={22} />} 
          label="Cerrar sesión" 
          onClick={() => {
            // Placeholder para cierre de sesión real
            window.location.href = '/'; 
          }}
        />
      </Sidebar>

      <main className="pos-main-content">
        <Outlet />
      </main>
    </div>
  );
};

export default PosLayout;
