import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Package, Search, Plus, Edit } from 'lucide-react';
import '../../premium-catalogs.css';

interface PurchasePresentation {
  id: string;
  code: string;
  name: string;
  item_id: string;
  item_name?: string;
  supplier_id: string;
  supplier_name?: string;
  package_type: string;
  base_unit_yield: number;
  base_unit_code?: string;
  last_net_price: number;
  cost_per_base_unit: number;
  tax_rate: number;
  status: string;
}

const PresentationsList = () => {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPresentation, setSelectedPresentation] = useState<PurchasePresentation | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editPrice, setEditPrice] = useState('');

  const { data: presentations = [], isLoading, error } = useQuery<PurchasePresentation[]>({
    queryKey: ['purchase-presentations'],
    queryFn: () => fetchApi('/purchase-presentations'),
  });

  const priceMutation = useMutation({
    mutationFn: ({ id, price }: { id: string; price: number }) => {
      return fetchApi(`/purchase-presentations/${id}/price`, {
        method: 'PUT',
        body: JSON.stringify({ net_price: price }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-presentations'] });
      setIsModalOpen(false);
    },
  });

  const filtered = presentations.filter((p) =>
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (p.item_name && p.item_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
    p.code.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const openPriceModal = (pres: PurchasePresentation) => {
    setSelectedPresentation(pres);
    setEditPrice(String(pres.last_net_price || ''));
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 className="premium-header-title">Presentaciones de Compra</h1>
          <p className="premium-header-subtitle">
            Formatos comerciales de compra por proveedor, factor de rendimiento y costo unitario resultante.
          </p>
        </div>
      </div>

      <div className="premium-card" style={{ marginBottom: 20, padding: 16 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Search size={18} style={{ color: 'var(--color-text-muted)' }} />
          <input
            type="text"
            placeholder="Buscar por presentación, insumo base o clave..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: 8,
              border: '1px solid var(--color-border)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
            }}
          />
        </div>
      </div>

      <div className="premium-card">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando presentaciones...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar presentaciones.</div>
        ) : filtered.length === 0 ? (
          <div className="premium-empty-state">
            <Package size={64} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No se encontraron presentaciones</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Revisa el término de búsqueda o registra una nueva presentación.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Clave</th>
                  <th>Presentación Comercial</th>
                  <th>Insumo Base</th>
                  <th style={{ textAlign: 'right' }}>Rendimiento Base</th>
                  <th style={{ textAlign: 'right' }}>Último Precio Compra</th>
                  <th style={{ textAlign: 'right' }}>Costo / Unidad Base</th>
                  <th>Estatus</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id}>
                    <td style={{ fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>{item.code}</td>
                    <td style={{ fontWeight: 600 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ padding: 6, background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', borderRadius: 6 }}>
                          <Package size={16} />
                        </div>
                        {item.name}
                      </div>
                    </td>
                    <td>{item.item_name || 'Insumo Base'}</td>
                    <td style={{ textAlign: 'right', fontWeight: 500 }}>
                      {Number(item.base_unit_yield).toFixed(3)} {item.base_unit_code || 'UNIDAD'}
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--color-text)' }}>
                      ${Number(item.last_net_price).toFixed(2)}
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--color-green)' }}>
                      ${Number(item.cost_per_base_unit).toFixed(2)} / {item.base_unit_code || 'u'}
                    </td>
                    <td>
                      <Badge variant={item.status === 'active' ? 'success' : 'default'}>
                        {item.status === 'active' ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button className="premium-action-btn edit" onClick={() => openPriceModal(item)} title="Actualizar precio">
                        <Edit size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Actualizar Precio de Compra">
        {selectedPresentation && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
              Presentación: <strong>{selectedPresentation.name}</strong>
            </p>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>
                Nuevo Precio Neto ($ MXN)
              </label>
              <Input
                type="number"
                step="0.01"
                value={editPrice}
                onChange={(e: any) => setEditPrice(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <Button variant="secondary" onClick={() => setIsModalOpen(false)}>
                Cancelar
              </Button>
              <Button
                variant="primary"
                onClick={() => priceMutation.mutate({ id: selectedPresentation.id, price: parseFloat(editPrice) })}
                disabled={priceMutation.isPending}
              >
                Guardar Precio
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
};

export default PresentationsList;