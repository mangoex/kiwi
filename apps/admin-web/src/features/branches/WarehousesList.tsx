import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Box, Edit, Trash2 } from 'lucide-react';

import '../../premium-catalogs.css';

interface Warehouse {
  id: string;
  name: string;
  branch_id: string;
  status: string;
  created_at: string;
}

interface Branch {
  id: string;
  name: string;
}

const WarehousesList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingWarehouse, setEditingWarehouse] = useState<Warehouse | null>(null);
  const [formData, setFormData] = useState({ name: '', branch_id: '', status: 'active' });

  const { data: warehouses, isLoading, error } = useQuery<Warehouse[]>({
    queryKey: ['warehouses'],
    queryFn: () => fetchApi('/warehouses'),
  });

  const { data: branches } = useQuery<Branch[]>({
    queryKey: ['branches'],
    queryFn: () => fetchApi('/branches'),
  });

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      if (editingWarehouse) {
        return fetchApi(`/warehouses/${editingWarehouse.id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
      }
      return fetchApi('/warehouses', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] });
      setIsModalOpen(false);
    }
  });

  // the backend delete_warehouse is missing, but let's keep the frontend ready for when it's added (if added)
  // Wait, I didn't add delete_warehouse in backend for phase 1. Let's just remove delete button or use deactivate.
  
  const openModal = (warehouse?: Warehouse) => {
    if (warehouse) {
      setEditingWarehouse(warehouse);
      setFormData({ name: warehouse.name, branch_id: warehouse.branch_id, status: warehouse.status });
    } else {
      setEditingWarehouse(null);
      setFormData({ name: '', branch_id: branches?.[0]?.id || '', status: 'active' });
    }
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Almacenes</h1>
          <p className="premium-header-subtitle">Gestiona los almacenes físicos asignados a cada sucursal.</p>
        </div>
        <button className="premium-add-btn" onClick={() => openModal()}>
          <Plus size={18} />
          Nuevo Almacén
        </button>
      </div>

      <div className="premium-card">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando almacenes...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar almacenes.</div>
        ) : !warehouses || warehouses.length === 0 ? (
          <div className="premium-empty-state">
            <Box size={64} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay almacenes registrados</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Crea el primer almacén de inventario para una sucursal.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Sucursal</th>
                  <th>Estatus</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {warehouses.map((warehouse) => {
                  const branchName = branches?.find(b => b.id === warehouse.branch_id)?.name || warehouse.branch_id;
                  return (
                    <tr key={warehouse.id}>
                      <td style={{ fontWeight: 500 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{ padding: 8, background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', borderRadius: 8 }}>
                            <Box size={18} />
                          </div>
                          {warehouse.name}
                        </div>
                      </td>
                      <td style={{ color: 'var(--color-text-muted)' }}>{branchName}</td>
                      <td>
                        <Badge variant={warehouse.status === 'active' ? 'success' : 'default'}>
                          {warehouse.status === 'active' ? 'Activo' : 'Inactivo'}
                        </Badge>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                          <button className="premium-action-btn edit" onClick={() => openModal(warehouse)}><Edit size={18} /></button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingWarehouse ? "Editar Almacén" : "Nuevo Almacén"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Nombre del Almacén</label>
            <Input value={formData.name} onChange={(e: any) => setFormData({...formData, name: e.target.value})} />
          </div>
          
          {!editingWarehouse && (
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Sucursal Asignada</label>
              <select 
                value={formData.branch_id} 
                onChange={e => setFormData({...formData, branch_id: e.target.value})}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', outline: 'none' }}
              >
                <option value="">Selecciona una sucursal</option>
                {branches?.map(b => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
            </div>
          )}

          {editingWarehouse && (
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Estatus</label>
              <select 
                value={formData.status} 
                onChange={e => setFormData({...formData, status: e.target.value})}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', outline: 'none' }}
              >
                <option value="active">Activo</option>
                <option value="inactive">Inactivo</option>
              </select>
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
export default WarehousesList;
