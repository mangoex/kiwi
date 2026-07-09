import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Users, Edit, Trash2 } from 'lucide-react';

interface User {
  id: string;
  display_name: string;
  email: string;
  status: string;
}

const UsersList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({ display_name: '', email: '', password: '' });

  const { data: users, isLoading, error } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => fetchApi('/users'),
  });

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      if (editingUser) {
        return fetchApi(`/users/${editingUser.id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
      }
      return fetchApi('/users', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setIsModalOpen(false);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => fetchApi(`/users/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] })
  });

  const openModal = (user?: User) => {
    if (user) {
      setEditingUser(user);
      setFormData({ display_name: user.display_name, email: user.email, password: '' });
    } else {
      setEditingUser(null);
      setFormData({ display_name: '', email: '', password: '' });
    }
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Users & Access</h1>
          <p className="premium-header-subtitle">Manage staff accounts, roles, and permissions securely.</p>
        </div>
        <button className="premium-add-btn" onClick={() => openModal()}>
          <Plus size={18} />
          Invite User
        </button>
      </div>

      <div className="premium-card">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando usuarios...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar los usuarios.</div>
        ) : !users || users.length === 0 ? (
          <div className="premium-empty-state">
            <Users size={64} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay usuarios</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Invita al primer usuario a la plataforma.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td style={{ fontWeight: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ padding: 8, background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', borderRadius: 8 }}>
                          <Users size={18} />
                        </div>
                        {user.display_name}
                      </div>
                    </td>
                    <td style={{ color: 'var(--color-text-muted)' }}>{user.email}</td>
                    <td>
                      <Badge variant={user.status === 'active' ? 'success' : user.status === 'invited' ? 'info' : 'default'}>
                        {user.status === 'active' ? 'Activo' : user.status === 'invited' ? 'Invitado' : 'Suspendido'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button className="premium-action-btn edit" onClick={() => openModal(user)}><Edit size={18} /></button>
                        <button className="premium-action-btn delete" onClick={() => deleteMutation.mutate(user.id)}><Trash2 size={18} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingUser ? "Editar Usuario" : "Nuevo Usuario"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Correo electrónico</label>
            <Input value={formData.email} onChange={(e: any) => setFormData({...formData, email: e.target.value})} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Nombre a mostrar</label>
            <Input value={formData.display_name} onChange={(e: any) => setFormData({...formData, display_name: e.target.value})} />
          </div>
          {!editingUser && (
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Contraseña</label>
              <Input type="password" value={formData.password} onChange={(e: any) => setFormData({...formData, password: e.target.value})} />
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 16 }}>
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>Cancelar</Button>
            <Button variant="primary" onClick={() => saveMutation.mutate(formData)} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Guardando...' : 'Guardar'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};
export default UsersList;
