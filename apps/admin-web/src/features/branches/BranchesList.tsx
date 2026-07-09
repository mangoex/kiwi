import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Store, Edit, Trash2 } from 'lucide-react';

import '../../premium-catalogs.css';

interface Branch {
  id: string;
  name: string;
  code: string;
  status: string;
  address: string;
  organization_id: string;
}

const BranchesList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBranch, setEditingBranch] = useState<Branch | null>(null);
  const [formData, setFormData] = useState({ name: '', code: '' });

  const { data: branches, isLoading, error } = useQuery<Branch[]>({
    queryKey: ['branches'],
    queryFn: () => fetchApi('/branches'),
  });

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      if (editingBranch) {
        return fetchApi(`/branches/${editingBranch.id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
      }
      return fetchApi('/branches', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['branches'] });
      setIsModalOpen(false);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => fetchApi(`/branches/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['branches'] })
  });

  const openModal = (branch?: Branch) => {
    if (branch) {
      setEditingBranch(branch);
      setFormData({ name: branch.name, code: branch.code || '' });
    } else {
      setEditingBranch(null);
      setFormData({ name: '', code: '' });
    }
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Branches & Locations</h1>
          <p className="premium-header-subtitle">Administra las sucursales de la franquicia.</p>
        </div>
        <button className="premium-add-btn" onClick={() => openModal()}>
          <Plus size={18} />
          Nueva Sucursal
        </button>
      </div>

      <div className="premium-card">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando sucursales...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar sucursales.</div>
        ) : !branches || branches.length === 0 ? (
          <div className="premium-empty-state">
            <Store size={64} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay sucursales registradas</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Agrega la primera sucursal para operar.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Estatus</th>
                  <th>Código</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {branches.map((branch) => (
                  <tr key={branch.id}>
                    <td style={{ fontWeight: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ padding: 8, background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', borderRadius: 8 }}>
                          <Store size={18} />
                        </div>
                        {branch.name}
                      </div>
                    </td>
                    <td>
                      <Badge variant={branch.status === 'active' ? 'success' : 'default'}>
                        {branch.status === 'active' ? 'Activa' : 'Inactiva'}
                      </Badge>
                    </td>
                    <td style={{ color: 'var(--color-text-muted)' }}>{branch.code}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button className="premium-action-btn edit" onClick={() => openModal(branch)}><Edit size={18} /></button>
                        <button className="premium-action-btn delete" onClick={() => deleteMutation.mutate(branch.id)}><Trash2 size={18} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingBranch ? "Editar Sucursal" : "Nueva Sucursal"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Nombre de la sucursal</label>
            <Input value={formData.name} onChange={(e: any) => setFormData({...formData, name: e.target.value})} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Código (ej. SUC01)</label>
            <Input value={formData.code} onChange={(e: any) => setFormData({...formData, code: e.target.value})} />
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
export default BranchesList;
