import React, { Component, ErrorInfo, ReactNode, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, Link } from 'react-router-dom';
import { Badge } from '@restaurantos/ui';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import {
  Package,
  Plus,
  Edit,
  Trash2,
  SlidersHorizontal,
  Search,
  Sparkles,
  Printer,
  RotateCcw,
  Save,
  X,
  Utensils,
  Truck,
  Zap,
  Star,
  ExternalLink,
  Image as ImageIcon,
  DollarSign,
  BookOpen,
  Layers,
  MessageSquare,
  Award,
  AlertTriangle,
  RefreshCw,
  FolderPlus
} from 'lucide-react';
import { ModifierManager } from './ModifierManager';
import { ProductOnboardingAiModal } from './ProductOnboardingAiModal';
import { ComboCompositionModal } from './ComboCompositionModal';

import './ProductosWindow.css';
import '../../premium-catalogs.css';

export interface Product {
  id: string;
  name: string;
  sku: string;
  category_name: string;
  price_cents: number | null;
  station: string;
  status?: string;
  image_url?: string;
  catalog_scope?: 'organization' | 'branch';
  source_branch_id?: string | null;
  subgroup?: string;
  unit?: string;
  is_favorite?: boolean;
  service_dining?: boolean;
  service_delivery?: boolean;
  service_quick?: boolean;
  tax_rate?: number;
  barcode?: string;
}

interface Category {
  id: string;
  name: string;
  display_order?: number;
  status?: string;
}

interface SubgroupItem {
  id: string;
  code: string;
  name: string;
  category_name: string;
}

const DEFAULT_SUBGROUPS: SubgroupItem[] = [
  { id: '1', code: '01', name: 'AGUA CHICA', category_name: 'AGUAS' },
  { id: '2', code: '02', name: 'AGUA GRANDE', category_name: 'AGUAS' },
  { id: '3', code: '03', name: 'ENSALADA CHICA', category_name: 'ENSALADAS' },
  { id: '4', code: '04', name: 'ENSALADA GRANDE', category_name: 'ENSALADAS' },
  { id: '5', code: '05', name: 'EXTRA ADEREZOS', category_name: 'EXTRAS' },
  { id: '6', code: '06', name: 'EXTRA DE SEMILLA', category_name: 'EXTRAS' },
  { id: '7', code: '07', name: 'EXTRA FRUTA Y VERDURA', category_name: 'EXTRAS' },
];

export function formatMoney(amountInCents: number | null | undefined): string {
  if (amountInCents == null || isNaN(Number(amountInCents))) {
    return '$0.00';
  }
  return `$${(Number(amountInCents) / 100).toFixed(2)}`;
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  errorText: string;
}

export class ProductosErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, errorText: '' };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, errorText: error.message || 'Error inesperado en catálogo de productos' };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ProductosErrorBoundary atrapó un error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, background: '#fee2e2', border: '2px solid #ef4444', borderRadius: 6, margin: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#991b1b', fontWeight: 700, fontSize: '1.1rem' }}>
            <AlertTriangle size={24} />
            Ha ocurrido un problema al renderizar el Catálogo de Productos
          </div>
          <p style={{ margin: '12px 0', color: '#7f1d1d', fontSize: '0.9rem' }}>{this.state.errorText}</p>
          <button
            onClick={() => {
              this.setState({ hasError: false, errorText: '' });
              window.location.reload();
            }}
            style={{
              padding: '6px 14px',
              background: '#b91c1c',
              color: '#ffffff',
              border: 'none',
              borderRadius: 4,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <RefreshCw size={16} /> Recargar pantalla
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const emptyFormState = {
  name: '',
  sku: '',
  category_name: '',
  subgroup: '',
  station: 'kitchen',
  status: 'active',
  price: '0.00',
  tax_rate: 16,
  is_tax_exempt: false,
  unit: 'PZA',
  service_dining: true,
  service_delivery: true,
  service_quick: true,
  is_favorite: false,
  barcode: '',
  image_url: '',
  notes: '',
};


function ToggleSwitch({ checked, onChange, label, activeColor = '#0284c7' }: { checked: boolean, onChange: () => void, label: string, activeColor?: string }) {
  return (
    <div
      onClick={onChange}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        cursor: 'pointer',
        padding: '6px 12px',
        borderRadius: 20,
        background: checked ? 'rgba(2, 132, 199, 0.1)' : '#f1f5f9',
        border: `1px solid ${checked ? activeColor : '#cbd5e1'}`,
        userSelect: 'none',
        transition: 'all 0.2s',
      }}
    >
      <div style={{
        width: 16, height: 16, borderRadius: '50%',
        background: checked ? activeColor : '#94a3b8',
      }} />
      <span style={{ fontSize: '0.85rem', fontWeight: checked ? 600 : 400, color: checked ? '#0f172a' : '#64748b' }}>
        {label}
      </span>
    </div>
  );
}


type ProductTab =
  | 'principal'
  | 'receta'
  | 'precios'
  | 'imagen'
  | 'monedero'
  | 'paquete'
  | 'modificadores';

