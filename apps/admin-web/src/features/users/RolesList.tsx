import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Shield, Edit, Trash2 } from 'lucide-react';

import '../../premium-catalogs.css';

interface Role {
  id: string;
  name: string;
  scope: string;
  created_at: string;
}

interface Permission {
  id: string;
  code: string;
  description: string;
}

const RolesList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [formData, setFormData] = useState({ name: '', scope: 'branch' });
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);

  const { data: roles, isLoading, error } = useQuery<Role[]>({
    queryKey: ['roles'],
    queryFn: () => fetchApi('/roles'),
  });

  const { data: permissions } = useQuery<Permission[]>({
    queryKey: ['permissions'],
    queryFn: () => fetchApi('/permissions'),
  });

  const { data: rolePermissions } = useQuery<string[]>({
    queryKey: ['roles', editingRole?.id, 'permissions'],
    queryFn: () => fetchApi(`/roles/${editingRole?.id}/permissions`),
    enabled: !!editingRole,
  });

  // Update selectedPermissions when rolePermissions loads
  React.useEffect(() => {
    if (rolePermissions) {
      setSelectedPermissions(rolePermissions);
    }
  }, [rolePermissions]);

  const saveMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      let roleId = editingRole?.id;
      if (editingRole) {
        await fetchApi(`/roles/${roleId}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
      } else {
        const response = await fetchApi('/roles', {
          method: 'POST',
          body: JSON.stringify(data),
        });
        roleId = (response as { id: string }).id;
      }
      
      if (roleId) {
        await fetchApi(`/roles/${roleId}/permissions`, {
          method: 'PUT',
          body: JSON.stringify({ permission_ids: selectedPermissions }),
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      setIsModalOpen(false);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => fetchApi(`/roles/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['roles'] })
  });

  const openModal = (role?: Role) => {
    if (role) {
      setEditingRole(role);
      setFormData({ name: role.name, scope: role.scope });
      setSelectedPermissions([]); // Will load from query
    } else {
      setEditingRole(null);
      setFormData({ name: '', scope: 'branch' });
      setSelectedPermissions([]);
    }
    setIsModalOpen(true);
  };

  const togglePermission = (id: string) => {
    setSelectedPermissions(prev => 
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]
    );
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Roles de Usuario</h1>
          <p className="premium-header-subtitle">Configura los roles y sus permisos detallados.</p>
        </div>
        <button className="premium-add-btn" onClick={() => openModal()}>
          <Plus size={18} />
          Nuevo Rol
        </button>
      </div>

      <div className="premium-card">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando roles...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar los roles.</div>
        ) : !roles || roles.length === 0 ? (
          <div className="premium-empty-state">
            <Shield size={64} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay roles registrados</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Agrega el primer rol para asignar a tus usuarios.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Nombre del Rol</th>
                  <th>Alcance (Scope)</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((role) => (
                  <tr key={role.id}>
                    <td style={{ fontWeight: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ padding: 8, background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', borderRadius: 8 }}>
                          <Shield size={18} />
                        </div>
                        {role.name}
                      </div>
                    </td>
                    <td><Badge variant="info">{role.scope}</Badge></td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button className="premium-action-btn edit" onClick={() => openModal(role)}><Edit size={18} /></button>
                        <button className="premium-action-btn delete" onClick={() => deleteMutation.mutate(role.id)}><Trash2 size={18} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingRole ? "Editar Rol" : "Nuevo Rol"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Nombre del Rol</label>
            <Input value={formData.name} onChange={(e: any) => setFormData({...formData, name: e.target.value})} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Alcance (organization / branch)</label>
            <Input value={formData.scope} onChange={(e: any) => setFormData({...formData, scope: e.target.value})} />
          </div>

          <div style={{ marginTop: 16 }}>
            <h4 style={{ marginBottom: 12, fontWeight: 600 }}>Permisos</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: '200px', overflowY: 'auto', padding: 8, border: '1px solid var(--color-border)', borderRadius: 8 }}>
              {permissions?.map(perm => (
                <label key={perm.id} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <input 
                    type="checkbox" 
                    checked={selectedPermissions.includes(perm.id)} 
                    onChange={() => togglePermission(perm.id)} 
                  />
                  <span>{perm.description} <small style={{ color: 'var(--color-text-muted)' }}>({perm.code})</small></span>
                </label>
              ))}
            </div>
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
export default RolesList;
