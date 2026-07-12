import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Input } from '@restaurantos/ui';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { Lock, Mail } from 'lucide-react';

export const Login = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetchApi<{ token: string; user: any }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      
      localStorage.setItem('auth_token', response.token);
      localStorage.setItem('user', JSON.stringify(response.user));
      if (response.user.assigned_branch_id) {
        localStorage.setItem('pos_branch_id', response.user.assigned_branch_id);
      }
      if (!localStorage.getItem('pos_register_id')) {
        localStorage.setItem('pos_register_id', 'CAJA-01');
      }

      const roles: string[] = response.user.roles || [];
      const permissions: string[] = response.user.permissions || [];
      const canUseAdmin = response.user.is_superadmin
        || roles.includes('Administrador corporativo')
        || permissions.includes('admin.manage')
        || permissions.includes('dashboard.read')
        || permissions.includes('inventory.transfer.receive');
      const canUsePos = permissions.includes('pos.operate')
        || roles.includes('Cajero')
        || roles.includes('Caja');
      if (canUsePos && !canUseAdmin) {
        const isDev = window.location.hostname === 'localhost'
          || window.location.hostname === '127.0.0.1'
          || (window.location.port !== '' && window.location.port !== '80' && window.location.port !== '443');
        const targetUrl = isDev
          ? `http://localhost:3001/pos/pos?token=${response.token}&user=${encodeURIComponent(JSON.stringify(response.user))}`
          : '/pos/pos';
        window.location.href = targetUrl;
        return;
      }
      navigate(
        permissions.includes('inventory.transfer.receive') && !permissions.includes('dashboard.read')
          ? '/inventory/transfers'
          : '/'
      );
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message || 'Error de autenticación');
      } else {
        setError('Error de conexión al servidor');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', backgroundColor: 'var(--color-bg)' }}>
      <Card style={{ width: 400, padding: 32 }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{ fontSize: '1.5rem', color: 'var(--color-blue)', marginBottom: 8 }}>RestaurantOS</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>Ingresa tus credenciales para continuar</p>
        </div>

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {error && (
            <div style={{ padding: 12, backgroundColor: 'var(--color-red-light)', color: 'var(--color-red)', borderRadius: 8, fontSize: '0.875rem' }}>
              {error}
            </div>
          )}

          <div>
            <label style={{ display: 'block', marginBottom: 8, fontSize: '0.875rem', fontWeight: 500 }}>Correo electrónico</label>
            <div style={{ position: 'relative' }}>
              <Mail size={18} style={{ position: 'absolute', left: 12, top: 11, color: 'var(--color-text-muted)' }} />
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@restaurantos.com"
                style={{ paddingLeft: 40, width: '100%' }}
                required
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 8, fontSize: '0.875rem', fontWeight: 500 }}>Contraseña</label>
            <div style={{ position: 'relative' }}>
              <Lock size={18} style={{ position: 'absolute', left: 12, top: 11, color: 'var(--color-text-muted)' }} />
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{ paddingLeft: 40, width: '100%' }}
                required
              />
            </div>
          </div>

          <Button type="submit" variant="primary" style={{ width: '100%', marginTop: 8 }} disabled={loading}>
            {loading ? 'Ingresando...' : 'Iniciar Sesión'}
          </Button>
        </form>
      </Card>
    </div>
  );
};

export default Login;
