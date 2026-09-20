import React, { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import {
  Plus,
  Carrot,
  Edit,
  Printer,
  Save,
  Undo2,
  BookOpen,
  Sliders,
  Search,
} from 'lucide-react';

import '../../premium-catalogs.css';
import './InsumosWindow.css';
import { readAdminAiSelection } from '../admin-ai/adminAiSelection';
import { resolveBranchId } from '../../lib/branchContext';
import { RecipeUsagesModal } from '../admin-catalog/RecipeUsagesModal';

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
  category_name?: string;
  catalog_scope?: 'organization' | 'branch';
  last_unit_cost?: number | string;
  average_unit_cost?: number | string;
}

interface Unit {
  id: string;
  code: string;
  name: string;
  dimension?: string;
}

interface Category {
  id: string;
  name: string;
  display_order: number;
  status: string;
}

interface PurchasePresentation {
  id: string;
  code: string;
  name: string;
  item_id: string;
  supplier_id?: string;
  supplier_name?: string;
  base_unit_yield: number | string;
  base_unit_code?: string;
  last_net_price: number | string;
  cost_per_base_unit?: number | string;
  tax_rate?: number | string;
  status?: string;
}

interface Supplier {
  id: string;
  commercial_name: string;
}

// Error Boundary to completely protect against white-screen unmounts
class InsumosErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('InsumosErrorBoundary caught error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, border: '2px solid #ef4444', background: '#fef2f2', borderRadius: 8, margin: 20 }}>
          <h2 style={{ color: '#b91c1c', margin: '0 0 8px' }}>Error al cargar la vista de Insumos</h2>
          <p style={{ color: '#7f1d1d', margin: '0 0 16px', fontSize: '0.9rem' }}>
            {this.state.error?.message || 'Ocurrió un error inesperado al renderizar el catálogo.'}
          </p>
          <button
            type="button"
            style={{ padding: '8px 16px', background: '#b91c1c', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
          >
            Reintentar recarga
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// Safe number formatter helper to never throw on string, Decimal, null or undefined
const formatMoney = (val: unknown): string => {
  if (val === null || val === undefined) return '0.00';
  const num = typeof val === 'number' ? val : parseFloat(String(val));
  return isNaN(num) ? '0.00' : num.toFixed(2);
};

const InsumosView = () => {
  const branchId = resolveBranchId();
  const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : '';
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Selection & Mode State
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<string>('(TODOS)');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [isNew, setIsNew] = useState<boolean>(false);

  // Modals State
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [isUnitModalOpen, setIsUnitModalOpen] = useState(false);
  const [isPresentationModalOpen, setIsPresentationModalOpen] = useState(false);
  const [usageItem, setUsageItem] = useState<Item | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    sku: '',
    category_name: '',
    base_unit_id: '',
    item_type: 'ingredient',
    status: 'active',
    tax_rate: '16.00',
    waste_rate: '0',
    is_inventoriable: true,
    use_scale: false,
  });

  // Modal Subordinate Form States
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newUnitCode, setNewUnitCode] = useState('');
  const [newUnitName, setNewUnitName] = useState('');
  const [newPresentation, setNewPresentation] = useState({
    code: '',
    name: '',
    supplier_id: '',
    base_unit_yield: '1',
    last_net_price: '0',
    tax_rate: '0.16',
  });

  // Queries with safe catch-blocks to prevent unhandled 403 or network exceptions
  const { data: rawItems = [], isLoading, error } = useQuery<Item[]>({
    queryKey: ['inventory', 'items', branchId],
    queryFn: () => fetchApi<Item[]>(`/inventory/items${query}`).catch(() => []),
  });

  const { data: rawUnits = [] } = useQuery<Unit[]>({
    queryKey: ['inventory', 'units'],
    queryFn: () => fetchApi<Unit[]>('/inventory/units').catch(() => []),
  });

  const { data: rawCategories = [] } = useQuery<Category[]>({
    queryKey: ['categories'],
    queryFn: () => fetchApi<Category[]>('/categories').catch(() => []),
    retry: false,
  });

  const { data: rawPresentations = [] } = useQuery<PurchasePresentation[]>({
    queryKey: ['purchase-presentations'],
    queryFn: () => fetchApi<PurchasePresentation[]>('/purchase-presentations').catch(() => []),
    retry: false,
  });

  const { data: rawSuppliers = [] } = useQuery<Supplier[]>({
    queryKey: ['suppliers'],
    queryFn: () => fetchApi<Supplier[]>('/suppliers').catch(() => []),
    retry: false,
  });

  // Array safety wrappers
  const items = useMemo(() => (Array.isArray(rawItems) ? rawItems : []), [rawItems]);
  const units = useMemo(() => (Array.isArray(rawUnits) ? rawUnits : []), [rawUnits]);
  const categories = useMemo(() => (Array.isArray(rawCategories) ? rawCategories : []), [rawCategories]);
  const presentations = useMemo(() => (Array.isArray(rawPresentations) ? rawPresentations : []), [rawPresentations]);
  const suppliers = useMemo(() => (Array.isArray(rawSuppliers) ? rawSuppliers : []), [rawSuppliers]);

  // Admin AI Selection filter support
  const assistantSelectionId = searchParams.get('admin_ai_selection');
  const assistantSelection = useMemo(
    () => readAdminAiSelection(assistantSelectionId),
    [assistantSelectionId],
  );

  const clearAssistantSelection = () => {
    if (assistantSelectionId) sessionStorage.removeItem(`admin-ai-selection:${assistantSelectionId}`);
    const next = new URLSearchParams(searchParams);
    next.delete('admin_ai_selection');
    setSearchParams(next, { replace: true });
  };

  // Filtered Items for Master table
  const visibleItems = useMemo(() => {
    let result = items;
    if (assistantSelection && Array.isArray(assistantSelection.item_ids)) {
      result = result.filter((item) => item && assistantSelection.item_ids.includes(item.id));
    }
    if (selectedGroup !== '(TODOS)') {
      result = result.filter((item) => (item?.category_name || '').toUpperCase() === selectedGroup.toUpperCase());
    }
    if (searchTerm.trim()) {
      const q = searchTerm.trim().toLowerCase();
      result = result.filter(
        (item) =>
          (item?.name || '').toLowerCase().includes(q) ||
          (item?.sku || '').toLowerCase().includes(q)
      );
    }
    return result;
  }, [items, assistantSelection, selectedGroup, searchTerm]);

  // Selected item reference
  const selectedItem = useMemo(() => {
    if (selectedItemId) {
      const found = items.find((i) => i && i.id === selectedItemId);
      if (found) return found;
    }
    return visibleItems.length > 0 ? visibleItems[0] : null;
  }, [items, selectedItemId, visibleItems]);

  // Synchronize form when selectedItem changes (unless editing)
  useEffect(() => {
    if (!isEditing && selectedItem) {
      setFormData({
        name: selectedItem.name || '',
        sku: selectedItem.sku || '',
        category_name: selectedItem.category_name || '',
        base_unit_id: selectedItem.base_unit_id || '',
        item_type: selectedItem.item_type || 'ingredient',
        status: selectedItem.status || 'active',
        tax_rate: '16.00',
        waste_rate: '0',
        is_inventoriable: true,
        use_scale: false,
      });
    }
  }, [selectedItem, isEditing]);

  // Linked Purchase Presentations for Selected Item
  const itemPresentations = useMemo(() => {
    if (!selectedItem) return [];
    return presentations.filter((p) => p && p.item_id === selectedItem.id);
  }, [presentations, selectedItem]);

  // Distinct groups/categories list for filter dropdown
  const categoryOptions = useMemo(() => {
    const names = new Set<string>();
    categories.forEach((c) => {
      if (c && typeof c.name === 'string' && c.name.trim()) {
        names.add(c.name.trim().toUpperCase());
      }
    });
    items.forEach((i) => {
      if (i && typeof i.category_name === 'string' && i.category_name.trim()) {
        names.add(i.category_name.trim().toUpperCase());
      }
    });
    return Array.from(names).sort();
  }, [categories, items]);

  // Item Save Mutation
  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      if (isEditing && !isNew && selectedItem) {
        return fetchApi(`/inventory/items/${selectedItem.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            name: data.name,
            category_name: data.category_name,
            base_unit_id: data.base_unit_id,
            item_type: data.item_type,
            status: data.status,
          }),
        });
      }
      return fetchApi('/inventory/items', {
        method: 'POST',
        body: JSON.stringify({
          name: data.name,
          sku: data.sku,
          category_name: data.category_name,
          base_unit_id: data.base_unit_id,
          item_type: data.item_type,
        }),
      });
    },
    onSuccess: (saved: any) => {
      queryClient.invalidateQueries({ queryKey: ['inventory', 'items'] });
      setIsEditing(false);
      setIsNew(false);
      if (saved?.id) setSelectedItemId(saved.id);
    },
  });

  // Quick Category Mutation
  const categoryMutation = useMutation({
    mutationFn: (name: string) =>
      fetchApi('/categories', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim().toUpperCase(), display_order: 0 }),
      }),
    onSuccess: (cat: any) => {
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      setFormData((prev) => ({ ...prev, category_name: cat?.name || newCategoryName.toUpperCase() }));
      setNewCategoryName('');
      setIsCategoryModalOpen(false);
    },
  });

  // Quick Unit Mutation
  const unitMutation = useMutation({
    mutationFn: (unitData: { code: string; name: string }) =>
      fetchApi('/inventory/units', {
        method: 'POST',
        body: JSON.stringify({
          code: unitData.code.trim().toUpperCase(),
          name: unitData.name.trim().toUpperCase(),
          precision_scale: 2,
          dimension: 'discrete',
        }),
      }),
    onSuccess: (unit: any) => {
      queryClient.invalidateQueries({ queryKey: ['inventory', 'units'] });
      if (unit?.id) {
        setFormData((prev) => ({ ...prev, base_unit_id: unit.id }));
      }
      setNewUnitCode('');
      setNewUnitName('');
      setIsUnitModalOpen(false);
    },
  });

  // Quick Presentation Mutation
  const presentationMutation = useMutation({
    mutationFn: () => {
      if (!selectedItem) throw new Error('No hay insumo seleccionado');
      const payload = {
        item_id: selectedItem.id,
        supplier_id: newPresentation.supplier_id || undefined,
        code: newPresentation.code,
        name: newPresentation.name,
        base_unit_yield: parseFloat(newPresentation.base_unit_yield) || 1.0,
        usable_content: parseFloat(newPresentation.base_unit_yield) || 1.0,
        last_net_price: parseFloat(newPresentation.last_net_price) || 0.0,
        tax_rate: parseFloat(newPresentation.tax_rate) || 0.16,
      };
      return fetchApi('/purchase-presentations', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-presentations'] });
      setNewPresentation({
        code: '',
        name: '',
        supplier_id: '',
        base_unit_yield: '1',
        last_net_price: '0',
        tax_rate: '0.16',
      });
      setIsPresentationModalOpen(false);
    },
  });

  // Handlers for Toolbar Actions
  const handleNew = () => {
    setIsNew(true);
    setIsEditing(true);
    setFormData({
      name: '',
      sku: '',
      category_name: selectedGroup !== '(TODOS)' ? selectedGroup : '',
      base_unit_id: units?.[0]?.id || '',
      item_type: 'ingredient',
      status: 'active',
      tax_rate: '16.00',
      waste_rate: '0',
      is_inventoriable: true,
      use_scale: false,
    });
  };

  const handleEdit = () => {
    if (!selectedItem) return;
    setIsNew(false);
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setIsNew(false);
    if (selectedItem) {
      setFormData({
        name: selectedItem.name || '',
        sku: selectedItem.sku || '',
        category_name: selectedItem.category_name || '',
        base_unit_id: selectedItem.base_unit_id || '',
        item_type: selectedItem.item_type || 'ingredient',
        status: selectedItem.status || 'active',
        tax_rate: '16.00',
        waste_rate: '0',
        is_inventoriable: true,
        use_scale: false,
      });
    }
  };

  const handleSave = () => {
    if (!formData.name.trim() || !formData.base_unit_id) return;
    if (isNew && !formData.sku.trim()) return;
    saveMutation.mutate(formData);
  };

  const handlePrint = () => {
    window.print();
  };

  // Safe numerical calculations for costs (supporting number or string representations)
  const lastCost = typeof selectedItem?.last_unit_cost === 'number'
    ? selectedItem.last_unit_cost
    : parseFloat(String(selectedItem?.last_unit_cost ?? 0)) || 0;

  const avgCost = typeof selectedItem?.average_unit_cost === 'number'
    ? selectedItem.average_unit_cost
    : parseFloat(String(selectedItem?.average_unit_cost ?? 0)) || 0;

  const taxPct = parseFloat(formData.tax_rate) || 16.0;
  const costWithTax = lastCost * (1 + taxPct / 100);
  const wastePct = parseFloat(formData.waste_rate) || 0;
  const costWithWaste =
    wastePct > 0 && wastePct < 100 ? lastCost / (1 - wastePct / 100) : lastCost;

  return (
    <div className="insumos-window-container">
      {/* Header Bar styled like reference */}
      <div className="insumos-window-header">
        <div className="insumos-window-title">
          <Carrot size={18} />
          <span>Insumos</span>
        </div>
        <div className="insumos-window-controls">
          <button type="button" className="insumos-win-btn" title="Minimizar">_</button>
          <button type="button" className="insumos-win-btn" title="Maximizar">□</button>
          <button type="button" className="insumos-win-btn close" title="Cerrar">✕</button>
        </div>
      </div>

      {assistantSelection && (
        <div style={{ margin: '8px 12px 0', padding: 10, background: '#ecfdf5', border: '1px solid #10b981', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <strong>Revisión preparada por el asistente AI (admin_ai_selection)</strong>
            <p style={{ margin: 0, fontSize: '0.8rem', color: '#047857' }}>
              Mostrando {assistantSelection.item_ids.length} insumos seleccionados.
            </p>
          </div>
          <Button variant="secondary" onClick={clearAssistantSelection}>Ver todos los insumos</Button>
        </div>
      )}

      {/* Main Split Layout */}
      <div className="insumos-split-layout">
        {/* Left Column: Master Table */}
        <div className="insumos-master-panel">
          <div className="insumos-master-controls">
            <select
              className="insumos-filter-select"
              value={selectedGroup}
              onChange={(e) => setSelectedGroup(e.target.value)}
              title="Filtrar por Grupo"
            >
              <option value="(TODOS)">(TODOS)</option>
              {categoryOptions.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>

            <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
              <Search size={14} color="#64748b" />
              <input
                type="text"
                className="insumos-search-input"
                placeholder="Buscar clave o descripción..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            <button
              type="button"
              className="insumos-btn-print"
              onClick={handlePrint}
              title="Imprimir catálogo de insumos"
            >
              <Printer size={14} />
              <span>Imprimir</span>
            </button>
          </div>

          <div className="insumos-master-table-wrap">
            {isLoading ? (
              <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>Cargando catálogo...</div>
            ) : error ? (
              <div style={{ padding: 24, textAlign: 'center', color: '#ef4444' }}>Error al consultar insumos.</div>
            ) : visibleItems.length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>No hay insumos registrados.</div>
            ) : (
              <table className="insumos-table">
                <thead>
                  <tr>
                    <th style={{ width: '85px' }}>Clave</th>
                    <th>Descripción</th>
                    <th style={{ width: '90px', textAlign: 'right' }}>Costo</th>
                    <th style={{ width: '75px' }}>Unidad</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleItems.map((item) => {
                    const isSelected = selectedItem?.id === item.id;
                    return (
                      <tr
                        key={item.id}
                        className={isSelected ? 'active' : ''}
                        onClick={() => {
                          setSelectedItemId(item.id);
                          if (isEditing && isNew) {
                            setIsEditing(false);
                            setIsNew(false);
                          }
                        }}
                      >
                        <td style={{ fontFamily: 'monospace' }}>{item.sku || '—'}</td>
                        <td>{item.name || 'Sin nombre'}</td>
                        <td style={{ textAlign: 'right' }}>
                          ${formatMoney(item.last_unit_cost)}
                        </td>
                        <td>{item.unit_name || item.unit_code || 'N/A'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right Column: Detail & Sub-Catalogs */}
        <div className="insumos-detail-panel">
          {/* Action Toolbar */}
          <div className="insumos-toolbar">
            <button
              type="button"
              className="insumos-action-btn"
              onClick={handleNew}
              disabled={isEditing && isNew}
            >
              <Plus size={14} />
              <span>Nuevo</span>
            </button>

            <button
              type="button"
              className={`insumos-action-btn ${isEditing ? 'save-highlight' : ''}`}
              onClick={handleSave}
              disabled={!isEditing || saveMutation.isPending}
            >
              <Save size={14} />
              <span>{saveMutation.isPending ? 'Guardando...' : 'Guardar'}</span>
            </button>

            <button
              type="button"
              className="insumos-action-btn"
              onClick={handleCancel}
              disabled={!isEditing}
            >
              <Undo2 size={14} />
              <span>Deshacer</span>
            </button>

            <button
              type="button"
              className="insumos-action-btn"
              onClick={handleEdit}
              disabled={isEditing || !selectedItem}
            >
              <Edit size={14} />
              <span>Editar</span>
            </button>

            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
              {isNew ? (
                <Badge variant="warning">Nuevo Insumo</Badge>
              ) : isEditing ? (
                <Badge variant="info">Modo Edición</Badge>
              ) : (
                <Badge variant="default">Consulta</Badge>
              )}
            </div>
          </div>

          {/* Form Detail */}
          <div className="insumos-detail-form">
            {/* Grupo with [+] button */}
            <div className="insumos-form-row">
              <label className="insumos-form-label">Grupo:</label>
              <select
                className="insumos-form-select"
                style={{ flex: 1, maxWidth: 300 }}
                value={formData.category_name}
                disabled={!isEditing}
                onChange={(e) => setFormData({ ...formData, category_name: e.target.value })}
              >
                <option value="">(Sin clasificar)</option>
                {categoryOptions.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="insumos-btn-plus"
                title="Nuevo Grupo / Categoría"
                onClick={() => setIsCategoryModalOpen(true)}
              >
                +
              </button>
            </div>

            {/* Clave / SKU */}
            <div className="insumos-form-row">
              <label className="insumos-form-label">Clave:</label>
              <input
                type="text"
                className="insumos-form-input"
                style={{ width: 180 }}
                value={formData.sku}
                disabled={!isEditing || (!isNew && Boolean(selectedItem))}
                onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                placeholder="SKU o Código"
              />
            </div>

            {/* Descripción / Nombre */}
            <div className="insumos-form-row">
              <label className="insumos-form-label">Descripción:</label>
              <input
                type="text"
                className="insumos-form-input"
                style={{ flex: 1, minWidth: 240 }}
                value={formData.name}
                disabled={!isEditing}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Nombre del insumo (ej. POLLO)"
              />
            </div>

            {/* Unidad de Medida with [+] button */}
            <div className="insumos-form-row">
              <label className="insumos-form-label">Unidad de medida:</label>
              <select
                className="insumos-form-select"
                style={{ flex: 1, maxWidth: 300 }}
                value={formData.base_unit_id}
                disabled={!isEditing}
                onChange={(e) => setFormData({ ...formData, base_unit_id: e.target.value })}
              >
                <option value="">Selecciona unidad</option>
                {units.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.code})
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="insumos-btn-plus"
                title="Nueva Unidad de Medida"
                onClick={() => setIsUnitModalOpen(true)}
              >
                +
              </button>
            </div>

            {/* Financial / Cost Breakdown Box (Derived from receipts, strictly read-only) */}
            <div className="insumos-cost-box">
              <div className="insumos-cost-cell">
                <span className="insumos-cost-label">Último costo:</span>
                <input
                  type="text"
                  readOnly
                  className="insumos-form-input readonly-cost"
                  value={`$${formatMoney(lastCost)}`}
                />
              </div>

              <div className="insumos-cost-cell">
                <span className="insumos-cost-label">Costo promedio:</span>
                <input
                  type="text"
                  readOnly
                  className="insumos-form-input readonly-cost"
                  value={`$${formatMoney(avgCost)}`}
                />
              </div>

              <div className="insumos-cost-cell">
                <span className="insumos-cost-label">IVA:</span>
                <input
                  type="text"
                  className="insumos-form-input"
                  style={{ textAlign: 'right' }}
                  value={`${formData.tax_rate} %`}
                  disabled={!isEditing}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      tax_rate: e.target.value.replace(/[^0-9.]/g, ''),
                    })
                  }
                />
              </div>

              <div className="insumos-cost-cell">
                <span className="insumos-cost-label">Costo c/ impuestos:</span>
                <input
                  type="text"
                  readOnly
                  className="insumos-form-input readonly-cost"
                  value={`$${formatMoney(costWithTax)}`}
                />
              </div>
            </div>

            {/* Inventariable, Báscula y Umbrales */}
            <div className="insumos-features-row">
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <label className="insumos-form-label" style={{ width: 'auto' }}>Inventariable:</label>
                <select
                  className="insumos-form-select"
                  disabled={!isEditing}
                  value={formData.is_inventoriable ? 'SI' : 'NO'}
                  onChange={(e) =>
                    setFormData({ ...formData, is_inventoriable: e.target.value === 'SI' })
                  }
                >
                  <option value="SI">SI</option>
                  <option value="NO">NO</option>
                </select>
              </div>

              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.825rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  disabled={!isEditing}
                  checked={formData.use_scale}
                  onChange={(e) => setFormData({ ...formData, use_scale: e.target.checked })}
                />
                <span>Usar báscula en inventarios</span>
              </label>

              <button
                type="button"
                className="insumos-feature-btn"
                onClick={() => navigate('/inventory/thresholds')}
                title="Configurar mínimos y máximos en almacén"
              >
                <Sliders size={14} />
                <span>Alerta de existencias (Umbrales)</span>
              </button>
            </div>

            {/* Merma & Usos en Recetas */}
            <div className="insumos-features-row">
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>% de merma:</span>
                <input
                  type="text"
                  style={{ width: 60, textAlign: 'right' }}
                  className="insumos-form-input"
                  value={`${formData.waste_rate} %`}
                  disabled={!isEditing}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      waste_rate: e.target.value.replace(/[^0-9.]/g, ''),
                    })
                  }
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Último costo c/ merma:</span>
                <strong style={{ fontSize: '0.85rem' }}>${formatMoney(costWithWaste)}</strong>
              </div>

              {selectedItem && (
                <button
                  type="button"
                  className="insumos-feature-btn"
                  onClick={() => setUsageItem(selectedItem)}
                  title="Ver en qué recetas se utiliza este insumo (PRD-FR-240)"
                >
                  <BookOpen size={14} />
                  <span>Recetas con este insumo</span>
                </button>
              )}
            </div>

            {/* Presentaciones Sub-table */}
            <div className="insumos-presentations-panel">
              <div className="insumos-presentations-header">
                <span>Presentaciones de compra vinculadas:</span>
                {selectedItem && (
                  <button
                    type="button"
                    className="insumos-btn-plus"
                    style={{ width: 22, height: 22 }}
                    title="Agregar presentación para este insumo"
                    onClick={() => setIsPresentationModalOpen(true)}
                  >
                    +
                  </button>
                )}
              </div>

              <div className="insumos-presentations-table-wrap">
                {itemPresentations.length === 0 ? (
                  <div style={{ padding: 12, textAlign: 'center', fontSize: '0.8rem', color: '#64748b' }}>
                    Sin presentaciones registradas. Presiona [+] para vincular una presentación de compra.
                  </div>
                ) : (
                  <table className="insumos-table">
                    <thead>
                      <tr>
                        <th>Clave</th>
                        <th>Descripción</th>
                        <th style={{ textAlign: 'right' }}>Rendimiento</th>
                        <th>Unidad</th>
                        <th style={{ textAlign: 'right' }}>Costo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {itemPresentations.map((p) => (
                        <tr key={p.id}>
                          <td style={{ fontFamily: 'monospace' }}>{p.code || '—'}</td>
                          <td>{p.name || 'Sin descripción'}</td>
                          <td style={{ textAlign: 'right' }}>{p.base_unit_yield ?? '1'}</td>
                          <td>{p.base_unit_code || selectedItem?.unit_code || 'U'}</td>
                          <td style={{ textAlign: 'right' }}>${formatMoney(p.last_net_price)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Modal: Quick Category Add */}
      <Modal
        isOpen={isCategoryModalOpen}
        onClose={() => setIsCategoryModalOpen(false)}
        title="Nuevo Grupo / Categoría"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600, fontSize: '0.875rem' }}>
              Nombre del Grupo (Mayúsculas):
            </label>
            <Input
              value={newCategoryName}
              placeholder="Ej. ABARROTE, CARNES, LACTEOS"
              onChange={(e: any) => setNewCategoryName(e.target.value.toUpperCase())}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
            <Button variant="secondary" onClick={() => setIsCategoryModalOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={!newCategoryName.trim() || categoryMutation.isPending}
              onClick={() => categoryMutation.mutate(newCategoryName)}
            >
              {categoryMutation.isPending ? 'Guardando...' : 'Crear Grupo'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal: Quick Unit Add */}
      <Modal
        isOpen={isUnitModalOpen}
        onClose={() => setIsUnitModalOpen(false)}
        title="Nueva Unidad de Medida Base"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600, fontSize: '0.875rem' }}>
              Código / Símbolo (Ej. KG, LT, PZA):
            </label>
            <Input
              value={newUnitCode}
              placeholder="Símbolo oficial"
              onChange={(e: any) => setNewUnitCode(e.target.value.toUpperCase())}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600, fontSize: '0.875rem' }}>
              Nombre de la Unidad (Ej. KILO, LITRO, PIEZA):
            </label>
            <Input
              value={newUnitName}
              placeholder="Nombre descriptivo"
              onChange={(e: any) => setNewUnitName(e.target.value.toUpperCase())}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
            <Button variant="secondary" onClick={() => setIsUnitModalOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={!newUnitCode.trim() || !newUnitName.trim() || unitMutation.isPending}
              onClick={() =>
                unitMutation.mutate({ code: newUnitCode, name: newUnitName })
              }
            >
              {unitMutation.isPending ? 'Guardando...' : 'Crear Unidad'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal: Quick Purchase Presentation Add */}
      <Modal
        isOpen={isPresentationModalOpen}
        onClose={() => setIsPresentationModalOpen(false)}
        title={`Nueva Presentación de Compra: ${selectedItem?.name || ''}`}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ fontSize: '0.85rem', color: '#64748b', margin: 0 }}>
            Insumo base: <strong>{selectedItem?.name}</strong> ({selectedItem?.unit_name || selectedItem?.unit_code})
          </p>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600, fontSize: '0.85rem' }}>
              Clave de Presentación:
            </label>
            <Input
              value={newPresentation.code}
              placeholder="Ej. CAJA-12, COSTAL-25KG"
              onChange={(e: any) =>
                setNewPresentation({ ...newPresentation, code: e.target.value.toUpperCase() })
              }
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600, fontSize: '0.85rem' }}>
              Descripción del Empaque:
            </label>
            <Input
              value={newPresentation.name}
              placeholder="Ej. Costal de 25 kg marca San Marcos"
              onChange={(e: any) =>
                setNewPresentation({ ...newPresentation, name: e.target.value })
              }
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600, fontSize: '0.85rem' }}>
              Proveedor habitual:
            </label>
            <select
              style={{ width: '100%', padding: '8px 10px', borderRadius: 4, border: '1px solid #cbd5e1' }}
              value={newPresentation.supplier_id}
              onChange={(e) =>
                setNewPresentation({ ...newPresentation, supplier_id: e.target.value })
              }
            >
              <option value="">(Sin proveedor específico)</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.commercial_name}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 600, fontSize: '0.85rem' }}>
                Rendimiento ({selectedItem?.unit_code || 'unidades base'}):
              </label>
              <Input
                type="number"
                step="any"
                value={newPresentation.base_unit_yield}
                onChange={(e: any) =>
                  setNewPresentation({ ...newPresentation, base_unit_yield: e.target.value })
                }
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 600, fontSize: '0.85rem' }}>
                Último precio neto ($):
              </label>
              <Input
                type="number"
                step="any"
                value={newPresentation.last_net_price}
                onChange={(e: any) =>
                  setNewPresentation({ ...newPresentation, last_net_price: e.target.value })
                }
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
            <Button variant="secondary" onClick={() => setIsPresentationModalOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={
                !newPresentation.code.trim() ||
                !newPresentation.name.trim() ||
                presentationMutation.isPending
              }
              onClick={() => presentationMutation.mutate()}
            >
              {presentationMutation.isPending ? 'Guardando...' : 'Guardar Presentación'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Recipe Usages Modal (PRD-FR-240) */}
      {usageItem && branchId && (
        <RecipeUsagesModal
          item={usageItem}
          branchId={branchId}
          onClose={() => setUsageItem(null)}
        />
      )}
    </div>
  );
};

const ItemsList = () => (
  <InsumosErrorBoundary>
    <InsumosView />
  </InsumosErrorBoundary>
);

export default ItemsList;
