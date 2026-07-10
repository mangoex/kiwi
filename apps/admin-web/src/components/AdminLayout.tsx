import React, { useState } from 'react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { 
  LayoutDashboard, Users, FileText, Settings, BarChart2, Bell, Search, 
  LogOut, Package, Store, Shield, Box, Scale, Carrot, Tags, MessageSquare, Briefcase,
  ChevronLeft, ChevronRight, Camera, ShoppingCart
} from 'lucide-react';
import { Modal, Input, Button } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';

const compressImage = (dataUrl: string, maxWidth = 128, maxHeight = 128): Promise<string> => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.src = dataUrl;
    img.onload = () => {
      const canvas = document.createElement('canvas');
      let width = img.width;
      let height = img.height;

      if (width > height) {
        if (width > maxWidth) {
          height = Math.round((height * maxWidth) / width);
          width = maxWidth;
        }
      } else {
        if (height > maxHeight) {
          width = Math.round((width * maxHeight) / height);
          height = maxHeight;
        }
      }

      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        resolve(dataUrl);
        return;
      }
      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL('image/jpeg', 0.7));
    };
    img.onerror = (err) => reject(err);
  });
};

const AdminLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [profileData, setProfileData] = useState({ display_name: '', email: '', password: '' });
  const [profileAvatar, setProfileAvatar] = useState('');
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
  const currentUserAvatar = localStorage.getItem(`user_avatar_${currentUser.id}`) || `https://i.pravatar.cc/150?u=${currentUser.id}`;

  const openProfileModal = () => {
    setProfileData({
      display_name: currentUser.display_name || '',
      email: currentUser.email || '',
      password: ''
    });
    setProfileAvatar(localStorage.getItem(`user_avatar_${currentUser.id}`) || '');
    setIsProfileModalOpen(true);
  };

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = async () => {
        try {
          const compressed = await compressImage(reader.result as string);
          setProfileAvatar(compressed);
        } catch (err) {
          console.error("Error compressing image:", err);
          setProfileAvatar(reader.result as string);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const saveProfile = async () => {
    if (!currentUser.id) return;
    setIsSavingProfile(true);
    try {
      const payload: any = {
        display_name: profileData.display_name,
        email: profileData.email,
      };
      if (profileData.password.trim()) {
        payload.password = profileData.password;
      }
      
      const response = await fetchApi(`/users/${currentUser.id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      
      if (response) {
        const updatedUser = {
          ...currentUser,
          display_name: profileData.display_name,
          email: profileData.email
        };
        localStorage.setItem('user', JSON.stringify(updatedUser));
        
        if (profileAvatar) {
          localStorage.setItem(`user_avatar_${currentUser.id}`, profileAvatar);
        } else {
          localStorage.removeItem(`user_avatar_${currentUser.id}`);
        }
        
        setIsProfileModalOpen(false);
        window.location.reload();
      }
    } catch (err) {
      console.error(err);
      alert('Error al guardar el perfil');
    } finally {
      setIsSavingProfile(false);
    }
  };

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
    { path: '/pos-app', label: 'Punto de Venta', icon: <ShoppingCart size={20} style={{ color: 'var(--color-green)' }} /> },
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
                onClick={() => {
                  if (item.path === '/pos-app') {
                    const token = localStorage.getItem('auth_token');
                    const user = localStorage.getItem('user');
                    const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || (window.location.port !== '' && window.location.port !== '80' && window.location.port !== '443');
                    const target = isDev
                      ? `http://localhost:3001/pos?token=${token}&user=${encodeURIComponent(user || '{}')}`
                      : `/pos?token=${token}&user=${encodeURIComponent(user || '{}')}`;
                    window.location.href = target;
                  } else {
                    navigate(item.path);
                  }
                }}
                style={{ justifyContent: isCollapsed ? 'center' : 'flex-start', padding: isCollapsed ? '12px 0' : '12px 24px' }}
                title={isCollapsed ? item.label : undefined}
              >
                {item.icon}
                {!isCollapsed && <span>{item.label}</span>}
              </div>
            );
          })}
        </div>
        
        {/* Configuración & Logout at the bottom */}
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
           <div 
             className="admin-nav-item"
             onClick={handleLogout}
             style={{ justifyContent: isCollapsed ? 'center' : 'flex-start', padding: isCollapsed ? '12px 0' : '12px 24px', color: '#ef4444' }}
             title={isCollapsed ? 'Cerrar sesión' : undefined}
           >
             <LogOut size={20} style={{ color: '#ef4444' }} />
             {!isCollapsed && <span style={{ color: '#ef4444' }}>Cerrar sesión</span>}
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
            <div 
              onClick={openProfileModal}
              style={{ width: 40, height: 40, borderRadius: '50%', backgroundColor: 'var(--admin-accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, overflow: 'hidden', cursor: 'pointer', border: '2px solid var(--admin-accent)' }}
              title="Editar mi perfil"
            >
              <img src={currentUserAvatar} alt="Admin" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <div className="admin-content">
          <Outlet />
        </div>
      </div>

      <Modal isOpen={isProfileModalOpen} onClose={() => setIsProfileModalOpen(false)} title="Mi Cuenta">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Avatar Upload Preview */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <div style={{ position: 'relative', width: 100, height: 100, borderRadius: '50%', overflow: 'hidden', background: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {profileAvatar ? (
                <img src={profileAvatar} alt="Avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              ) : (
                <Users size={48} style={{ color: '#94a3b8' }} />
              )}
              <label style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 32, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#fff' }}>
                <Camera size={16} />
                <input type="file" accept="image/*" onChange={handleAvatarChange} style={{ display: 'none' }} />
              </label>
            </div>
            <span style={{ fontSize: '0.875rem', color: 'var(--admin-text-muted)' }}>Sube una foto de perfil</span>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Nombre a mostrar</label>
            <Input value={profileData.display_name} onChange={(e: any) => setProfileData({...profileData, display_name: e.target.value})} />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Correo electrónico</label>
            <Input value={profileData.email} onChange={(e: any) => setProfileData({...profileData, email: e.target.value})} />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Nueva contraseña (dejar en blanco para conservar la actual)</label>
            <Input type="password" value={profileData.password} onChange={(e: any) => setProfileData({...profileData, password: e.target.value})} />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 16 }}>
            <Button variant="secondary" onClick={() => setIsProfileModalOpen(false)}>Cancelar</Button>
            <Button variant="primary" onClick={saveProfile} disabled={isSavingProfile}>
              {isSavingProfile ? 'Guardando...' : 'Guardar Cambios'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default AdminLayout;
