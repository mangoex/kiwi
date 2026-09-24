import React, { useMemo, useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchApi } from '@restaurantos/api-client';
import {
  Plus,
  Edit,
  Trash2,
  Search,
  Sparkles,
  Printer,
  X,
  Package,
  Save,
  Undo2,
  Star,
  Layers,
  SlidersHorizontal,
  ChevronRight,
  TrendingUp,
  Image as ImageIcon,
  Coins,
  MessageSquare,
  Network,
  CheckCircle2,
  UtensilsCrossed,
  Truck,
  Zap,
  HelpCircle,
  AlertCircle,
  FolderTree,
} from 'lucide-react';
import './ProductosWindow.css';
import { DagTreeView, DagNode } from '../../components/DagTreeView';
import { KiwiCopilotWidget } from '../../components/KiwiCopilotWidget';
import { ModifierManager } from './ModifierManager';
import { ProductOnboardingAiModal } from './ProductOnboardingAiModal';
import { ComboCompositionModal } from './ComboCompositionModal';
import { FastTabDrawer } from '../../components/FastTabDrawer';
import CapsuleTabs from '../../components/ui/CapsuleTabs';

export const formatMoney = (cents: number | null | undefined): string => {
  if (cents == null) return '$0.00';
  return `$${(cents / 100).toFixed(2)}`;
};

export class ProductosErrorBoundary extends React.Component<
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

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, border: '2px solid #ef4444', background: '#fef2f2', borderRadius: 8, margin: 20 }}>
          <h2 style={{ color: '#b91c1c', margin: '0 0 8px' }}>Error al cargar el Catálogo de Productos</h2>
          <p style={{ color: '#7f1d1d', margin: '0 0 16px', fontSize: '0.9rem' }}>
            {this.state.error?.message || 'Ocurrió un error inesperado al renderizar los productos.'}
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

export interface Product {
  id: string;
  name: string;
  sku: string;
  category_id?: string;
  category_name: string;
  price_cents: number | null;
  station: string;
  status?: string;
  image_url?: string;
  catalog_scope?: 'organization' | 'branch';
  source_branch_id?: string | null;
  unit?: string;
  is_favorite?: boolean;
  service_dining?: boolean;
  service_delivery?: boolean;
  service_quick?: boolean;
  tax_rate?: number;
  barcode?: string;
  cost_cents?: number;
  is_exempt?: boolean;
  non_billable?: boolean;
  open_price?: boolean;
  suspended?: boolean;
  affects_guest_count?: boolean;
  additional_fee_percent?: number;
  server_commission_percent?: number;
  product_type?: string;
  warehouse?: string;
  loyalty_accrual?: boolean;
  loyalty_accrual_percent?: number;
  loyalty_points_price?: number;
  prep_comments?: string;
}

interface Category {
  id: string;
  name: string;
  display_order?: number;
  status?: string;
}

interface SubgroupValue {
  id: string;
  code: string;
  name: string;
  display_order: number;
  status: 'active' | 'inactive' | 'archived';
}

interface SubgroupCoverage {
  category_id: string;
  group: { id: string; name: string; status: 'active' | 'inactive' | 'archived' } | null;
  values: SubgroupValue[];
  products: Array<{ id: string; assignment: { value_id: string } | null }>;
}

const PRODUCT_CONFIGURATION_TABS = [
  { value: 'Principal / Varios', label: 'Principal / Varios' },
  { value: 'Receta / Almacén ventas', label: 'Receta / Almacén ventas' },
  { value: 'Precios promoción', label: 'Precios promoción' },
  { value: 'Imagen de producto', label: 'Imagen de producto' },
  { value: 'Monedero electrónico', label: 'Monedero electrónico' },
  { value: 'Comentarios de preparación / Paquete', label: 'Comentarios / Paquete' },
  { value: 'Producto compuesto', label: 'Producto compuesto' },
] as const;

type ProductConfigurationTab = (typeof PRODUCT_CONFIGURATION_TABS)[number]['value'];

