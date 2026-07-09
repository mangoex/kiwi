import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Button, Badge } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Users, Edit, Trash2 } from 'lucide-react';

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  role_id: string;
}

const UsersList = () => {
  const { data: users, isLoading, error } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => fetchApi('/users'),
  });

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="admin-title" style={{ marginBottom: 4 }}>Usuarios</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>Controla los accesos y permisos de tu equipo.</p>
        </div>
        <Button variant="primary" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Plus size={18} />
          Nuevo Usuario
        </Button>
      </div>

      <Card style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>
            Cargando usuarios...
          </div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>
            Error al cargar usuarios. Revisa tu conexión.
          </div>
        ) : !users || users.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center' }}>
            <Users size={48} style={{ color: 'var(--color-border)', margin: '0 auto 16px' }} />
            <h3 style={{ marginBottom: 8 }}>No hay usuarios</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Tu organización aún no tiene usuarios registrados.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)' }}>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Nombre</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Correo</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Estatus</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Rol</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '16px 24px', fontWeight: 500 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 32, height: 32, borderRadius: '50%', backgroundColor: 'var(--color-blue-light)', color: 'var(--color-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: '0.75rem' }}>
                        {user.first_name.charAt(0)}{user.last_name.charAt(0)}
                      </div>
                      {user.first_name} {user.last_name}
                    </div>
                  </td>
                  <td style={{ padding: '16px 24px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                    {user.email}
                  </td>
                  <td style={{ padding: '16px 24px' }}>
                    <Badge variant={user.is_active ? 'success' : 'default'}>
                      {user.is_active ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                  <td style={{ padding: '16px 24px', fontSize: '0.875rem' }}>
                    {user.role_id || 'Usuario'}
                  </td>
                  <td style={{ padding: '16px 24px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                      <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-blue)' }}><Edit size={18} /></button>
                      <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-red)' }}><Trash2 size={18} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
};

export default UsersList;
