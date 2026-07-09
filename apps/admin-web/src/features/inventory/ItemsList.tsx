import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Carrot, Edit } from 'lucide-react';

import '../../premium-catalogs.css';

interface Item {
  id: string;
  name: string;
  sku: string;
  base_unit_id: string;
  unit_name?: string;
  unit_code?: string;
  item_type: string;
  status: string;
  created_at: string;
}

interface Unit {
  id: string;
  code: string;
  name: string;
}

const ItemsList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<Item | null>(null);
  const [formData, setFormData] = useState({ name: '', sku: '', base_unit_id: '', item_type: 'ingredient', status: 'active' });

  const { data: items, isLoading, error } = useQuery<Item[]>({
    queryKey: ['inventory', 'items'],
    queryFn: () => fetchApi('/inventory/items'),
  });

  const { data: units } = useQuery<Unit[]>({
    queryKey: ['inventory', 'units'],
    queryFn: () => fetchApi('/inventory/units'),
  });

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      if (editingItem) {
        return fetchApi(`/inventory/items/${editingItem.id}`, {
          method: 'PUT',
          body: JSON.stringify({ name: data.name, base_unit_id: data.base_unit_id, item_type: data.item_type, status: data.status }),
        });
      }
      return fetchApi('/inventory/items', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory', 'items'] });
      setIsModalOpen(false);
    }
  });

  const openModal = (item?: Item) => {
    if (item) {
      setEditingItem(item);
      setFormData({ name: item.name, sku: item.sku, base_unit_id: item.base_unit_id, item_type: item.item_type, status: item.status });
    } else {
      setEditingItem(null);
      setFormData({ name: '', sku: '', base_unit_id: units?.[0]?.id || '', item_type: 'ingredient', status: 'active' });
    }
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Insumos y Artículos</h1>
          <p className="premium-header-subtitle">Gestiona los insumos, empaques y artículos del inventario.</p>
        </div>
        <button className="premium-add-btn" onClick={() => openModal()}>
          <Plus size={18} />
          Nuevo Insumo
        </button>
      </div>

      <div className="premium-card">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando insumos...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar los insumos.</div>
        ) : !items || items.length === 0 ? (
          <div className="premium-empty-state">
            <Carrot size={64} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay insumos registrados</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Crea ingredientes o empaques para armar tus recetas.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Nombre</th>
                  <th>Tipo</th>
                  <th>Unidad Base</th>
                  <th>Estatus</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td style={{ fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>{item.sku}</td>
                    <td style={{ fontWeight: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ padding: 8, background: 'rgba(234, 88, 12, 0.1)', color: '#ea580c', borderRadius: 8 }}>
                          <Carrot size={18} />
                        </div>
                        {item.name}
                      </div>
                    </td>
                    <td>
                      <Badge variant={item.item_type === 'ingredient' ? 'info' : 'default'}>
                        {item.item_type}
                      </Badge>
                    </td>
                    <td style={{ color: 'var(--color-text-muted)' }}>{item.unit_name || item.unit_code || 'N/A'}</td>
                    <td>
                      <Badge variant={item.status === 'active' ? 'success' : 'default'}>
                        {item.status === 'active' ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button className="premium-action-btn edit" onClick={() => openModal(item)}><Edit size={18} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingItem ? "Editar Insumo" : "Nuevo Insumo"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {!editingItem && (
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>SKU</label>
              <Input value={formData.sku} onChange={(e: any) => setFormData({...formData, sku: e.target.value})} />
            </div>
          )}
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Nombre</label>
            <Input value={formData.name} onChange={(e: any) => setFormData({...formData, name: e.target.value})} />
          </div>
          
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Tipo de Artículo</label>
            <select 
              value={formData.item_type} 
              onChange={e => setFormData({...formData, item_type: e.target.value})}
              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', outline: 'none' }}
            >
              <option value="ingredient">Ingrediente</option>
              <option value="packaging">Empaque</option>
              <option value="other">Otro</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Unidad de Medida Base</label>
            <select 
              value={formData.base_unit_id} 
              onChange={e => setFormData({...formData, base_unit_id: e.target.value})}
              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)', outline: 'none' }}
            >
              <option value="">Selecciona una unidad</option>
              {units?.map(u => (
                <option key={u.id} value={u.id}>{u.name} ({u.code})</option>
              ))}
            </select>
          </div>

          {editingItem && (
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
            <Button variant="primary" onClick={() => saveMutation.mutate(formData)} disabled={saveMutation.isPending || !formData.base_unit_id}>
              {saveMutation.isPending ? 'Guardando...' : 'Guardar'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};
export default ItemsList;