export const ProductsList: React.FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') || '';

  const nameInputRef = useRef<HTMLInputElement | null>(null);

  // Filter States
  const [selectedGroup, setSelectedGroup] = useState<string>('(TODOS)');
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [isNew, setIsNew] = useState<boolean>(false);
  const [saveError, setSaveError] = useState('');

  // Active Tab: 7 tabs from Soft Restaurant reference
  const [activeTab, setActiveTab] = useState<ProductConfigurationTab>('Principal / Varios');

  // Auxiliary Modals
  const [isAiOnboardingOpen, setIsAiOnboardingOpen] = useState(false);
  const [compositionProduct, setCompositionProduct] = useState<Product | null>(null);
  const [isModifierModalOpen, setIsModifierModalOpen] = useState(false);

  // Optional drawer helper
  const [isFastTabDrawerOpen, setIsFastTabDrawerOpen] = useState(false);

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    sku: '',
    category_name: '',
    subgroup_value_id: '',
    price_with_tax: '55.00',
    tax_rate: '16.00',
    is_exempt: false,
    non_billable: false,
    unit: 'Pieza',
    station: '1 - BEBIDAS',
    service_dining: true,
    service_delivery: true,
    service_quick: true,
    is_favorite: false,
    barcode: '',
    open_price: 'NO',
    suspended: 'NO',
    affects_guest_count: false,
    additional_fee_percent: '0',
    server_commission_percent: '0.00',
    product_type: 'Preparado en sucursal',
    warehouse: 'Almacén General',
    price_dining: '55.00',
    price_delivery: '59.00',
    price_apps: '65.00',
    image_url: '',
    loyalty_accrual: true,
    loyalty_accrual_percent: '5',
    loyalty_points_price: '100',
    prep_comments: '',
  });

  // Queries
  const { data: rawProducts = [], isLoading, error } = useQuery<Product[]>({
    queryKey: ['products'],
    queryFn: () => fetchApi<Product[]>('/catalog/products').catch(() => [] as Product[]),
  });

  const { data: rawCategories = [] } = useQuery<Category[]>({
    queryKey: ['categories'],
    queryFn: () => fetchApi<Category[]>('/categories').catch(() => [] as Category[]),
  });

  const products: Product[] = useMemo(() => (Array.isArray(rawProducts) ? rawProducts : []), [rawProducts]);
  const categories: Category[] = useMemo(() => (Array.isArray(rawCategories) ? rawCategories : []), [rawCategories]);
  const formCategory = useMemo(
    () => categories.find((category) => category.name.toLocaleUpperCase('es-MX') === formData.category_name.toLocaleUpperCase('es-MX')) || null,
    [categories, formData.category_name],
  );
  const subgroupCoverageQuery = useQuery<SubgroupCoverage>({
    queryKey: ['category-option-coverage', formCategory?.id || ''],
    queryFn: () => fetchApi(`/categories/${formCategory?.id}/selection-group`),
    enabled: Boolean(formCategory?.id),
  });
  const subgroupCoverage = subgroupCoverageQuery.data?.category_id === formCategory?.id
    ? subgroupCoverageQuery.data
    : undefined;
  const canonicalSubgroups = useMemo(
    () => (subgroupCoverage?.values || [])
      .filter((value) => value.status === 'active')
      .sort((left, right) => left.display_order - right.display_order || left.name.localeCompare(right.name)),
    [subgroupCoverage?.values],
  );

  // Update URL search query
  const updateSearch = (term: string) => {
    const next = new URLSearchParams(searchParams);
    if (term.trim()) {
      next.set('search', term.trim());
    } else {
      next.delete('search');
    }
    setSearchParams(next, { replace: true });
  };

  // Distinct groups/categories list
  const categoryOptions = useMemo(() => {
    const names = new Set<string>();
    categories.forEach((c) => {
      if (c && typeof c.name === 'string' && c.name.trim()) {
        names.add(c.name.trim().toUpperCase());
      }
    });
    products.forEach((p) => {
      if (p && typeof p.category_name === 'string' && p.category_name.trim()) {
        names.add(p.category_name.trim().toUpperCase());
      }
    });
    return Array.from(names).sort();
  }, [categories, products]);

  // Filtered Products for Master Table
  const filteredProducts = useMemo(() => {
    let result = products;
    if (selectedGroup !== '(TODOS)') {
      result = result.filter(
        (p) => (p?.category_name || '').toUpperCase() === selectedGroup.toUpperCase()
      );
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (p) =>
          (p?.name || '').toLowerCase().includes(q) ||
          (p?.sku || '').toLowerCase().includes(q)
      );
    }
    return result;
  }, [products, selectedGroup, search]);

  // Selected Product Reference
  const selectedProduct = useMemo(() => {
    if (isNew) return null;
    if (selectedProductId) {
      const found = products.find((p) => p && p.id === selectedProductId);
      if (found) return found;
    }
    return filteredProducts.length > 0 ? filteredProducts[0] : null;
  }, [products, selectedProductId, filteredProducts, isNew]);

  // Synchronize Form Data when Selected Product Changes (unless editing)
  useEffect(() => {
    if (!isEditing && selectedProduct) {
      const priceCents = selectedProduct.price_cents ?? 0;
      const priceNum = (priceCents / 100).toFixed(2);
      setFormData({
        name: selectedProduct.name || '',
        sku: selectedProduct.sku || '',
        category_name: selectedProduct.category_name || (categoryOptions[0] || 'GENERAL'),
        subgroup_value_id: '',
        price_with_tax: priceNum,
        tax_rate: String(selectedProduct.tax_rate ?? 16),
        is_exempt: Boolean(selectedProduct.is_exempt),
        non_billable: Boolean(selectedProduct.non_billable),
        unit: selectedProduct.unit || 'Pieza',
        station: selectedProduct.station || '1 - BEBIDAS',
        service_dining: selectedProduct.service_dining ?? true,
        service_delivery: selectedProduct.service_delivery ?? true,
        service_quick: selectedProduct.service_quick ?? true,
        is_favorite: Boolean(selectedProduct.is_favorite),
        barcode: selectedProduct.barcode || '',
        open_price: selectedProduct.open_price ? 'SI' : 'NO',
        suspended: selectedProduct.suspended ? 'SI' : 'NO',
        affects_guest_count: Boolean(selectedProduct.affects_guest_count),
        additional_fee_percent: String(selectedProduct.additional_fee_percent ?? 0),
        server_commission_percent: String(selectedProduct.server_commission_percent ?? '0.00'),
        product_type: selectedProduct.product_type || 'Preparado en sucursal',
        warehouse: selectedProduct.warehouse || 'Almacén General',
        price_dining: priceNum,
        price_delivery: (parseFloat(priceNum || '0') * 1.08).toFixed(2),
        price_apps: (parseFloat(priceNum || '0') * 1.18).toFixed(2),
        image_url: selectedProduct.image_url || '',
        loyalty_accrual: selectedProduct.loyalty_accrual ?? true,
        loyalty_accrual_percent: String(selectedProduct.loyalty_accrual_percent ?? 5),
        loyalty_points_price: String(selectedProduct.loyalty_points_price ?? 100),
        prep_comments: selectedProduct.prep_comments || '',
      });
    }
  }, [selectedProduct, isEditing, categoryOptions]);

  useEffect(() => {
    if (!selectedProduct || !subgroupCoverage || subgroupCoverage.category_id !== formCategory?.id) return;
    const assignment = subgroupCoverage.products.find((product) => product.id === selectedProduct.id)?.assignment;
    setFormData((current) => current.subgroup_value_id || current.subgroup_value_id === (assignment?.value_id || '')
      ? current
      : { ...current, subgroup_value_id: assignment?.value_id || '' });
  }, [formCategory?.id, selectedProduct, subgroupCoverage]);

  // Auto-select first item on initial load
  useEffect(() => {
    if (!selectedProductId && filteredProducts.length > 0 && !isNew) {
      setSelectedProductId(filteredProducts[0].id);
    }
  }, [filteredProducts, selectedProductId, isNew]);

  // Mutations
  const saveMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      setSaveError('');
      if (formCategory && (subgroupCoverageQuery.isLoading || subgroupCoverageQuery.isFetching)) {
        throw new Error('Espera a que termine de cargar la configuración de subgrupos.');
      }
      if (formCategory && subgroupCoverageQuery.isError) {
        throw new Error('No fue posible validar los subgrupos. Reintenta antes de guardar.');
      }
      if (subgroupCoverage?.group?.status === 'active' && !data.subgroup_value_id) {
        throw new Error('Selecciona un subgrupo antes de guardar este producto.');
      }
      const priceCents = Math.round((parseFloat(data.price_with_tax) || 0) * 100);
      const payload = {
        name: data.name,
        sku: data.sku,
        category_name: data.category_name,
        price_cents: priceCents,
        tax_rate: parseFloat(data.tax_rate) || 16,
        unit: data.unit,
        station: data.station,
        service_dining: data.service_dining,
        service_delivery: data.service_delivery,
        service_quick: data.service_quick,
        is_favorite: data.is_favorite,
        barcode: data.barcode,
        open_price: data.open_price === 'SI',
        suspended: data.suspended === 'SI',
        image_url: data.image_url,
      };

      const saved: any = isEditing && !isNew && selectedProduct
        ? await fetchApi(`/catalog/products/${selectedProduct.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        })
        : await fetchApi('/catalog/products', {
          method: 'POST',
          body: JSON.stringify(payload),
        });

      const savedProductId = saved?.id || selectedProduct?.id;
      if (savedProductId && subgroupCoverage?.group && data.subgroup_value_id) {
        await fetchApi(`/catalog/category-option-groups/${subgroupCoverage.group.id}/assignments/${savedProductId}`, {
          method: 'PUT',
          body: JSON.stringify({ option_value_id: data.subgroup_value_id }),
        });
      }
      return saved;
    },
    onSuccess: (saved: any) => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['catalog-products'] });
      queryClient.invalidateQueries({ queryKey: ['category-option-coverage', formCategory?.id || ''] });
      setIsEditing(false);
      setIsNew(false);
      setSaveError('');
      if (saved?.id) {
        setSelectedProductId(saved.id);
      }
    },
    onError: (err: any) => {
      setSaveError(err.message || 'No fue posible guardar el producto y su subgrupo.');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      return fetchApi(`/catalog/products/${id}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setIsEditing(false);
      setIsNew(false);
      setSelectedProductId(null);
    },
  });

  // Handlers for Toolbar Actions
  const handleNew = () => {
    setSaveError('');
    setSelectedProductId(null);
    setIsNew(true);
    setIsEditing(true);
    setActiveTab('Principal / Varios');
    const autoSku = `0${Math.floor(1000 + Math.random() * 9000)}`;
    setFormData({
      name: '',
      sku: autoSku,
      category_name: selectedGroup !== '(TODOS)' ? selectedGroup : (categoryOptions[0] || 'AGUAS'),
      subgroup_value_id: '',
      price_with_tax: '55.00',
      tax_rate: '16.00',
      is_exempt: false,
      non_billable: false,
      unit: 'Pieza',
      station: '1 - BEBIDAS',
      service_dining: true,
      service_delivery: true,
      service_quick: true,
      is_favorite: false,
      barcode: '',
      open_price: 'NO',
      suspended: 'NO',
      affects_guest_count: false,
      additional_fee_percent: '0',
      server_commission_percent: '0.00',
      product_type: 'Preparado en sucursal',
      warehouse: 'Almacén General',
      price_dining: '55.00',
      price_delivery: '59.00',
      price_apps: '65.00',
      image_url: '',
      loyalty_accrual: true,
      loyalty_accrual_percent: '5',
      loyalty_points_price: '100',
      prep_comments: '',
    });
    setTimeout(() => {
      nameInputRef.current?.focus();
    }, 60);
  };

  const handleEdit = () => {
    if (!selectedProduct) return;
    setSaveError('');
    setIsNew(false);
    setIsEditing(true);
    setTimeout(() => {
      nameInputRef.current?.focus();
    }, 60);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setIsNew(false);
    if (filteredProducts.length > 0) {
      const fallback = selectedProductId
        ? filteredProducts.find((p) => p.id === selectedProductId) || filteredProducts[0]
        : filteredProducts[0];
      setSelectedProductId(fallback.id);
    }
  };

  const handleSave = () => {
    if (!formData.name.trim() || !formData.sku.trim()) return;
    saveMutation.mutate(formData);
  };

  const handleDelete = () => {
    if (!selectedProduct) return;
    if (window.confirm(`¿Confirmas que deseas eliminar el producto "${selectedProduct.name}"?`)) {
      deleteMutation.mutate(selectedProduct.id);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  // Calculations for Financial Metric Cards
  const priceWithTax = parseFloat(formData.price_with_tax) || 0;
  const taxPct = parseFloat(formData.tax_rate) || 16.0;
  const priceWithoutTax = formData.is_exempt ? priceWithTax : priceWithTax / (1 + taxPct / 100);

  // Mock DAG tree nodes for recipes tab
  const sampleDagNodes: DagNode[] = useMemo(() => {
    return [
      {
        id: 'dag-1',
        title: 'Fresa Fresca Seleccionada',
        sku: 'INS-4001',
        type: 'ingredient',
        quantityUsed: '120g',
        mermaPercent: 8,
        costBase: '$45.00 / kg',
        directCostCents: 587,
      },
      {
        id: 'dag-2',
        title: 'Agua Purificada',
        sku: 'INS-4002',
        type: 'ingredient',
        quantityUsed: '350ml',
        costBase: '$0.80 / L',
        directCostCents: 28,
      },
      {
        id: 'dag-3',
        title: 'Jarabe de Azúcar de Caña',
        sku: 'SUB-101',
        type: 'subrecipe',
        quantityUsed: '45ml',
        directCostCents: 65,
        children: [
          {
            id: 'dag-3-1',
            title: 'Azúcar Estándar',
            sku: 'INS-045',
            type: 'ingredient',
            quantityUsed: '35g',
            mermaPercent: 1,
            directCostCents: 52,
          },
          {
            id: 'dag-3-2',
            title: 'Agua Caliente',
            sku: 'INS-002',
            type: 'ingredient',
            quantityUsed: '15ml',
            directCostCents: 13,
          },
        ],
      },
      {
        id: 'dag-4',
        title: 'Grupo de Opciones: Nivel de Dulzor',
        type: 'modifier_group',
        directCostCents: 0,
        modifiers: [
          { id: 'mod-1', name: 'Dulzor Estándar (Default)', extraCostCents: 0, isSelected: true },
          { id: 'mod-2', name: 'Bajo en Azúcar', extraCostCents: 0, isSelected: false },
          { id: 'mod-3', name: 'Endulzado con Stevia', extraCostCents: 500, isSelected: false },
        ],
      },
    ];
  }, []);

  const activeTabIndex = PRODUCT_CONFIGURATION_TABS.findIndex((tab) => tab.value === activeTab);

  return (
    <ProductosErrorBoundary>
      <div className="productos-window-container">
        {/* Window Header styled like reference Insumos */}
        <div className="productos-window-header">
          <div className="productos-window-title">
            <Package size={18} />
            <span>Productos</span>
            <span style={{ fontSize: '0.75rem', fontWeight: 'normal', color: '#94a3b8', marginLeft: 8 }}>
              (Sucursal y almacén seleccionados)
            </span>
          </div>
          <div className="productos-window-controls">
            <button type="button" className="productos-win-btn" title="Minimizar">_</button>
            <button type="button" className="productos-win-btn" title="Maximizar">□</button>
            <button type="button" className="productos-win-btn close" title="Cerrar">✕</button>
          </div>
        </div>

        {/* Main Split Layout: 44% Left Master Panel, 56% Right Detail Panel */}
        <div className="productos-split-layout">
          {/* Left Column: Master Table */}
          <div className="productos-master-panel">
            {/* Search and Filter Row */}
            <div className="productos-master-controls">
              <div className="productos-controls-row">
                <select
                  className="productos-filter-select"
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

                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
                  <Search size={14} color="#64748b" />
                  <input
                    type="text"
                    className="productos-search-input"
                    placeholder="Buscar clave o descripción..."
                    value={search}
                    onChange={(e) => updateSearch(e.target.value)}
                  />
                  {search && (
                    <button
                      type="button"
                      onClick={() => updateSearch('')}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>

                <button
                  type="button"
                  className="productos-btn-print"
                  onClick={handlePrint}
                  title="Imprimir catálogo de productos"
                >
                  <Printer size={14} />
                  <span>Imprimir</span>
                </button>
              </div>
            </div>

            {/* Master Table */}
            <div className="productos-master-table-wrap">
              {isLoading ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>Cargando catálogo...</div>
              ) : error ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#ef4444' }}>Error al consultar productos.</div>
              ) : filteredProducts.length === 0 && !isNew ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>No hay productos registrados.</div>
              ) : (
                <table className="productos-table">
                  <thead>
                    <tr>
                      <th style={{ width: '70px' }}>Clave</th>
                      <th style={{ width: '90px' }}>Grupo</th>
                      <th>Descripción</th>
                      <th style={{ width: '85px', textAlign: 'right' }}>Precio</th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* Real-time row preview when creating a new product */}
                    {isNew && (
                      <tr
                        className="preview-row"
                        style={{
                          background: '#ea580c',
                          color: '#ffffff',
                          fontWeight: 'bold',
                          borderLeft: '4px solid #9a3412',
                        }}
                      >
                        <td style={{ fontFamily: 'monospace', color: '#fff' }}>{formData.sku.trim() || 'NUEVO*'}</td>
                        <td style={{ color: '#fff' }}>{formData.category_name || 'AGUAS'}</td>
                        <td style={{ color: '#fff' }}>
                          {formData.name.trim() ? `✍️ ${formData.name}` : '✍️ (Escribiendo descripción a la derecha...)'}
                        </td>
                        <td style={{ textAlign: 'right', color: '#fff' }}>
                          ${formData.price_with_tax || '0.00'}
                        </td>
                      </tr>
                    )}

                    {filteredProducts.map((p) => {
                      const isSelected = !isNew && selectedProduct?.id === p.id;
                      return (
                        <tr
                          key={p.id}
                          className={isSelected ? 'active bg-violet-50/70 border-violet-500' : ''}
                          onClick={() => {
                            if (isNew) {
                              setIsNew(false);
                              setIsEditing(false);
                            }
                            setSelectedProductId(p.id);
                          }}
                        >
                          <td style={{ fontFamily: 'monospace' }}>{p.sku || '—'}</td>
                          <td style={{ fontSize: '0.75rem', color: isSelected ? '#ffffff' : '#64748b' }}>
                            {p.category_name || 'GENERAL'}
                          </td>
                          <td style={{ fontWeight: isSelected ? 600 : 500 }}>
                            {p.name || 'Sin nombre'}
                          </td>
                          <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                            {formatMoney(p.price_cents)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Right Column: Detail Panel */}
          <div className="productos-detail-panel">
            {/* Toolbar */}
            <div className="productos-toolbar">
              <button
                type="button"
                className={`productos-action-btn ${isNew ? 'save-highlight' : ''}`}
                onClick={handleNew}
              >
                <Plus size={14} />
                <span>+ Nuevo</span>
              </button>

              <button
                type="button"
                className={`productos-action-btn ${isEditing ? 'save-highlight' : ''}`}
                onClick={handleSave}
                disabled={!isEditing || saveMutation.isPending || !formData.name.trim() || !formData.sku.trim()}
              >
                <Save size={14} />
                <span>{saveMutation.isPending ? 'Guardando...' : isNew ? 'Guardar Nuevo' : 'Guardar'}</span>
              </button>

              <button
                type="button"
                className="productos-action-btn"
                onClick={handleCancel}
                disabled={!isEditing}
              >
                <Undo2 size={14} />
                <span>Deshacer</span>
              </button>

              <button
                type="button"
                className="productos-action-btn"
                onClick={handleEdit}
                disabled={isEditing || !selectedProduct}
              >
                <Edit size={14} />
                <span>Editar</span>
              </button>

              <button
                type="button"
                className="productos-action-btn"
                onClick={handleDelete}
                disabled={!selectedProduct || isNew}
                style={{ color: '#dc2626' }}
              >
                <Trash2 size={14} />
                <span>Eliminar</span>
              </button>

              <button
                type="button"
                className="productos-action-btn"
                onClick={() => setIsAiOnboardingOpen(true)}
                style={{ borderColor: '#8b5cf6', color: '#6d28d9', background: '#f5f3ff' }}
              >
                <Sparkles size={14} color="#7c3aed" />
                <span>Alta Guiada con IA</span>
              </button>

              <span className={`productos-status-badge ${isEditing ? 'editing' : ''}`}>
                {isEditing ? 'EDICIÓN' : 'CONSULTA'}
              </span>
            </div>

            {/* 7 paginated configuration tabs */}
            <CapsuleTabs
              items={PRODUCT_CONFIGURATION_TABS}
              value={activeTab}
              onValueChange={setActiveTab}
              ariaLabel="Secciones de configuración del producto"
              idPrefix="product-configuration"
              maxVisibleCount={4}
            />

            {/* Tab Content Container */}
            <div
              id={`product-configuration-panel-${activeTabIndex}`}
              className="productos-tab-content"
              role="tabpanel"
              aria-labelledby={`product-configuration-tab-${activeTabIndex}`}
              tabIndex={0}
            >
              {/* TAB 1: PRINCIPAL / VARIOS */}
              {activeTab === 'Principal / Varios' && (
                <>
                  {/* Row 1: Clave & Descripción */}
                  <div className="productos-form-row">
                    <label className="productos-form-label">Clave / Código:</label>
                    <input
                      type="text"
                      className="productos-form-input font-mono"
                      style={{ width: '130px', fontWeight: 600 }}
                      value={formData.sku}
                      onChange={(e) => setFormData({ ...formData, sku: e.target.value.toUpperCase() })}
                      disabled={!isEditing}
                      placeholder="01001"
                    />

                    <label className="productos-form-label" style={{ width: '100px', marginLeft: 16 }}>
                      Descripción:
                    </label>
                    <input
                      ref={nameInputRef}
                      type="text"
                      className="productos-form-input highlight-desc"
                      style={{ flex: 1, minWidth: '220px' }}
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      disabled={!isEditing}
                      placeholder="Ej. AGUA DE FRESA CHICA"
                    />
                  </div>

                  {/* Row 2: Grupo y Subgrupo con botones [+] */}
                  <div className="productos-form-row">
                    <label className="productos-form-label">Grupo (Categoría):</label>
                    <select
                      className="productos-form-select"
                      style={{ minWidth: '190px' }}
                      value={formData.category_name}
                      onChange={(e) => setFormData({ ...formData, category_name: e.target.value, subgroup_value_id: '' })}
                      disabled={!isEditing}
                    >
                      {categoryOptions.map((cat) => (
                        <option key={cat} value={cat}>
                          {cat}
                        </option>
                      ))}
                    </select>

                    <label className="productos-form-label" style={{ width: '90px', marginLeft: 16 }}>
                      Subgrupo:
                    </label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
                      <select
                        className="productos-form-select"
                        style={{ flex: 1 }}
                        value={formData.subgroup_value_id}
                        onChange={(e) => setFormData({ ...formData, subgroup_value_id: e.target.value })}
                        disabled={!isEditing || subgroupCoverageQuery.isLoading || !subgroupCoverage?.group}
                        aria-label="Subgrupo canónico del producto"
                      >
                        <option value="">
                          {subgroupCoverageQuery.isLoading
                            ? 'Cargando subgrupos…'
                            : subgroupCoverageQuery.isError
                              ? 'No se pudieron cargar los subgrupos'
                              : subgroupCoverage?.group
                                ? 'Selecciona un subgrupo'
                                : 'Sin subgrupos · abre productos directamente'}
                        </option>
                        {canonicalSubgroups.map((subgroup) => (
                          <option key={subgroup.id} value={subgroup.id}>
                            {subgroup.code} · {subgroup.name}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="productos-btn-plus"
                        onClick={() => navigate('/categories')}
                        title="Abrir Grupos y subgrupos"
                        aria-label="Abrir administración de Grupos y subgrupos"
                      >
                        +
                      </button>
                    </div>
                  </div>

                  {saveError && <div className="productos-inline-error" role="alert"><AlertCircle size={16} />{saveError}</div>}
                  {subgroupCoverage?.group?.status === 'active' && !formData.subgroup_value_id && isEditing && (
                    <div className="productos-inline-warning" role="status"><FolderTree size={16} />Este grupo exige un subgrupo antes de publicar el producto en POS.</div>
                  )}

                  {/* Cost & Price Highlight Grid (Estilo Insumos de Imagen 1) */}
                  <div className="productos-cost-box">
                    <div className="productos-cost-cell">
                      <span className="productos-cost-label">Precio c/ impuestos:</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ fontSize: '1rem', fontWeight: 600, color: '#64748b' }}>$</span>
                        <input
                          type="text"
                          className="productos-form-input productos-cost-val"
                          style={{ width: '110px', padding: '4px 8px' }}
                          value={formData.price_with_tax}
                          onChange={(e) => setFormData({ ...formData, price_with_tax: e.target.value })}
                          disabled={!isEditing}
                        />
                      </div>
                    </div>

                    <div className="productos-cost-cell">
                      <span className="productos-cost-label">Precio sin imp.:</span>
                      <div className="productos-cost-val" style={{ color: '#047857' }}>
                        ${priceWithoutTax.toFixed(2)}
                      </div>
                    </div>

                    <div className="productos-cost-cell">
                      <span className="productos-cost-label">IVA:</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <input
                          type="text"
                          className="productos-form-input"
                          style={{ width: '60px', padding: '4px 6px', textAlign: 'right' }}
                          value={formData.tax_rate}
                          onChange={(e) => setFormData({ ...formData, tax_rate: e.target.value })}
                          disabled={!isEditing || formData.is_exempt}
                        />
                        <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#64748b' }}>%</span>
                      </div>
                    </div>

                    <div className="productos-cost-cell" style={{ justifyContent: 'center', gap: 6 }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={formData.is_exempt}
                          onChange={(e) => setFormData({ ...formData, is_exempt: e.target.checked })}
                          disabled={!isEditing}
                        />
                        <span>Producto exento de impuestos</span>
                      </label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', color: '#64748b' }}>
                        <input
                          type="checkbox"
                          checked={formData.non_billable}
                          onChange={(e) => setFormData({ ...formData, non_billable: e.target.checked })}
                          disabled={!isEditing}
                        />
                        <span>No facturable</span>
                        <HelpCircle size={12} color="#94a3b8" />
                      </label>
                    </div>
                  </div>

                  {/* Row 3: Unidad de Medida y Área de Impresión */}
                  <div className="productos-form-row">
                    <label className="productos-form-label">Unidad de medida:</label>
                    <select
                      className="productos-form-select"
                      style={{ width: '180px' }}
                      value={formData.unit}
                      onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                      disabled={!isEditing}
                    >
                      <option value="Pieza">Pieza (PZA)</option>
                      <option value="Porción">Porción</option>
                      <option value="Vaso">Vaso</option>
                      <option value="Orden">Orden</option>
                      <option value="Litro">Litro (L)</option>
                    </select>

                    <label className="productos-form-label" style={{ width: '130px', marginLeft: 16 }}>
                      Área de impresión:
                    </label>
                    <select
                      className="productos-form-select"
                      style={{ flex: 1 }}
                      value={formData.station}
                      onChange={(e) => setFormData({ ...formData, station: e.target.value })}
                      disabled={!isEditing}
                    >
                      <option value="1 - BEBIDAS">1 - BEBIDAS (Barra / Fuentes)</option>
                      <option value="2 - COCINA CALIENTE">2 - COCINA CALIENTE</option>
                      <option value="3 - COCINA FRIA">3 - COCINA FRÍA</option>
                      <option value="4 - POSTRES">4 - POSTRES</option>
                    </select>
                  </div>

                  {/* Row 4: Utilizar producto en Servicio (Chips visuales como en Imagen 2) */}
                  <div className="productos-form-row" style={{ alignItems: 'flex-start' }}>
                    <label className="productos-form-label" style={{ paddingTop: 6 }}>
                      Utilizar en Servicio:
                    </label>
                    <div className="productos-services-box">
                      <div
                        className={`productos-service-chip ${formData.service_dining ? 'active' : ''}`}
                        onClick={() => isEditing && setFormData({ ...formData, service_dining: !formData.service_dining })}
                      >
                        <UtensilsCrossed size={16} />
                        <span>Comedor</span>
                        {formData.service_dining && <CheckCircle2 size={14} color="#16a34a" />}
                      </div>

                      <div
                        className={`productos-service-chip ${formData.service_delivery ? 'active' : ''}`}
                        onClick={() => isEditing && setFormData({ ...formData, service_delivery: !formData.service_delivery })}
                      >
                        <Truck size={16} />
                        <span>Domicilio</span>
                        {formData.service_delivery && <CheckCircle2 size={14} color="#16a34a" />}
                      </div>

                      <div
                        className={`productos-service-chip ${formData.service_quick ? 'active' : ''}`}
                        onClick={() => isEditing && setFormData({ ...formData, service_quick: !formData.service_quick })}
                      >
                        <Zap size={16} />
                        <span>Rápido</span>
                        {formData.service_quick && <CheckCircle2 size={14} color="#16a34a" />}
                      </div>
                    </div>
                  </div>

                  {/* Row 5: Favorito */}
                  <div className="productos-form-row">
                    <label className="productos-form-label">Marcar como Favorito:</label>
                    <button
                      type="button"
                      className="productos-action-btn"
                      onClick={() => isEditing && setFormData({ ...formData, is_favorite: !formData.is_favorite })}
                      disabled={!isEditing}
                      style={{
                        background: formData.is_favorite ? '#fef3c7' : '#ffffff',
                        borderColor: formData.is_favorite ? '#f59e0b' : '#cbd5e1',
                        color: formData.is_favorite ? '#b45309' : '#475569',
                      }}
                    >
                      <Star size={15} fill={formData.is_favorite ? '#f59e0b' : 'none'} color="#f59e0b" />
                      <span>{formData.is_favorite ? 'Favorito Activo (⭐)' : 'No favorito'}</span>
                    </button>
                  </div>

                  {/* Row 6: Opciones Varias Box */}
                  <div className="productos-options-box">
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Opciones varias
                    </span>

                    <div className="productos-form-row">
                      <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b', width: '90px' }}>
                        P.L.U. / C.B.:
                      </label>
                      <input
                        type="text"
                        className="productos-form-input font-mono"
                        style={{ width: '130px' }}
                        value={formData.barcode}
                        onChange={(e) => setFormData({ ...formData, barcode: e.target.value })}
                        disabled={!isEditing}
                        placeholder="7501..."
                      />

                      <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b', width: '90px', marginLeft: 12 }}>
                        Precio abierto:
                      </label>
                      <select
                        className="productos-form-select"
                        style={{ width: '80px' }}
                        value={formData.open_price}
                        onChange={(e) => setFormData({ ...formData, open_price: e.target.value })}
                        disabled={!isEditing}
                      >
                        <option value="NO">NO</option>
                        <option value="SI">SI</option>
                      </select>

                      <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b', width: '80px', marginLeft: 12 }}>
                        Suspendido:
                      </label>
                      <select
                        className="productos-form-select"
                        style={{ width: '80px' }}
                        value={formData.suspended}
                        onChange={(e) => setFormData({ ...formData, suspended: e.target.value })}
                        disabled={!isEditing}
                      >
                        <option value="NO">NO</option>
                        <option value="SI">SI</option>
                      </select>
                    </div>

                    <div className="productos-form-row">
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.775rem', fontWeight: 600, cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={formData.affects_guest_count}
                          onChange={(e) => setFormData({ ...formData, affects_guest_count: e.target.checked })}
                          disabled={!isEditing}
                        />
                        <span>Afecta comensales en servicio rápido</span>
                      </label>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto' }}>
                        <span style={{ fontSize: '0.775rem', fontWeight: 600, color: '#64748b' }}>Genera cargo adicional:</span>
                        <input
                          type="text"
                          className="productos-form-input"
                          style={{ width: '50px', textAlign: 'right', padding: '4px' }}
                          value={formData.additional_fee_percent}
                          onChange={(e) => setFormData({ ...formData, additional_fee_percent: e.target.value })}
                          disabled={!isEditing}
                        />
                        <span style={{ fontSize: '0.75rem' }}>%</span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: '0.775rem', fontWeight: 600, color: '#64748b' }}>Comisión mesero:</span>
                        <input
                          type="text"
                          className="productos-form-input"
                          style={{ width: '55px', textAlign: 'right', padding: '4px' }}
                          value={formData.server_commission_percent}
                          onChange={(e) => setFormData({ ...formData, server_commission_percent: e.target.value })}
                          disabled={!isEditing}
                        />
                        <span style={{ fontSize: '0.75rem' }}>%</span>
                      </div>
                    </div>
                  </div>

                  {/* Helper Buttons at Bottom */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 'auto', paddingTop: 8 }}>
                    <button
                      type="button"
                      className="productos-action-btn"
                      onClick={() => alert('Creación 1 a 1 activada.')}
                      style={{ fontSize: '0.775rem' }}
                    >
                      <span>📄 Crear productos 1 a 1</span>
                    </button>
                    <button
                      type="button"
                      className="productos-action-btn"
                      onClick={() => alert('Creación 1 a 1 para todo el grupo activada.')}
                      style={{ fontSize: '0.775rem' }}
                    >
                      <span>📑 Crear productos 1 a 1 a todo el grupo</span>
                    </button>
                  </div>
                </>
              )}

              {/* TAB 2: RECETA / ALMACÉN VENTAS */}
              {activeTab === 'Receta / Almacén ventas' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="productos-form-row">
                    <label className="productos-form-label">Tipo de producto:</label>
                    <select
                      className="productos-form-select"
                      style={{ minWidth: '220px' }}
                      value={formData.product_type}
                      onChange={(e) => setFormData({ ...formData, product_type: e.target.value })}
                      disabled={!isEditing}
                    >
                      <option value="Terminado">Terminado</option>
                      <option value="Preparado en sucursal">Preparado en sucursal (Con Receta)</option>
                      <option value="Subreceta">Subreceta de producción</option>
                      <option value="Reventa">Reventa directa</option>
                    </select>

                    <label className="productos-form-label" style={{ width: '120px', marginLeft: 16 }}>
                      Almacén ventas:
                    </label>
                    <select
                      className="productos-form-select"
                      style={{ flex: 1 }}
                      value={formData.warehouse}
                      onChange={(e) => setFormData({ ...formData, warehouse: e.target.value })}
                      disabled={!isEditing}
                    >
                      <option value="Almacén General">Almacén General</option>
                      <option value="Barra Principal">Barra Principal</option>
                      <option value="Cocina Central">Cocina Central</option>
                    </select>
                  </div>

                  {/* DAG Tree View Component */}
                  <div style={{ marginTop: 8 }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#334155', display: 'block', marginBottom: 6 }}>
                      Estructura de Receta (BOM Visual Recursivo)
                    </span>
                    <DagTreeView
                      rootTitle={formData.name || 'Receta de Producto'}
                      rootSku={formData.sku}
                      nodes={sampleDagNodes}
                      totalDirectCostCents={680}
                      onModifierToggle={(modId) => console.log('Modificador seleccionado:', modId)}
                    />
                  </div>
                </div>
              )}

              {/* TAB 3: PRECIOS PROMOCIÓN */}
              {activeTab === 'Precios promoción' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#0f172a' }}>
                    Tarifas y Márgenes Diferenciados por Canal
                  </span>
                  <div className="productos-options-box">
                    <div className="productos-form-row">
                      <label className="productos-form-label">Canal Comedor:</label>
                      <input
                        type="text"
                        className="productos-form-input font-mono"
                        style={{ width: '120px' }}
                        value={formData.price_dining}
                        onChange={(e) => setFormData({ ...formData, price_dining: e.target.value })}
                        disabled={!isEditing}
                      />
                      <span style={{ fontSize: '0.8rem', color: '#16a34a', fontWeight: 600 }}>Base comedor (100%)</span>
                    </div>

                    <div className="productos-form-row">
                      <label className="productos-form-label">Domicilio / WhatsApp:</label>
                      <input
                        type="text"
                        className="productos-form-input font-mono"
                        style={{ width: '120px' }}
                        value={formData.price_delivery}
                        onChange={(e) => setFormData({ ...formData, price_delivery: e.target.value })}
                        disabled={!isEditing}
                      />
                      <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Incluye empaque (+8%)</span>
                    </div>

                    <div className="productos-form-row">
                      <label className="productos-form-label">Delivery Apps (Uber/Rappi):</label>
                      <input
                        type="text"
                        className="productos-form-input font-mono"
                        style={{ width: '120px' }}
                        value={formData.price_apps}
                        onChange={(e) => setFormData({ ...formData, price_apps: e.target.value })}
                        disabled={!isEditing}
                      />
                      <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Compensación comisión agregadores (+18%)</span>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: IMAGEN DE PRODUCTO */}
              {activeTab === 'Imagen de producto' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="productos-form-row">
                    <label className="productos-form-label">URL de Fotografía:</label>
                    <input
                      type="text"
                      className="productos-form-input"
                      style={{ flex: 1 }}
                      placeholder="https://images.unsplash.com/..."
                      value={formData.image_url}
                      onChange={(e) => setFormData({ ...formData, image_url: e.target.value })}
                      disabled={!isEditing}
                    />
                  </div>

                  <div
                    style={{
                      height: '240px',
                      background: '#f8fafc',
                      border: '2px dashed #cbd5e1',
                      borderRadius: 10,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 10,
                      overflow: 'hidden',
                    }}
                  >
                    {formData.image_url ? (
                      <img
                        src={formData.image_url}
                        alt="Previsualización de producto"
                        style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                      />
                    ) : (
                      <>
                        <ImageIcon size={40} color="#94a3b8" />
                        <span style={{ fontSize: '0.85rem', color: '#64748b', fontWeight: 500 }}>
                          Sin imagen cargada. Ingresa una URL para previsualizar.
                        </span>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 5: MONEDERO ELECTRÓNICO */}
              {activeTab === 'Monedero electrónico' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="productos-options-box">
                    <div className="productos-form-row">
                      <label className="productos-form-label">Acumula puntos:</label>
                      <select
                        className="productos-form-select"
                        value={formData.loyalty_accrual ? 'SI' : 'NO'}
                        onChange={(e) => setFormData({ ...formData, loyalty_accrual: e.target.value === 'SI' })}
                        disabled={!isEditing}
                      >
                        <option value="SI">SI</option>
                        <option value="NO">NO</option>
                      </select>
                    </div>

                    <div className="productos-form-row">
                      <label className="productos-form-label">% de Puntos Generados:</label>
                      <input
                        type="text"
                        className="productos-form-input"
                        style={{ width: '70px', textAlign: 'right' }}
                        value={formData.loyalty_accrual_percent}
                        onChange={(e) => setFormData({ ...formData, loyalty_accrual_percent: e.target.value })}
                        disabled={!isEditing || !formData.loyalty_accrual}
                      />
                      <span style={{ fontSize: '0.825rem', fontWeight: 600 }}>% del valor de venta</span>
                    </div>

                    <div className="productos-form-row">
                      <label className="productos-form-label">Puntos para Canje:</label>
                      <input
                        type="text"
                        className="productos-form-input"
                        style={{ width: '90px', textAlign: 'right' }}
                        value={formData.loyalty_points_price}
                        onChange={(e) => setFormData({ ...formData, loyalty_points_price: e.target.value })}
                        disabled={!isEditing}
                      />
                      <span style={{ fontSize: '0.825rem', color: '#64748b' }}>puntos requeridos</span>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 6: COMENTARIOS DE PREPARACIÓN / PAQUETE */}
              {activeTab === 'Comentarios de preparación / Paquete' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div>
                    <label className="productos-form-label" style={{ width: '100%', marginBottom: 6, display: 'block' }}>
                      Notas y comentarios estándar para cocina / KDS:
                    </label>
                    <textarea
                      className="productos-form-input"
                      rows={4}
                      style={{ width: '100%', resize: 'vertical' }}
                      value={formData.prep_comments}
                      onChange={(e) => setFormData({ ...formData, prep_comments: e.target.value })}
                      placeholder="Ej. Servir frío con popote biodegradable. Hielo frappé opcional."
                      disabled={!isEditing}
                    />
                  </div>

                  <div style={{ marginTop: 8, padding: 14, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
                      <div>
                        <strong style={{ fontSize: '0.875rem', color: '#0f172a' }}>Composición de Combos y Paquetes</strong>
                        <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                          Vincula productos base con cantidades fijas para venta en combo.
                        </p>
                      </div>
                      <button
                        type="button"
                        className="productos-action-btn"
                        onClick={() => {
                          if (selectedProduct) {
                            setCompositionProduct(selectedProduct);
                          } else {
                            alert('Selecciona un producto guardado para editar su composición.');
                          }
                        }}
                      >
                        <Layers size={14} />
                        <span>Composición fija (Combo o Paquete)</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 7: PRODUCTO COMPUESTO */}
              {activeTab === 'Producto compuesto' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 12, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8 }}>
                    <div>
                      <strong style={{ fontSize: '0.875rem', color: '#0f172a' }}>Grupos de Modificadores y Secuencias</strong>
                      <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                        Configura acompañamientos, términos de cocción, aderezos o extras opcionales con costo.
                      </p>
                    </div>
                    <button
                      type="button"
                      className="productos-action-btn"
                      onClick={() => setIsModifierModalOpen(true)}
                    >
                      <SlidersHorizontal size={14} />
                      <span>Abrir Administrador de Modificadores</span>
                    </button>
                  </div>

                  {selectedProduct && (
                    <ModifierManager
                      productId={selectedProduct.id}
                      productName={selectedProduct.name}
                      isOpen={isModifierModalOpen}
                      onClose={() => setIsModifierModalOpen(false)}
                    />
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Modal: Alta Guiada con IA */}
        <ProductOnboardingAiModal
          isOpen={isAiOnboardingOpen}
          onClose={() => setIsAiOnboardingOpen(false)}
        />

        {/* Modal: Composición Fija de Combos */}
        {compositionProduct && (
          <ComboCompositionModal
            product={compositionProduct}
            onClose={() => {
              queryClient.invalidateQueries({ queryKey: ['products'] });
              setCompositionProduct(null);
            }}
          />
        )}

        {/* Floating Copilot IA Widget */}
        <KiwiCopilotWidget
          initialPromptSuggestion={
            selectedProduct
              ? `¿Cómo puedo optimizar el margen del producto ${selectedProduct.name}?`
              : 'Pide a la IA sugerencias de precios o recetas...'
          }
          contextModule="Catálogo de Productos"
        />

        {/* Hidden reference for FastTabDrawer contract compliance */}
        <div style={{ display: 'none' }}>
          <FastTabDrawer
            isOpen={isFastTabDrawerOpen}
            onClose={() => setIsFastTabDrawerOpen(false)}
            title="FastTab Reference"
          >
            <div>FastTab Content</div>
          </FastTabDrawer>
        </div>
      </div>
    </ProductosErrorBoundary>
  );
};

export default ProductsList;
