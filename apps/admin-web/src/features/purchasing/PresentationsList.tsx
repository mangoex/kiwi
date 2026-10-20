import { useAdminPermission } from '../../lib/adminSession';
import React, { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Button, Badge, Modal, Input, usePythonPreview } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Package, Search, Plus, Edit } from 'lucide-react';
import '../../premium-catalogs.css';
import { readAdminAiSelection } from '../admin-ai/adminAiSelection';
import { resolveBranchId } from '../../lib/branchContext';
import { formatRecipeDecimal, recipeCaptureError, rateToPercent, percentToRate } from '../catalog/recipeDecimal';
import './PresentationsList.css';

interface PurchasePresentation {
  id: string;
  code: string;
  name: string;
  item_id: string;
  item_name?: string;
  supplier_id: string;
  supplier_name?: string;
  package_type: string;
  base_unit_yield: string | number;
  base_unit_code?: string;
  last_net_price: string | number;
  cost_per_base_unit: string | number;
  tax_rate: string | number;
  commercial_unit_id: string;
  usable_content: string | number;
  status: string;
  updated_at: string;
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
  status: string;
}

type DecimalField = 'base_unit_yield' | 'usable_content' | 'last_net_price' | 'tax_rate';

const PresentationsList = () => {
  const canCreate = useAdminPermission('purchases.manage');
  const canEdit = useAdminPermission('admin.manage');
  const canReadInventory = useAdminPermission('inventory.read');
  const branchId = resolveBranchId();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<PurchasePresentation | null>(null);
  const [decimalInputs, setDecimalInputs] = useState<Partial<Record<DecimalField, string>>>({});

  const [formData, setFormData] = useState({
    item_id: '',
    supplier_id: '',
    code: '',
    name: '',
    base_unit_yield: '',
    usable_content: '',
    commercial_unit_id: '',
    last_net_price: '0',
    tax_rate: '0',
  });

  const { data: presentations = [], isLoading, error } = useQuery<PurchasePresentation[]>({
    queryKey: ['purchase-presentations', branchId],
    queryFn: () => fetchApi('/purchase-presentations?branch_id=' + branchId),
  });

  const { data: items = [] } = useQuery<InventoryItem[]>({
    queryKey: ['inventory', 'items', branchId],
    queryFn: () => fetchApi('/inventory/items?branch_id=' + branchId),
    enabled: canReadInventory,
  });

  const { data: suppliers = [], error: supplierError } = useQuery<Supplier[]>({
    queryKey: ['suppliers', branchId],
    queryFn: () => fetchApi('/suppliers?branch_id=' + branchId),
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
        supplier_id: data.supplier_id,
        branch_id: branchId,
        base_unit_id: items.find(item => item.id === data.item_id)?.base_unit_id,
        commercial_unit_id: data.commercial_unit_id,
        code: data.code,
        name: data.name,
        base_unit_yield: data.base_unit_yield,
        usable_content: data.usable_content,
        last_net_price: data.last_net_price,
        tax_rate: data.tax_rate,
        ...(editingItem ? { expected_updated_at: editingItem.updated_at } : {}),
      };

      if (editingItem ? !canEdit : !canCreate) throw new Error('No tienes permiso para guardar esta presentación.');
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
    saveMutation.reset();
    setDecimalInputs({});
    setEditingItem(null);
    const defaultItem = items.find((item) => assistantItemIds.includes(item.id)) || items[0];
    setFormData({
      item_id: defaultItem ? defaultItem.id : '',
      supplier_id: '',
      commercial_unit_id: '',
      usable_content: '',
      code: defaultItem ? `PRES-${defaultItem.sku}` : '',
      name: defaultItem ? `${defaultItem.name} (Presentación)` : '',
      base_unit_yield: '',
      last_net_price: '0',
      tax_rate: '0',
    });
    setIsModalOpen(true);
  };

  const openEditModal = (pres: PurchasePresentation) => {
    saveMutation.reset();
    setDecimalInputs({});
    setEditingItem(pres);
    setFormData({
      item_id: pres.item_id,
      supplier_id: pres.supplier_id || '',
      code: pres.code,
      name: pres.name,
      base_unit_yield: String(pres.base_unit_yield),
      commercial_unit_id: pres.commercial_unit_id,
      usable_content: String(pres.usable_content),
      last_net_price: String(pres.last_net_price || '0'),
      tax_rate: String(pres.tax_rate ?? '0'),
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
      (p.supplier_name && p.supplier_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      p.code.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesAssistantSelection && matchesSearch;
  });

  const selectedItemObj = items.find((it) => it.id === formData.item_id);
  const { data: units = [], error: unitError } = useQuery<{ id: string; code: string }[]>({ queryKey: ['inventory-units'], queryFn: () => fetchApi('/inventory/units') });
  const captureError = Object.values(decimalInputs).map(recipeCaptureError).find(Boolean);
  const preview = usePythonPreview<{ cost_per_base_unit: string; content_cost_mismatch?: boolean }>(fetchApi, '/purchase-presentations/preview', { ...formData, branch_id: branchId, base_unit_id: selectedItemObj?.base_unit_id || '', ...(editingItem ? { presentation_id: editingItem.id } : {}) }, isModalOpen && !captureError);
  const calculatedCostPerBase = preview.data?.cost_per_base_unit;
  const decimalInput = (field: DecimalField, label: string) => (
    <label className="presentation-field" htmlFor={`presentation-${field}`}>
      {label}
      <Input id={`presentation-${field}`} inputMode="decimal"
        value={decimalInputs[field] ?? (formData[field] === '' ? '' : formatRecipeDecimal(field === 'tax_rate' ? rateToPercent(formData[field]) : formData[field]))}
        aria-invalid={!!recipeCaptureError(decimalInputs[field])}
        onChange={event => {
          const value = event.target.value;
          setDecimalInputs(previous => ({ ...previous, [field]: value }));
          setFormData(previous => ({ ...previous, [field]: field === 'tax_rate' ? percentToRate(value) : value.replace(',', '.') }));
        }} />
    </label>
  );

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 className="premium-header-title">Presentaciones de Compra</h1>
          <p className="premium-header-subtitle">
            Formatos comerciales de compra por proveedor, factor de rendimiento y costo unitario resultante.
          </p>
        </div>
        {canCreate && canReadInventory && <button className="premium-add-btn" onClick={openCreateModal}>
          <Plus size={18} />
          Nueva Presentación
        </button>}
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
              {canCreate && canReadInventory && <Button onClick={openCreateModal}><Plus size={16} /> Nueva presentación</Button>}
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
            {assistantSelection && (canCreate && canReadInventory ? <Button onClick={openCreateModal}><Plus size={16} /> Crear presentación</Button> : null)}
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
                        <div><span>{item.name}</span><small className="presentation-supplier-name">{item.supplier_name}</small></div>
                      </div>
                    </td>
                    <td>{item.item_name || 'Insumo Base'}</td>
                    <td style={{ textAlign: 'right', fontWeight: 500 }}>
                      {formatRecipeDecimal(item.base_unit_yield)} {item.base_unit_code || 'UNIDAD'}
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--color-text)' }}>
                      ${formatRecipeDecimal(item.last_net_price)}
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--color-green)' }}>
                      ${formatRecipeDecimal(item.cost_per_base_unit)} / {item.base_unit_code || 'u'}
                    </td>
                    <td>
                      <Badge variant={item.status === 'active' ? 'success' : 'default'}>
                        {item.status === 'active' ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {canEdit && <button className="premium-action-btn edit" onClick={() => openEditModal(item)} title="Editar presentación" aria-label={`Editar ${item.name}`}>
                        <Edit size={16} />
                      </button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} size="lg" contentClassName="presentation-editor" title={editingItem ? "Editar Presentación de Compra" : "Nueva Presentación de Compra"}>
        <div className="presentation-form">
          <p className="presentation-help">Asigna el proveedor y el empaque de compra. El insumo conserva su unidad base; las compras anteriores conservan sus datos originales.</p>
          <div className="presentation-field"><label htmlFor="presentation-item">Insumo base</label>
            <select id="presentation-item" value={formData.item_id} onChange={event => onItemChange(event.target.value)} disabled={!!editingItem}>
              <option value="">Selecciona insumo</option>
              {items.map(item => <option key={item.id} value={item.id}>{item.sku} · {item.name} ({item.unit_code || item.unit_name})</option>)}
            </select>
          </div>
          <label className="presentation-field" htmlFor="presentation-name">Nombre de la presentación comercial
            <Input id="presentation-name" value={formData.name} onChange={event => setFormData({ ...formData, name: event.target.value })} />
          </label>
          <div className="presentation-grid">
            <label className="presentation-field" htmlFor="presentation-code">Clave / Código
              <Input id="presentation-code" value={formData.code} disabled={!!editingItem} onChange={event => setFormData({ ...formData, code: event.target.value })} />
            </label>
            <div className="presentation-field"><label htmlFor="presentation-supplier">Proveedor</label>
              <select id="presentation-supplier" value={formData.supplier_id} onChange={event => setFormData({ ...formData, supplier_id: event.target.value })}>
                <option value="">Selecciona proveedor</option>
                {suppliers.filter(supplier => supplier.status === 'active').map(supplier => <option key={supplier.id} value={supplier.id}>{supplier.commercial_name}</option>)}
              </select>
            </div>
            <div className="presentation-field"><label htmlFor="presentation-unit">Unidad comercial</label>
              <select id="presentation-unit" aria-describedby="presentation-unit-help" value={formData.commercial_unit_id} onChange={event => setFormData({ ...formData, commercial_unit_id: event.target.value })}>
                <option value="">Selecciona unidad</option>
                {units.map(unit => <option key={unit.id} value={unit.id}>{unit.code}</option>)}
              </select>
              <span id="presentation-unit-help" className="presentation-help">El empaque que compras, por ejemplo frasco o caja.</span>
            </div>
            {decimalInput('base_unit_yield', `Rendimiento a unidad base (${selectedItemObj?.unit_code || 'unidad'})`)}
            {decimalInput('usable_content', `Contenido útil (${selectedItemObj?.unit_code || 'unidad'})`)}
            {decimalInput('last_net_price', 'Precio de compra neto ($ MXN)')}
            {decimalInput('tax_rate', 'Impuesto (%)')}
          </div>
          {preview.data?.content_cost_mismatch && <div className="presentation-warning" role="status">
            <strong>Revisa el contenido heredado</strong>
            <p>El contenido útil no corresponde al costo guardado. Asignar proveedor conserva ese costo. Verifica cuánto aporta realmente cada empaque antes de cambiar cantidades.</p>
            <Button variant="secondary" onClick={() => {
              setFormData(previous => ({ ...previous, usable_content: previous.base_unit_yield }));
              setDecimalInputs(previous => { const next = { ...previous }; delete next.usable_content; return next; });
            }}>Usar rendimiento como contenido útil</Button>
          </div>}
          {(supplierError || unitError) && <p role="alert">No pudimos cargar proveedores o unidades. Cierra el editor y vuelve a intentarlo.</p>}
          {(captureError || saveMutation.error || preview.error) && <p role="alert">{captureError || saveMutation.error?.message || preview.error}</p>}
          <div className="presentation-cost" aria-live="polite">
            <span>Costo por unidad base al guardar</span>
            <strong>{calculatedCostPerBase !== undefined ? `$${formatRecipeDecimal(calculatedCostPerBase)} / ${selectedItemObj?.unit_code || 'unidad'}` : 'Calculando…'}</strong>
            <p className="presentation-help">Costo informativo del catálogo. La recepción confirma el costo de inventario; las recetas conservan su versión y fuente de costeo.</p>
          </div>
          <div className="presentation-actions">
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>Cancelar</Button>
            {(editingItem ? canEdit : canCreate) && <Button variant="primary" onClick={() => saveMutation.mutate(formData)} disabled={saveMutation.isPending || !!captureError || !!supplierError || !!unitError || !formData.name.trim() || !formData.item_id || !formData.supplier_id || !formData.commercial_unit_id || !preview.data}>
              {saveMutation.isPending ? 'Guardando…' : editingItem ? 'Guardar Cambios' : 'Crear Presentación'}
            </Button>}
          </div>
        </div>
      </Modal>
    </>
  );
};

export default PresentationsList;
