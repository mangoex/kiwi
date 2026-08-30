import React, { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Package, Search, Plus, Edit } from 'lucide-react';
import '../../premium-catalogs.css';
import { readAdminAiSelection } from '../admin-ai/adminAiSelection';

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

interface InventoryItem {
  id: string;
  name: string;
  sku: string;
  base_unit_id: string;
  unit_name?: string;
  unit_code?: string;
}

interface Supplier {
  id: string;
  commercial_name: string;
}

const PresentationsList = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<PurchasePresentation | null>(null);

  const [formData, setFormData] = useState({
    item_id: '',
    supplier_id: '',
    code: '',
    name: '',
    base_unit_yield: '1',
    last_net_price: '0',
    tax_rate: '0.16',
  });

  const { data: presentations = [], isLoading, error } = useQuery<PurchasePresentation[]>({
    queryKey: ['purchase-presentations'],
    queryFn: () => fetchApi('/purchase-presentations'),
  });

  const { data: items = [] } = useQuery<InventoryItem[]>({
    queryKey: ['inventory', 'items'],
    queryFn: () => fetchApi('/inventory/items'),
  });

  const { data: suppliers = [] } = useQuery<Supplier[]>({
    queryKey: ['suppliers'],
    queryFn: () => fetchApi('/suppliers'),
  });

  const assistantSelectionId = searchParams.get('admin_ai_selection');
  const assistantSelection = useMemo(
    () => readAdminAiSelection(assistantSelectionId),
    [assistantSelectionId],
  );
  const assistantItemIds = assistantSelection?.item_ids || [];

  const clearAssistantSelection = () => {
    if (assistantSelectionId) sessionStorage.removeItem(`admin-ai-selection:${assistantSelectionId}`);
    const next = new URLSearchParams(searchParams);
    next.delete('admin_ai_selection');
    setSearchParams(next, { replace: true });
  };

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      const payload = {
        item_id: data.item_id,
        supplier_id: data.supplier_id || undefined,
        code: data.code,
        name: data.name,
        base_unit_yield: parseFloat(data.base_unit_yield) || 1.0,
        usable_content: parseFloat(data.base_unit_yield) || 1.0,
        last_net_price: parseFloat(data.last_net_price) || 0.0,
        tax_rate: parseFloat(data.tax_rate) || 0.0,
      };

      if (editingItem) {
        return fetchApi(`/purchase-presentations/${editingItem.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      }
      return fetchApi('/purchase-presentations', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-presentations'] });
      setIsModalOpen(false);
    },
  });

  const openCreateModal = () => {
    setEditingItem(null);
    const defaultItem = items.find((item) => assistantItemIds.includes(item.id)) || items[0];
    setFormData({
      item_id: defaultItem ? defaultItem.id : '',
      supplier_id: suppliers[0] ? suppliers[0].id : '',
      code: defaultItem ? `PRES-${defaultItem.sku}` : '',
      name: defaultItem ? `${defaultItem.name} (Presentación)` : '',
      base_unit_yield: '1',
      last_net_price: '0',
      tax_rate: '0.16',
    });
    setIsModalOpen(true);
  };

  const openEditModal = (pres: PurchasePresentation) => {
    setEditingItem(pres);
    setFormData({
      item_id: pres.item_id,
      supplier_id: pres.supplier_id || '',
      code: pres.code,
      name: pres.name,
      base_unit_yield: String(pres.base_unit_yield || '1'),
      last_net_price: String(pres.last_net_price || '0'),
      tax_rate: String(pres.tax_rate || '0.16'),
    });
    setIsModalOpen(true);
  };

  const onItemChange = (itemId: string) => {
    const selected = items.find((it) => it.id === itemId);
    setFormData((prev) => ({
      ...prev,
      item_id: itemId,
      code: selected ? `PRES-${selected.sku}` : prev.code,
      name: selected && !editingItem ? `${selected.name} · Presentación` : prev.name,
    }));
  };

  const filtered = presentations.filter((p) => {
    const matchesAssistantSelection = !assistantSelection || assistantItemIds.includes(p.item_id);
    const matchesSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (p.item_name && p.item_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      p.code.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesAssistantSelection && matchesSearch;
  });

  const selectedItemObj = items.find((it) => it.id === formData.item_id);
  const calculatedCostPerBase = (parseFloat(formData.last_net_price) || 0) / (parseFloat(formData.base_unit_yield) || 1);

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 className="premium-header-title">Presentaciones de Compra</h1>
          <p className="premium-header-subtitle">
            Formatos comerciales de compra por proveedor, factor de rendimiento y costo unitario resultante.
          </p>
        </div>
        <button className="premium-add-btn" onClick={openCreateModal}>
          <Plus size={18} />
          Nueva Presentación
        </button>
      </div>

      {assistantSelection && (
        <div className="premium-card" style={{ marginBottom: 20, padding: 16, borderLeft: '4px solid var(--color-green)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <strong>Revisión preparada por el asistente</strong>
              <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                Mostrando presentaciones relacionadas con {assistantItemIds.length} insumos. Crea o corrige una presentación para registrar un precio de compra utilizable.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button variant="secondary" onClick={clearAssistantSelection}>Ver todas</Button>
              <Button onClick={openCreateModal}><Plus size={16} /> Nueva presentación</Button>
            </div>
          </div>
        </div>
      )}

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
            <p style={{ color: 'var(--color-text-muted)' }}>
              {assistantSelection
                ? 'Los insumos seleccionados aún no tienen una presentación utilizable. Crea la primera para continuar.'
                : 'Crea una presentación comercial para comprar insumos a proveedores.'}
            </p>
            {assistantSelection && <Button onClick={openCreateModal}><Plus size={16} /> Crear presentación</Button>}
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
                      <button className="premium-action-btn edit" onClick={() => openEditModal(item)} title="Editar presentación">
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

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingItem ? "Editar Presentación de Compra" : "Nueva Presentación de Compra"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>
              Insumo Base Gastronómico
            </label>
            <select
              value={formData.item_id}
              onChange={(e) => onItemChange(e.target.value)}
              disabled={!!editingItem}
              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)' }}
            >
              {items.map((it) => (
                <option key={it.id} value={it.id}>
                  {it.sku} - {it.name} ({it.unit_code || it.unit_name})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>
              Nombre de la Presentación Comercial
            </label>
            <Input
              value={formData.name}
              placeholder="Ej. Aceituna Frasco 450g, Mayonesa Bote 3.35kg..."
              onChange={(e: any) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>
                Clave / Código
              </label>
              <Input
                value={formData.code}
                placeholder="PRES-1001"
                onChange={(e: any) => setFormData({ ...formData, code: e.target.value })}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>
                Proveedor
              </label>
              <select
                value={formData.supplier_id}
                onChange={(e) => setFormData({ ...formData, supplier_id: e.target.value })}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)' }}
              >
                <option value="">Proveedor General</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>{s.commercial_name}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>
                Rendimiento a Unidad Base ({selectedItemObj?.unit_code || 'Unidad'})
              </label>
              <Input
                type="number"
                step="0.001"
                value={formData.base_unit_yield}
                placeholder="Ej. 0.45, 3.35, 1.0"
                onChange={(e: any) => setFormData({ ...formData, base_unit_yield: e.target.value })}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>
                Precio de Compra Neto ($ MXN)
              </label>
              <Input
                type="number"
                step="0.01"
                value={formData.last_net_price}
                placeholder="Ej. 91.05, 135.00"
                onChange={(e: any) => setFormData({ ...formData, last_net_price: e.target.value })}
              />
            </div>
          </div>

          <div style={{ padding: 12, borderRadius: 8, background: 'rgba(34, 197, 94, 0.08)', border: '1px solid rgba(34, 197, 94, 0.2)' }}>
            <p style={{ margin: 0, fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-green)' }}>
              Costo Unitario Calculado: ${calculatedCostPerBase.toFixed(4)} / {selectedItemObj?.unit_code || 'unidad'}
            </p>
            <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              Este costo unitario se usará automáticamente en las recetas y para valorar las existencias del almacén al recibir compras.
            </p>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => saveMutation.mutate(formData)}
              disabled={saveMutation.isPending || !formData.name || !formData.item_id}
            >
              {editingItem ? "Guardar Cambios" : "Crear Presentación"}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default PresentationsList;
