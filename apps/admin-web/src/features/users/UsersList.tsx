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
  roles?: {
    role_id: string;
    role_name: string;
    scope?: string;
    branch_id?: string | null;
    branch_name?: string | null;
  }[];
}

const UsersList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({ display_name: '', email: '', password: '', role_id: '', branch_id: '' });

  const { data: users, isLoading, error } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => fetchApi('/users'),
  });

  const { data: roles } = useQuery<any[]>({
    queryKey: ['roles'],
    queryFn: () => fetchApi('/roles'),
  });

  const { data: branches } = useQuery<any[]>({
    queryKey: ['branches'],
    queryFn: () => fetchApi('/branches'),
  });

  const selectedRole = roles?.find((role) => role.id === formData.role_id);
  const requiresBranch = selectedRole?.scope === 'branch';

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      const payload = {
        ...data,
        branch_id: requiresBranch ? data.branch_id : null,
      };
      if (editingUser) {
        return fetchApi(`/users/${editingUser.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      }
      return fetchApi('/users', {
        method: 'POST',
        body: JSON.stringify(payload),
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
    const primaryRole = user?.roles && user.roles.length > 0 ? user.roles[0] : null;
    const userRoleId = primaryRole?.role_id || '';
    const userBranchId = primaryRole?.branch_id || '';
    if (user) {
      setEditingUser(user);
      setFormData({ display_name: user.display_name, email: user.email, password: '', role_id: userRoleId, branch_id: userBranchId });
    } else {
      setEditingUser(null);
      setFormData({ display_name: '', email: '', password: '', role_id: '', branch_id: branches?.[0]?.id || '' });
    }
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Users & Access</h1>
          <p className="premium-header-subtitle">Administra cuentas, roles y sucursales operativas.</p>
        </div>
        <button className="premium-add-btn" onClick={() => openModal()}>
          <Plus size={18} />
          Nuevo usuario
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
                  <th>Usuario</th>
                  <th>Email</th>
                  <th>Rol y sucursal</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
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
                      {user.roles && user.roles.length > 0 ? (
                        user.roles.map((r: any) => (
                          <div key={`${r.role_id}-${r.branch_id || 'org'}`} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <Badge variant="info">{r.role_name}</Badge>
                            {r.branch_name && <span style={{ color: 'var(--color-text-muted)', fontSize: '0.8125rem' }}>{r.branch_name}</span>}
                          </div>
                        ))
                      ) : (
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>Sin rol</span>
                      )}
                    </td>
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
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Rol</label>
            <select 
              value={formData.role_id} 
              onChange={(e) => setFormData({...formData, role_id: e.target.value})}
              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', fontSize: '1rem', outline: 'none' }}
            >
              <option value="">Selecciona un rol</option>
              {roles?.map(r => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
          </div>
          {requiresBranch && (
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Sucursal asignada al POS</label>
              <select
                value={formData.branch_id}
                onChange={(e) => setFormData({...formData, branch_id: e.target.value})}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', fontSize: '1rem', outline: 'none' }}
              >
                <option value="">Selecciona una sucursal</option>
                {branches?.map(branch => (
                  <option key={branch.id} value={branch.id}>{branch.name}</option>
                ))}
              </select>
              <p style={{ margin: '6px 0 0', color: 'var(--color-text-muted)', fontSize: '0.8125rem' }}>
                Esta sucursal sera la que el cajero vera por defecto al abrir caja.
              </p>
            </div>
          )}
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>
              {editingUser ? "Nueva contraseña (dejar en blanco para mantener la actual)" : "Contraseña"}
            </label>
            <Input type="password" value={formData.password} onChange={(e: any) => setFormData({...formData, password: e.target.value})} />
          </div>
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