function ProductsListInner() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') || '';

  // Filter dropdown states
  const [categoryFilter, setCategoryFilter] = useState<string>('(TODOS)');
  const [serviceFilter, setServiceFilter] = useState<string>('(TODOS)');

  // Master-Detail selection & editing states
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isNew, setIsNew] = useState(false);
  const [activeTab, setActiveTab] = useState<ProductTab>('principal');
  const [formData, setFormData] = useState(emptyFormState);

  // Subgroups list state
  const [subgroups, setSubgroups] = useState<SubgroupItem[]>(DEFAULT_SUBGROUPS);
  const [isSubgroupsModalOpen, setIsSubgroupsModalOpen] = useState(false);
  const [subgroupForm, setSubgroupForm] = useState({ code: '', name: '', category_name: '' });
  const [selectedSubgroup, setSelectedSubgroup] = useState<SubgroupItem | null>(null);

  // Quick Category creation modal
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');

  // Auxiliary modals
  const [isAiOnboardingOpen, setIsAiOnboardingOpen] = useState(false);
  const [modifierProduct, setModifierProduct] = useState<Product | null>(null);
  const [compositionProduct, setCompositionProduct] = useState<Product | null>(null);

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

  // Synchronize selection on initial load or deletion
  React.useEffect(() => {
    if (products.length > 0 && !selectedProduct && !isNew) {
      const first = products[0];
      setSelectedProduct(first);
      setFormData({
        name: first.name || '',
        sku: first.sku || '',
        category_name: first.category_name || '',
        subgroup: first.subgroup || '',
        station: first.station || 'kitchen',
        status: first.status || 'active',
        price: first.price_cents != null ? (first.price_cents / 100).toFixed(2) : '0.00',
        tax_rate: 16,
        is_tax_exempt: false,
        unit: first.unit || 'PZA',
        service_dining: first.service_dining ?? true,
        service_delivery: first.service_delivery ?? true,
        service_quick: first.service_quick ?? true,
        is_favorite: first.is_favorite ?? false,
        barcode: first.barcode || '',
        image_url: first.image_url || '',
        notes: '',
      });
    }
  }, [products, selectedProduct, isNew]);

  // Master Filtered Products
  const filteredProducts: Product[] = useMemo(() => {
    const term = search.trim().toLocaleLowerCase('es-MX');
    return products.filter((product: Product) => {
      const matchesSearch =
        !term ||
        (product.name || '').toLocaleLowerCase('es-MX').includes(term) ||
        (product.sku || '').toLocaleLowerCase('es-MX').includes(term);

      const matchesCategory =
        categoryFilter === '(TODOS)' || product.category_name === categoryFilter;

      let matchesService = true;
      if (serviceFilter === 'Comedor') matchesService = product.service_dining !== false;
      if (serviceFilter === 'Domicilio') matchesService = product.service_delivery !== false;
      if (serviceFilter === 'Rápido') matchesService = product.service_quick !== false;

      return matchesSearch && matchesCategory && matchesService;
    });
  }, [products, search, categoryFilter, serviceFilter]);

  const updateSearch = (value: string) => {
    setSearchParams(value ? { search: value } : {}, { replace: true });
  };

  const handleSelectProduct = (product: Product) => {
    setSelectedProduct(product);
    setIsNew(false);
    setIsEditing(false);
    setFormData({
      name: product.name || '',
      sku: product.sku || '',
      category_name: product.category_name || '',
      subgroup: product.subgroup || '',
      station: product.station || 'kitchen',
      status: product.status || 'active',
      price: product.price_cents != null ? (product.price_cents / 100).toFixed(2) : '0.00',
      tax_rate: 16,
      is_tax_exempt: false,
      unit: product.unit || 'PZA',
      service_dining: product.service_dining ?? true,
      service_delivery: product.service_delivery ?? true,
      service_quick: product.service_quick ?? true,
      is_favorite: product.is_favorite ?? false,
      barcode: product.barcode || '',
      image_url: product.image_url || '',
      notes: '',
    });
  };

  const handleNew = () => {
    const nextSkuNum = (products.length + 1).toString().padStart(5, '0');
    setIsNew(true);
    setIsEditing(true);
    setSelectedProduct(null);
    setActiveTab('principal');
    setFormData({
      ...emptyFormState,
      sku: nextSkuNum,
      category_name: categories.length > 0 ? categories[0].name : '',
    });
  };

  const handleUndo = () => {
    if (selectedProduct) {
      handleSelectProduct(selectedProduct);
    } else if (products.length > 0) {
      handleSelectProduct(products[0]);
    } else {
      setIsNew(false);
      setIsEditing(false);
      setFormData(emptyFormState);
    }
  };

  // Mutations
  const saveMutation = useMutation({
    mutationFn: async () => {
      const priceCents = Math.round((parseFloat(formData.price) || 0) * 100);
      const payload: Record<string, any> = {
        name: formData.name.trim(),
        sku: formData.sku.trim(),
        category_name: formData.category_name.trim(),
        station: formData.station,
        price_cents: priceCents,
        image_url: formData.image_url ? formData.image_url.trim() : null,
      };

      if (isNew) {
        return fetchApi('/catalog/products', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      } else if (selectedProduct) {
        payload.status = formData.status;
        return fetchApi(`/catalog/products/${selectedProduct.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      }
    },
    onSuccess: (savedProduct: any) => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setIsEditing(false);
      setIsNew(false);
      if (savedProduct?.id) {
        setSelectedProduct(savedProduct);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => fetchApi(`/catalog/products/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setSelectedProduct(null);
      setIsEditing(false);
      setIsNew(false);
    },
  });

  const createCategoryMutation = useMutation({
    mutationFn: (name: string) =>
      fetchApi('/categories', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim(), display_order: categories.length }),
      }),
    onSuccess: (createdCat: any) => {
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      setIsCategoryModalOpen(false);
      setNewCategoryName('');
      if (createdCat?.name) {
        setFormData((prev) => ({ ...prev, category_name: createdCat.name }));
      }
    },
  });

  // Calculate price without taxes
  const numericPrice = parseFloat(formData.price) || 0;
  const priceSinImp = formData.is_tax_exempt
    ? numericPrice
    : numericPrice / (1 + formData.tax_rate / 100);

  return (
    <div className="productos-window-container">
      {/* 1. Header Bar styled like Soft Restaurant */}
      <div className="productos-window-header">
        <div className="productos-window-title">
          <Package size={20} />
          {isNew
            ? `Productos - NUEVO PRODUCTO`
            : selectedProduct
            ? `Productos - ${selectedProduct.sku} ${selectedProduct.name.toUpperCase()}`
            : 'Productos y catálogo'}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={() => setIsAiOnboardingOpen(true)}
            style={{
              background: '#4338ca',
              color: '#ffffff',
              border: '1px solid #3730a3',
              borderRadius: 3,
              padding: '3px 10px',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <Sparkles size={14} />
            Alta Guiada con IA
          </button>
          <div className="productos-window-controls">
            <button className="productos-win-btn" title="Minimizar">_</button>
            <button className="productos-win-btn" title="Maximizar">□</button>
            <button className="productos-win-btn close" title="Cerrar" onClick={() => handleUndo()}>✕</button>
          </div>
        </div>
      </div>

      {/* 2. Split Layout: Master (Left 44%) and Detail (Right 56%) */}
      <div className="productos-split-layout">
        {/* LEFT COLUMN: Master List */}
        <div className="productos-master-panel">
          {/* Top Controls Bar */}
          <div className="productos-master-controls">
            <div className="productos-controls-row">
              <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#334155' }}>Grupo:</label>
              <select
                className="productos-filter-select"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
              >
                <option value="(TODOS)">(TODOS)</option>
                {categories.map((cat: Category) => (
                  <option key={cat.id} value={cat.name}>
                    {cat.name}
                  </option>
                ))}
              </select>

              <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#334155' }}>Servicio:</label>
              <select
                className="productos-filter-select"
                value={serviceFilter}
                onChange={(e) => setServiceFilter(e.target.value)}
                style={{ maxWidth: 110 }}
              >
                <option value="(TODOS)">(TODOS)</option>
                <option value="Comedor">Comedor</option>
                <option value="Domicilio">Domicilio</option>
                <option value="Rápido">Rápido</option>
              </select>

              <button
                className="productos-btn-print"
                onClick={() => window.print()}
                title="Imprimir lista de productos"
              >
                <Printer size={14} /> Imprimir
              </button>
            </div>

            <div className="productos-controls-row">
              <Search size={15} style={{ color: '#64748b' }} />
              <input
                className="productos-search-input"
                value={search}
                onChange={(e) => updateSearch(e.target.value)}
                placeholder="Buscar por descripción o Clave..."
                aria-label="Buscar producto por nombre o SKU"
              />
              {search && (
                <button
                  onClick={() => updateSearch('')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          {/* Master Table */}
          <div className="productos-master-table-wrap">
            {isLoading ? (
              <div style={{ padding: 30, textAlign: 'center', color: '#64748b' }}>Cargando catálogo...</div>
            ) : error ? (
              <div style={{ padding: 20, textAlign: 'center', color: '#ef4444' }}>
                {error instanceof ApiError ? error.message : 'Error al cargar los productos.'}
              </div>
            ) : (
              <table className="productos-table">
                <thead>
                  <tr>
                    <th style={{ width: '18%' }}>Clave</th>
                    <th style={{ width: '22%' }}>Grupo</th>
                    <th style={{ width: '42%' }}>Descripción</th>
                    <th style={{ width: '18%', textAlign: 'right' }}>Precio</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Live typing preview row when creating a new product */}
                  {isNew && (
                    <tr className="preview-row active">
                      <td style={{ fontWeight: 700 }}>{formData.sku || 'NUEVO'}</td>
                      <td>{formData.category_name || '-'}</td>
                      <td>
                        <span style={{ color: '#1d4ed8', fontWeight: 600 }}>
                          ⚡ {formData.name || '(Nuevo producto en captura)'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right', fontWeight: 700 }}>
                        ${Number(formData.price || 0).toFixed(2)}
                      </td>
                    </tr>
                  )}

                  {filteredProducts.map((product: Product) => {
                    const isSelected = selectedProduct?.id === product.id && !isNew;
                    return (
                      <tr
                        key={product.id}
                        className={isSelected ? 'active' : ''}
                        onClick={() => handleSelectProduct(product)}
                      >
                        <td style={{ fontWeight: 600 }}>{product.sku}</td>
                        <td>{product.category_name || '-'}</td>
                        <td>
                          {product.name}
                          {product.status === 'inactive' && (
                            <span style={{ marginLeft: 6, fontSize: '0.75rem', color: isSelected ? '#fed7aa' : '#dc2626' }}>
                              (Suspendido)
                            </span>
                          )}
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 600 }}>
                          {formatMoney(product.price_cents)}
                        </td>
                      </tr>
                    );
                  })}

                  {filteredProducts.length === 0 && !isNew && (
                    <tr>
                      <td colSpan={4} style={{ padding: 24, textAlign: 'center', color: '#94a3b8' }}>
                        No se encontraron productos coincidentes.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748b', padding: '2px 4px' }}>
            Total mostrados: {filteredProducts.length} productos
          </div>
        </div>

        {/* RIGHT COLUMN: Detail Panel with Tabs */}
        <div className="productos-detail-panel">
          {/* Action Toolbar */}
          <div className="productos-toolbar">
            <button
              className="productos-action-btn"
              onClick={handleNew}
              title="Dar de alta un nuevo producto"
            >
              <Plus size={16} color="#16a34a" /> Nuevo
            </button>

            <button
              className={`productos-action-btn ${isEditing ? 'save-highlight' : ''}`}
              disabled={!isEditing || saveMutation.isPending || !formData.name.trim() || !formData.sku.trim()}
              onClick={() => saveMutation.mutate()}
              title="Guardar cambios del producto"
            >
              <Save size={16} color="#047857" /> {saveMutation.isPending ? 'Guardando...' : 'Guardar'}
            </button>

            <button
              className="productos-action-btn"
              disabled={!isEditing}
              onClick={handleUndo}
              title="Deshacer modificaciones no guardadas"
            >
              <RotateCcw size={16} color="#d97706" /> Deshacer
            </button>

            <button
              className="productos-action-btn"
              disabled={!selectedProduct || isEditing}
              onClick={() => setIsEditing(true)}
              title="Editar el producto seleccionado"
            >
              <Edit size={16} color="#0284c7" /> Editar
            </button>

            <button
              className="productos-action-btn"
              onClick={() => {
                const searchEl = document.querySelector('.productos-search-input') as HTMLInputElement;
                if (searchEl) searchEl.focus();
              }}
              title="Buscar producto"
            >
              <Search size={16} color="#475569" /> Buscar
            </button>

            <button
              className="productos-action-btn"
              disabled={!selectedProduct || isNew}
              onClick={() => {
                if (selectedProduct && window.confirm(`¿Seguro que deseas eliminar ${selectedProduct.name}?`)) {
                  deleteMutation.mutate(selectedProduct.id);
                }
              }}
              title="Eliminar producto seleccionado"
            >
              <Trash2 size={16} color="#dc2626" /> Eliminar
            </button>

            <button
              className="productos-action-btn"
              onClick={handleUndo}
              title="Cerrar edición"
            >
              <X size={16} color="#64748b" /> Cerrar
            </button>
          </div>

          {/* Tab Strip with 7 Tabs */}
          <div className="productos-tab-strip">
            <button
              className={`productos-tab-btn ${activeTab === 'principal' ? 'active' : ''}`}
              onClick={() => setActiveTab('principal')}
            >
              Principal / Varios
            </button>
            <button
              className={`productos-tab-btn ${activeTab === 'receta' ? 'active' : ''}`}
              onClick={() => setActiveTab('receta')}
            >
              Receta / Almacén ventas
            </button>
            <button
              className={`productos-tab-btn ${activeTab === 'precios' ? 'active' : ''}`}
              onClick={() => setActiveTab('precios')}
            >
              Precios promoción
            </button>
            <button
              className={`productos-tab-btn ${activeTab === 'imagen' ? 'active' : ''}`}
              onClick={() => setActiveTab('imagen')}
            >
              Imagen de producto
            </button>
            <button
              className={`productos-tab-btn ${activeTab === 'monedero' ? 'active' : ''}`}
              onClick={() => setActiveTab('monedero')}
            >
              Monedero electrónico
            </button>
            <button
              className={`productos-tab-btn ${activeTab === 'paquete' ? 'active' : ''}`}
              onClick={() => setActiveTab('paquete')}
            >
              Comentarios de preparación / Paquete
            </button>
            <button
              className={`productos-tab-btn ${activeTab === 'modificadores' ? 'active' : ''}`}
              onClick={() => setActiveTab('modificadores')}
            >
              Producto compuesto
            </button>
          </div>

          {/* TAB 1: Principal / Varios */}
          {activeTab === 'principal' && (
            <div className="productos-tab-content">
              {/* Grupo */}
              <div className="productos-form-row">
                <label className="productos-form-label">Grupo:</label>
                <select
                  className="productos-form-select"
                  disabled={!isEditing}
                  value={formData.category_name}
                  onChange={(e) => setFormData({ ...formData, category_name: e.target.value })}
                  style={{ minWidth: 220 }}
                >
                  <option value="">-- Seleccionar grupo --</option>
                  {categories.map((cat: Category) => (
                    <option key={cat.id} value={cat.name}>
                      {cat.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="productos-btn-plus"
                  title="Dar de alta nuevo grupo de productos"
                  onClick={() => setIsCategoryModalOpen(true)}
                >
                  +
                </button>
              </div>

              {/* Subgrupo */}
              <div className="productos-form-row">
                <label className="productos-form-label">Subgrupo:</label>
                <select
                  className="productos-form-select"
                  disabled={!isEditing}
                  value={formData.subgroup}
                  onChange={(e) => setFormData({ ...formData, subgroup: e.target.value })}
                  style={{ minWidth: 220 }}
                >
                  <option value="">-- Seleccionar subgrupo --</option>
                  {subgroups
                    .filter((sg) => !formData.category_name || sg.category_name === formData.category_name)
                    .map((sg) => (
                      <option key={sg.id} value={sg.name}>
                        {sg.code} - {sg.name}
                      </option>
                    ))}
                </select>
                <button
                  type="button"
                  className="productos-btn-plus"
                  title="Administrar subgrupos de productos"
                  onClick={() => setIsSubgroupsModalOpen(true)}
                >
                  +
                </button>
              </div>

              {/* Clave / SKU */}
              <div className="productos-form-row">
                <label className="productos-form-label">Clave (SKU):</label>
                <input
                  className="productos-form-input"
                  disabled={!isEditing}
                  value={formData.sku}
                  onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                  style={{ width: 140, fontWeight: 600 }}
                  placeholder="Ej. 01001"
                />
              </div>

              {/* Descripción / Nombre */}
              <div className="productos-form-row">
                <label className="productos-form-label" style={{ color: '#1d4ed8' }}>
                  Descripción:
                </label>
                <input
                  className="productos-form-input highlight-desc"
                  disabled={!isEditing}
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Nombre del Producto (Descripción)"
                  style={{ flex: 1, minWidth: 280 }}
                />
              </div>

              {/* Precio y Precio sin Impuestos */}
              <div className="productos-form-row">
                <label className="productos-form-label">Precio ($ con IVA):</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontWeight: 700, color: '#334155' }}>$</span>
                  <input
                    type="number"
                    step="0.50"
                    className="productos-form-input"
                    disabled={!isEditing}
                    value={formData.price}
                    onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                    style={{ width: 120, fontWeight: 700 }}
                  />
                </div>

                <div style={{ marginLeft: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: '0.825rem', color: '#64748b' }}>Precio sin imp.:</span>
                  <span style={{ fontWeight: 600, color: '#047857', background: '#ecfdf5', padding: '4px 8px', border: '1px solid #a7f3d0', borderRadius: 2 }}>
                    ${priceSinImp.toFixed(4)}
                  </span>
                </div>
              </div>

              {/* IVA y Exenciones */}
              <div className="productos-form-row">
                <label className="productos-form-label">IVA:</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <input
                    type="number"
                    className="productos-form-input"
                    disabled={!isEditing || formData.is_tax_exempt}
                    value={formData.tax_rate}
                    onChange={(e) => setFormData({ ...formData, tax_rate: parseFloat(e.target.value) || 0 })}
                    style={{ width: 70 }}
                  />
                  <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>%</span>
                </div>

                <label style={{ marginLeft: 16, display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.825rem', cursor: isEditing ? 'pointer' : 'default' }}>
                  <input
                    type="checkbox"
                    disabled={!isEditing}
                    checked={formData.is_tax_exempt}
                    onChange={(e) => setFormData({ ...formData, is_tax_exempt: e.target.checked })}
                  />
                  Producto exento de impuestos
                </label>
              </div>

              {/* Unidad y Área de Impresión */}
              <div className="productos-form-row">
                <label className="productos-form-label">Unidad:</label>
                <select
                  className="productos-form-select"
                  disabled={!isEditing}
                  value={formData.unit}
                  onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                  style={{ width: 130 }}
                >
                  <option value="PZA">PZA</option>
                  <option value="ORDEN">ORDEN</option>
                  <option value="COPA">COPA</option>
                  <option value="BOTELLA">BOTELLA</option>
                  <option value="LT">LT</option>
                  <option value="KG">KG</option>
                </select>

                <label style={{ marginLeft: 16, width: 120, fontSize: '0.825rem', fontWeight: 600, color: '#334155' }}>
                  Área de impresión:
                </label>
                <select
                  className="productos-form-select"
                  disabled={!isEditing}
                  value={formData.station}
                  onChange={(e) => setFormData({ ...formData, station: e.target.value })}
                  style={{ minWidth: 150 }}
                >
                  <option value="unassigned">Sin asignar</option>
                  <option value="kitchen">Cocina</option>
                  <option value="drinks">Bebidas</option>
                  <option value="packing">Empaque</option>
                </select>
              </div>

              {/* Utilizar producto en Servicio */}
              <div style={{ marginTop: 6, background: '#f8fafc', padding: 10, border: '1px solid #e2e8f0', borderRadius: 4 }}>
                <div style={{ fontSize: '0.825rem', fontWeight: 700, color: '#1e293b', marginBottom: 8 }}>
                  Utilizar producto en Servicio:
                </div>
                <div className="productos-services-box">
                  <ToggleSwitch label="Comedor" checked={formData.service_dining} onChange={() => isEditing && setFormData({ ...formData, service_dining: !formData.service_dining })} />

                  <ToggleSwitch label="Domicilio" checked={formData.service_delivery} onChange={() => isEditing && setFormData({ ...formData, service_delivery: !formData.service_delivery })} />

                  <ToggleSwitch label="Rápido" checked={formData.service_quick} onChange={() => isEditing && setFormData({ ...formData, service_quick: !formData.service_quick })} />
                </div>
              </div>

              {/* Favorito y Opciones Varias */}
              <div className="productos-form-row" style={{ marginTop: 4 }}>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.825rem', fontWeight: 600, cursor: isEditing ? 'pointer' : 'default' }}>
                  <input
                    type="checkbox"
                    disabled={!isEditing}
                    checked={formData.is_favorite}
                    onChange={(e) => setFormData({ ...formData, is_favorite: e.target.checked })}
                  />
                  <Star size={16} color={formData.is_favorite ? '#eab308' : '#94a3b8'} fill={formData.is_favorite ? '#eab308' : 'none'} />
                  Marcar como Favorito
                </label>
              </div>

              {/* Opciones varias: PLU, Suspendido */}
              <div style={{ borderTop: '1px dashed #cbd5e1', paddingTop: 10, marginTop: 6 }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#64748b', marginBottom: 8 }}>
                  Opciones varias
                </div>
                <div className="productos-form-row">
                  <label className="productos-form-label">P.L.U. / Cód. Barras:</label>
                  <input
                    className="productos-form-input"
                    disabled={!isEditing}
                    value={formData.barcode}
                    onChange={(e) => setFormData({ ...formData, barcode: e.target.value })}
                    style={{ width: 140 }}
                    placeholder="Código de barras"
                  />

                  <label style={{ marginLeft: 16, width: 90, fontSize: '0.825rem', fontWeight: 600, color: '#334155' }}>
                    Suspendido:
                  </label>
                  <select
                    className="productos-form-select"
                    disabled={!isEditing}
                    value={formData.status === 'inactive' ? 'SI' : 'NO'}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value === 'SI' ? 'inactive' : 'active' })}
                    style={{ width: 80 }}
                  >
                    <option value="NO">NO</option>
                    <option value="SI">SI</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Receta / Almacén ventas */}
          {activeTab === 'receta' && (
            <div className="productos-tab-content">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 12, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 4 }}>
                <BookOpen size={24} color="#0284c7" />
                <div>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>Receta y Control de Costos</h4>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                    Vincula los insumos y subrecetas que se descuentan de almacén al preparar este producto.
                  </p>
                </div>
              </div>

              <div style={{ background: '#ffffff', padding: 16, border: '1px solid #cbd5e1', borderRadius: 4, marginTop: 10 }}>
                
                  <div className="sticky-kpi-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, padding: '12px 16px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0, zIndex: 10 }}>
                    <div style={{ display: 'flex', gap: 20 }}>
                      <div>
                        <span style={{ fontSize: '0.8rem', color: '#64748b', display: 'block' }}>Costo Receta</span>
                        <strong className="kpi-cost" style={{ fontSize: '1.2rem', color: '#0f172a' }}>$0.00</strong>
                      </div>
                      <div>
                        <span style={{ fontSize: '0.8rem', color: '#64748b', display: 'block' }}>Margen (Utilidad)</span>
                        <strong className="kpi-margin" style={{ fontSize: '1.2rem', color: '#16a34a' }}>100%</strong>
                      </div>
                    </div>
                    <Badge variant="info">Insumos descontados al preparar</Badge>
                  </div>
                  
                  <div style={{ marginBottom: 16 }}>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 6 }}>Agregar Insumo (Autocompletado)</label>
                    <input className="Typeahead" type="text" placeholder="Buscar insumo por nombre o SKU..." disabled={!isEditing} style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #cbd5e1' }} />
                  </div>

                <p style={{ fontSize: '0.85rem', color: '#475569', lineHeight: 1.5 }}>
                  Las recetas estándar de RestaurantOS operan bajo estricta inmutabilidad y versionado. Para consultar los componentes,
                  costos teóricos o editar la formulación de este producto, accede directamente al módulo de Recetario.
                </p>
                <div style={{ marginTop: 16 }}>
                  <Link
                    to="/recipes"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 16px',
                      background: '#0284c7',
                      color: '#ffffff',
                      textDecoration: 'none',
                      borderRadius: 4,
                      fontWeight: 600,
                      fontSize: '0.85rem',
                    }}
                  >
                    <ExternalLink size={16} /> Abrir Recetario del Sistema
                  </Link>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Precios promoción */}
          {activeTab === 'precios' && (
            <div className="productos-tab-content">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 12, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 4 }}>
                <DollarSign size={24} color="#16a34a" />
                <div>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>Tarifas por Canal y Promociones</h4>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                    Precios diferenciados por servicio y listas de precios para promociones.
                  </p>
                </div>
              </div>

              <table className="productos-table" style={{ marginTop: 14 }}>
                <thead>
                  <tr>
                    <th>Canal / Servicio</th>
                    <th>Margen / Comisión</th>
                    <th style={{ textAlign: 'right' }}>Precio Sugerido</th>
                    <th style={{ textAlign: 'center' }}>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Comedor (En sala)</td>
                    <td>Tarifa base estándar</td>
                    <td style={{ textAlign: 'right', fontWeight: 700 }}>${numericPrice.toFixed(2)}</td>
                    <td style={{ textAlign: 'center' }}><Badge variant="success">Activo</Badge></td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Plataformas Delivery</td>
                    <td>+15% compensación app</td>
                    <td style={{ textAlign: 'right', fontWeight: 700 }}>${(numericPrice * 1.15).toFixed(2)}</td>
                    <td style={{ textAlign: 'center' }}><Badge variant="info">Programable</Badge></td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Servicio Rápido / Barra</td>
                    <td>Tarifa mostrador</td>
                    <td style={{ textAlign: 'right', fontWeight: 700 }}>${numericPrice.toFixed(2)}</td>
                    <td style={{ textAlign: 'center' }}><Badge variant="success">Activo</Badge></td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}

          {/* TAB 4: Imagen de producto */}
          {activeTab === 'imagen' && (
            <div className="productos-tab-content">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 12, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 4 }}>
                <ImageIcon size={24} color="#8b5cf6" />
                <div>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>Fotografía del Producto</h4>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                    Imagen visual para el punto de venta (POS) y carta digital.
                  </p>
                </div>
              </div>

              <div className="productos-form-row" style={{ marginTop: 14 }}>
                <label className="productos-form-label">URL de imagen:</label>
                <input
                  className="productos-form-input"
                  disabled={!isEditing}
                  value={formData.image_url}
                  onChange={(e) => setFormData({ ...formData, image_url: e.target.value })}
                  placeholder="https://servidor.com/imagenes/producto.jpg"
                  style={{ flex: 1 }}
                />
              </div>

              <div style={{ marginTop: 14, display: 'flex', justifyContent: 'center', alignItems: 'center', height: 220, background: '#f1f5f9', border: '2px dashed #cbd5e1', borderRadius: 6, overflow: 'hidden' }}>
                {formData.image_url ? (
                  <img
                    src={formData.image_url}
                    alt={formData.name || 'Vista previa'}
                    style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                ) : (
                  <div style={{ textAlign: 'center', color: '#94a3b8' }}>
                    <ImageIcon size={48} style={{ margin: '0 auto 8px' }} />
                    <p style={{ margin: 0, fontSize: '0.85rem' }}>Sin imagen configurada</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 5: Monedero electrónico */}
          {activeTab === 'monedero' && (
            <div className="productos-tab-content">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 12, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 4 }}>
                <Award size={24} color="#eab308" />
                <div>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>Monedero Electrónico y Lealtad</h4>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                    Parámetros de puntos y recompensas acumulables por la compra de este artículo.
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 14, padding: 14, background: '#ffffff', border: '1px solid #cbd5e1' }}>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', fontWeight: 600 }}>
                  <input type="checkbox" defaultChecked /> Acumula puntos en monedero del cliente (10% del consumo)
                </label>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', fontWeight: 600 }}>
                  <input type="checkbox" defaultChecked /> Permite pago total o parcial con saldo de monedero
                </label>
                <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 4 }}>
                  Puntos equivalentes acreditados por unidad vendida:{' '}
                  <span style={{ fontWeight: 700, color: '#047857' }}>{Math.round(numericPrice * 0.1)} pts</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: Comentarios de preparación / Paquete */}
          {activeTab === 'paquete' && (
            <div className="productos-tab-content">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 12, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 4 }}>
                <MessageSquare size={24} color="#6366f1" />
                <div>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>Comentarios de Cocina y Paquetes (Combos)</h4>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                    Instrucciones estándar de preparación y configuración de paquetes de productos.
                  </p>
                </div>
              </div>

              <div style={{ marginTop: 14 }}>
                <label className="productos-form-label" style={{ display: 'block', marginBottom: 6 }}>
                  Comentarios frecuentes de preparación:
                </label>
                <textarea
                  className="productos-form-input"
                  disabled={!isEditing}
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  placeholder="Ej. Término medio, sin cebolla, salsa aparte..."
                  rows={3}
                  style={{ width: '100%', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginTop: 18, padding: 16, background: '#f8fafc', border: '2px dashed #6366f1', borderRadius: 6 }}>
                <h4 style={{ margin: '0 0 6px', fontSize: '0.9rem', fontWeight: 700, color: '#3730a3' }}>
                  Composición fija (Combo o Paquete)
                </h4>
                <p style={{ margin: '0 0 12px', fontSize: '0.825rem', color: '#4b5563' }}>
                  Define los artículos incluidos en este producto si corresponde a un combo o menú en paquete.
                </p>
                <button
                  type="button"
                  className="productos-action-btn"
                  style={{ background: '#e0e7ff', borderColor: '#a5b4fc', color: '#312e81' }}
                  disabled={!selectedProduct && !isNew}
                  onClick={() => selectedProduct && setCompositionProduct(selectedProduct)}
                >
                  <Layers size={16} /> Composición fija (Configurar Combo)
                </button>
              </div>
            </div>
          )}

          {/* TAB 7: Producto compuesto */}
          {activeTab === 'modificadores' && (
            <div className="productos-tab-content">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 12, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 4 }}>
                <SlidersHorizontal size={24} color="#0891b2" />
                <div>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>Modificadores y Complementos</h4>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                    Agrega grupos de opciones (aderezos, guarniciones, términos de carne) aplicables a este producto.
                  </p>
                </div>
              </div>

              <div style={{ marginTop: 20, padding: 16, background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 6 }}>
                <h4 style={{ margin: '0 0 6px', fontSize: '0.9rem', fontWeight: 700, color: '#166534' }}>
                  Gestor de Modificadores
                </h4>
                <p style={{ margin: '0 0 14px', fontSize: '0.825rem', color: '#15803d' }}>
                  Personaliza los extras con costo y selecciones forzosas al ordenar en mesa o delivery.
                </p>
                <button
                  type="button"
                  className="productos-action-btn"
                  style={{ background: '#0284c7', borderColor: '#0369a1', color: '#ffffff' }}
                  disabled={!selectedProduct && !isNew}
                  onClick={() => selectedProduct && setModifierProduct(selectedProduct)}
                >
                  <SlidersHorizontal size={16} /> Administrar Modificadores del Producto
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. Subgrupos de productos Modal Dialog (Soft Restaurant match from image 2) */}
      {isSubgroupsModalOpen && (
        <div className="retro-modal-overlay">
          <div className="retro-modal-window" style={{ maxWidth: 740 }}>
            <div className="retro-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <FolderPlus size={18} />
                Subgrupos de productos
              </div>
              <button
                className="productos-win-btn close"
                onClick={() => setIsSubgroupsModalOpen(false)}
              >
                ✕
              </button>
            </div>

            {/* Subgroups mini toolbar */}
            <div style={{ display: 'flex', gap: 6, background: '#e2e8f0', padding: '6px 10px', borderBottom: '1px solid #cbd5e1' }}>
              <button
                className="productos-action-btn"
                onClick={() => {
                  setSelectedSubgroup(null);
                  setSubgroupForm({
                    code: (subgroups.length + 1).toString().padStart(2, '0'),
                    name: '',
                    category_name: formData.category_name || (categories[0]?.name ?? ''),
                  });
                }}
              >
                <Plus size={14} color="#16a34a" /> Nuevo
              </button>
              <button
                className="productos-action-btn save-highlight"
                disabled={!subgroupForm.name.trim() || !subgroupForm.code.trim()}
                onClick={() => {
                  if (subgroupForm.name.trim()) {
                    const newSg: SubgroupItem = {
                      id: (Date.now()).toString(),
                      code: subgroupForm.code.trim(),
                      name: subgroupForm.name.trim().toUpperCase(),
                      category_name: subgroupForm.category_name,
                    };
                    setSubgroups((prev) => [...prev, newSg]);
                    setFormData((prev) => ({ ...prev, subgroup: newSg.name }));
                    setSelectedSubgroup(newSg);
                  }
                }}
              >
                <Save size={14} color="#047857" /> Guardar
              </button>
              <button
                className="productos-action-btn"
                onClick={() => setIsSubgroupsModalOpen(false)}
              >
                <X size={14} /> Cerrar
              </button>
            </div>

            {/* Subgroups 2-column layout */}
            <div style={{ display: 'grid', gridTemplateColumns: '55% 45%', padding: 12, gap: 12, background: '#f8fafc' }}>
              {/* Table */}
              <div style={{ maxHeight: 280, overflowY: 'auto', border: '1px solid #94a3b8', background: '#fff' }}>
                <table className="productos-table">
                  <thead>
                    <tr>
                      <th style={{ width: '25%' }}>Clave</th>
                      <th style={{ width: '35%' }}>Grupo</th>
                      <th style={{ width: '40%' }}>Descripción</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subgroups.map((sg) => (
                      <tr
                        key={sg.id}
                        className={selectedSubgroup?.id === sg.id ? 'active' : ''}
                        onClick={() => {
                          setSelectedSubgroup(sg);
                          setSubgroupForm({ code: sg.code, name: sg.name, category_name: sg.category_name });
                          setFormData((prev) => ({ ...prev, subgroup: sg.name }));
                        }}
                      >
                        <td>{sg.code}</td>
                        <td>{sg.category_name}</td>
                        <td>{sg.name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Form */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, background: '#fff', padding: 12, border: '1px solid #cbd5e1' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: 4 }}>Clave:</label>
                  <input
                    className="productos-form-input"
                    value={subgroupForm.code}
                    onChange={(e) => setSubgroupForm({ ...subgroupForm, code: e.target.value })}
                    style={{ width: 90 }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: 4 }}>Descripción:</label>
                  <input
                    className="productos-form-input highlight-desc"
                    value={subgroupForm.name}
                    onChange={(e) => setSubgroupForm({ ...subgroupForm, name: e.target.value })}
                    style={{ width: '100%', boxSizing: 'border-box' }}
                    placeholder="Ej. AGUA CHICA"
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: 4 }}>Grupo:</label>
                  <select
                    className="productos-form-select"
                    value={subgroupForm.category_name}
                    onChange={(e) => setSubgroupForm({ ...subgroupForm, category_name: e.target.value })}
                    style={{ width: '100%' }}
                  >
                    {categories.map((cat: Category) => (
                      <option key={cat.id} value={cat.name}>
                        {cat.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. Quick Category Creation Modal */}
      {isCategoryModalOpen && (
        <div className="retro-modal-overlay">
          <div className="retro-modal-window" style={{ maxWidth: 420 }}>
            <div className="retro-modal-header">
              <span>Nuevo Grupo de Productos</span>
              <button className="productos-win-btn close" onClick={() => setIsCategoryModalOpen(false)}>✕</button>
            </div>
            <div className="retro-modal-body">
              <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>Nombre del grupo:</label>
              <input
                className="productos-form-input highlight-desc"
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                placeholder="Ej. BEBIDAS, PLATILLOS..."
                autoFocus
              />
            </div>
            <div className="retro-modal-footer">
              <button className="productos-action-btn" onClick={() => setIsCategoryModalOpen(false)}>Cancelar</button>
              <button
                className="productos-action-btn save-highlight"
                disabled={!newCategoryName.trim() || createCategoryMutation.isPending}
                onClick={() => createCategoryMutation.mutate(newCategoryName)}
              >
                {createCategoryMutation.isPending ? 'Creando...' : 'Crear Grupo'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* External Subsystem Modals */}
      {modifierProduct && (
        <ModifierManager
          isOpen
          productId={modifierProduct.id}
          productName={modifierProduct.name}
          onClose={() => setModifierProduct(null)}
        />
      )}

      {compositionProduct && (
        <ComboCompositionModal
          product={compositionProduct}
          onClose={() => setCompositionProduct(null)}
        />
      )}

      <ProductOnboardingAiModal
        isOpen={isAiOnboardingOpen}
        onClose={() => setIsAiOnboardingOpen(false)}
      />
    </div>
  );
}

const ProductsList = () => {
  return (
    <ProductosErrorBoundary>
      <ProductsListInner />
    </ProductosErrorBoundary>
  );
};

export default ProductsList;
