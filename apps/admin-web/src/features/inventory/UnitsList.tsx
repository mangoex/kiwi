import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Scale, Edit } from 'lucide-react';

import '../../premium-catalogs.css';

interface Unit {
  id: string;
  code: string;
  name: string;
  precision_scale: number;
}

const UnitsList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUnit, setEditingUnit] = useState<Unit | null>(null);
  const [formData, setFormData] = useState({ code: '', name: '', precision_scale: 0 });

  const { data: units, isLoading, error } = useQuery<Unit[]>({
    queryKey: ['inventory', 'units'],
    queryFn: () => fetchApi('/inventory/units'),
  });

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      if (editingUnit) {
        return fetchApi(`/inventory/units/${editingUnit.id}`, {
          method: 'PUT',
          body: JSON.stringify({ name: data.name, precision_scale: data.precision_scale }),
        });
      }
      return fetchApi('/inventory/units', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory', 'units'] });
      setIsModalOpen(false);
    }
  });

  const openModal = (unit?: Unit) => {
    if (unit) {
      setEditingUnit(unit);
      setFormData({ code: unit.code, name: unit.name, precision_scale: unit.precision_scale });
    } else {
      setEditingUnit(null);
      setFormData({ code: '', name: '', precision_scale: 0 });
    }
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Unidades de Medida</h1>
          <p className="premium-header-subtitle">Administra las unidades base para el inventario (kg, litros, piezas, etc).</p>
        </div>
        <button className="premium-add-btn" onClick={() => openModal()}>
          <Plus size={18} />
          Nueva Unidad
        </button>
      </div>

      <div className="premium-card">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando unidades...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar las unidades.</div>
        ) : !units || units.length === 0 ? (
          <div className="premium-empty-state">
            <Scale size={64} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay unidades registradas</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Agrega la primera unidad de medida (ej. KG, LT, PZA).</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Nombre</th>
                  <th>Precisión (Decimales)</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {units.map((unit) => (
                  <tr key={unit.id}>
                    <td style={{ fontWeight: 600, color: 'var(--color-primary)' }}>{unit.code}</td>
                    <td style={{ fontWeight: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ padding: 8, background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', borderRadius: 8 }}>
                          <Scale size={18} />
                        </div>
                        {unit.name}
                      </div>
                    </td>
                    <td style={{ color: 'var(--color-text-muted)' }}>{unit.precision_scale}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button className="premium-action-btn edit" onClick={() => openModal(unit)}><Edit size={18} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingUnit ? "Editar Unidad" : "Nueva Unidad"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {!editingUnit && (
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Código (ej. KG)</label>
              <Input value={formData.code} onChange={(e: any) => setFormData({...formData, code: e.target.value.toUpperCase()})} />
            </div>
          )}
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Nombre (ej. Kilogramos)</label>
            <Input value={formData.name} onChange={(e: any) => setFormData({...formData, name: e.target.value})} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Precisión Decimal (0-4)</label>
            <Input 
              type="number" 
              min={0} 
              max={4}
              value={formData.precision_scale} 
              onChange={(e: any) => setFormData({...formData, precision_scale: parseInt(e.target.value) || 0})} 
            />
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
export default UnitsList;
