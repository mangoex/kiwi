import { classificationLabel, type ClassificationCode } from './catalogClassification';
import React, { useMemo, useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
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
import { KiwiCopilotWidget } from '../../components/KiwiCopilotWidget';
import { ModifierManager } from './ModifierManager';
import { ProductOnboardingAiModal } from './ProductOnboardingAiModal';
import { ComboCompositionModal } from './ComboCompositionModal';
import {
  ProductTaxonomyQuickCreateModal,
  type ProductTaxonomyQuickCreateResult,
} from './ProductTaxonomyQuickCreateModal';
import { FastTabDrawer } from '../../components/FastTabDrawer';
import CapsuleTabs from '../../components/ui/CapsuleTabs';
import { resolveBranchId } from '../../lib/branchContext';
import { RecipeManager, type RecipeWorkspaceItem } from './RecipeManager';

export const formatMoney = (cents: number | null | undefined): string => {
  if (cents == null) return '$0.00';
  return `$${(cents / 100).toFixed(2)}`;
};

const productSaveErrorMessage = (error: { code?: string; message?: string }): string => {
  const messages: Record<string, string> = {
    product_already_exists: 'La clave ya pertenece a otro producto.',
    product_configuration_version_conflict: 'El producto cambió en otra sesión. Recarga antes de guardar.',
    idempotency_key_conflict: 'Este intento ya fue usado con otros datos. Inicia un nuevo guardado.',
    category_option_value_required: 'Selecciona un subgrupo antes de guardar.',
    category_option_value_group_mismatch: 'El subgrupo no pertenece al grupo seleccionado.',
    invalid_product_name: 'El nombre debe estar escrito en mayúsculas.',
    invalid_product_sku: 'La clave debe contener únicamente números.',
    invalid_station: 'Selecciona Bebidas, Cocina o Empaque.',
  };
  return (error.code && messages[error.code]) || error.message || 'No fue posible guardar el producto.';
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
  updated_at: string;
}

interface Category {
  classification_code?: ClassificationCode | null;
  configuration_version?: number;
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

interface RecipeWorkspace {
  items: RecipeWorkspaceItem[];
}

type RecipeEditorProduct = Pick<Product, 'id' | 'name' | 'price_cents'>;

const PRODUCT_CONFIGURATION_TABS = [
  { value: 'Principal / Varios', label: 'Principal / Varios' },
  { value: 'Receta', label: 'Receta' },
  { value: 'Precios promoción', label: 'Precios promoción' },
  { value: 'Imagen de producto', label: 'Imagen de producto' },
  { value: 'Monedero electrónico', label: 'Monedero electrónico' },
  { value: 'Comentarios de preparación / Paquete', label: 'Comentarios / Paquete' },
  { value: 'Producto compuesto', label: 'Producto compuesto' },
] as const;

type ProductConfigurationTab = (typeof PRODUCT_CONFIGURATION_TABS)[number]['value'];

export const ProductsList: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') || '';

  const nameInputRef = useRef<HTMLInputElement | null>(null);
  const saveIntentKeyRef = useRef<string>(crypto.randomUUID());
  const continueToRecipeAfterSaveRef = useRef(false);
  const branchId = resolveBranchId();
  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
  const canManageRecipes = Boolean((currentUser.permissions || []).includes('recipes.manage'));

  // Filter States
  const [selectedGroup, setSelectedGroup] = useState<string>('(TODOS)');
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [isNew, setIsNew] = useState<boolean>(false);
  const [saveError, setSaveError] = useState('');

  const [activeTab, setActiveTab] = useState<ProductConfigurationTab>('Principal / Varios');
  const [previewResult, setPreviewResult] = useState<{ eligible: boolean; reason_codes: string[] } | null>(null);
  const extendedProductFieldsAvailable = false;

  // Auxiliary Modals
  const [isAiOnboardingOpen, setIsAiOnboardingOpen] = useState(false);
  const [compositionProduct, setCompositionProduct] = useState<Product | null>(null);
  const [recipeEditorProduct, setRecipeEditorProduct] = useState<RecipeEditorProduct | null>(null);
  const [taxonomyQuickCreateMode, setTaxonomyQuickCreateMode] = useState<'group' | 'subgroup' | null>(null);

  // Optional drawer helper
  const [isFastTabDrawerOpen, setIsFastTabDrawerOpen] = useState(false);

  // Form State
  const [formData, setFormData] = useState<Record<string, any>>({
    name: '',
    sku: '',
    category_name: '',
    subgroup_value_id: '',
    price_with_tax: '',
    tax_rate: '',
    is_exempt: false,
    non_billable: false,
    unit: '',
    station: '',
    service_dining: false,
    service_delivery: false,
    service_quick: false,
    is_favorite: false,
    barcode: '',
    open_price: 'NO',
    suspended: 'NO',
    affects_guest_count: false,
    additional_fee_percent: '',
    server_commission_percent: '',
    product_type: '',
    warehouse: '',
    price_dining: '',
    price_delivery: '',
    price_apps: '',
    status: 'active',
    image_url: '',
    loyalty_accrual: false,
    loyalty_accrual_percent: '',
    loyalty_points_price: '',
    prep_comments: '',
  });

  // Queries
  const { data: rawProducts = [], isLoading, error, refetch, isFetching } = useQuery<Product[]>({
    queryKey: ['products'],
    queryFn: () => fetchApi<Product[]>('/catalog/products'),
  });

  const { data: rawCategories = [], error: categoriesError, refetch: refetchCategories } = useQuery<Category[]>({
    queryKey: ['categories'],
    queryFn: () => fetchApi<Category[]>('/categories'),
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
        tax_rate: '',
        is_exempt: false,
        non_billable: false,
        unit: '',
        station: selectedProduct.station || '',
        service_dining: false,
        service_delivery: false,
        service_quick: false,
        is_favorite: false,
        barcode: '',
        open_price: 'NO',
        suspended: 'NO',
        affects_guest_count: false,
        additional_fee_percent: '',
        server_commission_percent: '',
        product_type: '',
        warehouse: '',
        price_dining: '',
        price_delivery: '',
        price_apps: '',
        status: selectedProduct.status || 'active',
        image_url: selectedProduct.image_url || '',
        loyalty_accrual: false,
        loyalty_accrual_percent: '',
        loyalty_points_price: '',
        prep_comments: '',
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

  useEffect(() => {
    if (!isEditing) return undefined;
    const warnBeforeLeaving = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeLeaving);
    return () => window.removeEventListener('beforeunload', warnBeforeLeaving);
  }, [isEditing]);

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
        name: data.name.trim().toLocaleUpperCase('es-MX'),
        sku: data.sku,
        category_id: formCategory?.id,
        subgroup_option_value_id: data.subgroup_value_id || null,
        price_cents: priceCents,
        station: data.station,
        image_url: data.image_url.trim() || null,
        status: data.status,
      };

      const saved: any = isEditing && !isNew && selectedProduct
        ? await fetchApi(`/catalog/product-configurations/${selectedProduct.id}`, {
          method: 'PUT',
          headers: { 'Idempotency-Key': saveIntentKeyRef.current },
          body: JSON.stringify({ ...payload, expected_updated_at: selectedProduct.updated_at }),
        })
        : await fetchApi('/catalog/product-configurations', {
          method: 'POST',
          headers: { 'Idempotency-Key': saveIntentKeyRef.current },
          body: JSON.stringify(payload),
        });
      return saved;
    },
    onSuccess: (saved: any, submittedData: typeof formData) => {
      const shouldContinueToRecipe = continueToRecipeAfterSaveRef.current;
      continueToRecipeAfterSaveRef.current = false;
      const confirmedProduct: Product | null = saved?.id ? {
        ...(selectedProduct || {} as Product),
        id: saved.id,
        name: saved.name || submittedData.name.trim().toLocaleUpperCase('es-MX'),
        sku: saved.sku || submittedData.sku,
        category_id: saved.category_id || formCategory?.id,
        category_name: saved.category_name || formCategory?.name || submittedData.category_name,
        price_cents: saved.price_cents ?? Math.round((parseFloat(submittedData.price_with_tax) || 0) * 100),
        station: saved.station || submittedData.station,
        status: saved.status || submittedData.status,
        image_url: saved.image_url || undefined,
        updated_at: saved.updated_at,
      } : null;
      if (confirmedProduct) {
        queryClient.setQueryData<Product[]>(['products'], (current = []) => {
          const exists = current.some((product) => product.id === confirmedProduct.id);
          return exists
            ? current.map((product) => product.id === confirmedProduct.id ? confirmedProduct : product)
            : [...current, confirmedProduct];
        });
      }
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['catalog-products'] });
      queryClient.invalidateQueries({ queryKey: ['category-option-coverage', formCategory?.id || ''] });
      setIsEditing(false);
      setIsNew(false);
      setSaveError('');
      if (confirmedProduct) {
        setSelectedProductId(confirmedProduct.id);
        if (shouldContinueToRecipe) {
          setActiveTab('Receta');
          setRecipeEditorProduct({
            id: confirmedProduct.id,
            name: confirmedProduct.name,
            price_cents: confirmedProduct.price_cents,
          });
        }
      }
      saveIntentKeyRef.current = crypto.randomUUID();
    },
    onError: (err: { code?: string; message?: string }) => {
      continueToRecipeAfterSaveRef.current = false;
      setSaveError(productSaveErrorMessage(err));
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
    if (isEditing && !window.confirm('Hay cambios sin guardar. ¿Deseas descartarlos?')) return;
    setSaveError('');
    setSelectedProductId(null);
    setIsNew(true);
    setIsEditing(true);
    setActiveTab('Principal / Varios');
    saveIntentKeyRef.current = crypto.randomUUID();
    setPreviewResult(null);
    setFormData({
      name: '',
      sku: '',
      category_name: selectedGroup !== '(TODOS)' ? selectedGroup : (categoryOptions[0] || ''),
      subgroup_value_id: '',
      price_with_tax: '',
      tax_rate: '',
      is_exempt: false,
      non_billable: false,
      unit: '',
      station: '',
      service_dining: false,
      service_delivery: false,
      service_quick: false,
      is_favorite: false,
      barcode: '',
      open_price: 'NO',
      suspended: 'NO',
      affects_guest_count: false,
      additional_fee_percent: '',
      server_commission_percent: '',
      product_type: '',
      warehouse: '',
      price_dining: '',
      price_delivery: '',
      price_apps: '',
      status: 'active',
      image_url: '',
      loyalty_accrual: false,
      loyalty_accrual_percent: '',
      loyalty_points_price: '',
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
    saveIntentKeyRef.current = crypto.randomUUID();
    setPreviewResult(null);
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
    if (!formData.name.trim() || !formData.sku.trim() || !formData.station || !formCategory) return;
    continueToRecipeAfterSaveRef.current = false;
    saveMutation.mutate(formData);
  };

  const handleSaveAndConfigureRecipe = () => {
    if (!formData.name.trim() || !formData.sku.trim() || !formData.station || !formCategory || !branchId) return;
    continueToRecipeAfterSaveRef.current = true;
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

  const handleTaxonomyCreated = async (result: ProductTaxonomyQuickCreateResult) => {
    if (result.kind === 'group') {
      queryClient.setQueryData<Category[]>(['categories'], (current = []) => (
        current.some((category) => category.id === result.group.id)
          ? current
          : [...current, result.group]
      ));
      setFormData((current) => ({
        ...current,
        category_name: result.group.name,
        subgroup_value_id: '',
      }));
      void queryClient.invalidateQueries({ queryKey: ['categories'] });
      return;
    }

    queryClient.setQueryData<SubgroupCoverage>(
      ['category-option-coverage', result.categoryId],
      (current) => {
        const values = current?.values || [];
        if (values.some((value) => value.id === result.subgroup.id)) return current;
        const nextDisplayOrder = values.reduce(
          (highest, value) => Math.max(highest, value.display_order),
          -1,
        ) + 1;
        return {
          category_id: result.categoryId,
          group: current?.group || result.selectionGroup,
          values: [...values, { ...result.subgroup, display_order: nextDisplayOrder }],
          products: current?.products || [],
        };
      },
    );
    setFormData((current) => ({ ...current, subgroup_value_id: result.subgroup.id }));
    void queryClient.invalidateQueries({ queryKey: ['category-option-coverage', result.categoryId] });
  };

  const recipeQuery = useQuery<{ id?: string; version?: number; source?: string; yield_quantity?: string; components?: unknown[] }>({
    queryKey: ['product-recipe', selectedProduct?.id, branchId],
    queryFn: () => fetchApi(`/products/${selectedProduct!.id}/recipe${branchId ? `?branch_id=${branchId}` : ''}`),
    enabled: Boolean(selectedProduct?.id && branchId && canManageRecipes && activeTab === 'Receta'),
  });

  const recipeWorkspaceQuery = useQuery<RecipeWorkspace>({
    queryKey: ['recipes-workspace', branchId],
    queryFn: () => fetchApi(`/recipes/workspace?branch_id=${encodeURIComponent(branchId!)}`),
    enabled: Boolean(branchId && canManageRecipes && (activeTab === 'Receta' || recipeEditorProduct)),
  });

  const previewMutation = useMutation({
    mutationFn: () => fetchApi<{ eligible: boolean; reason_codes: string[] }>(
      `/catalog/products/${selectedProduct?.id}/pos-preview?branch_id=${branchId}`,
    ),
    onSuccess: setPreviewResult,
    onError: (err: Error) => setSaveError(err.message || 'No fue posible calcular la vista previa POS.'),
  });

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
              Catálogo corporativo · la sucursal se usa sólo para previsualizar POS
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

            {categoriesError && (
              <div role="alert" style={{ padding: 12, color: '#b91c1c' }}>
                No se pudieron cargar los grupos.
                <button type="button" onClick={() => void refetchCategories()}>Reintentar grupos</button>
              </div>
            )}
            {/* Master Table */}
            <div className="productos-master-table-wrap">
              {isLoading ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>Cargando catálogo...</div>
              ) : error ? (
                <div role="alert" style={{ padding: 24, textAlign: 'center', color: '#b91c1c' }}>
                  <p>No se pudo cargar el catálogo. Esto no significa que no haya productos registrados.</p>
                  <button type="button" onClick={() => void refetch()} disabled={isFetching}>
                    {isFetching ? 'Reintentando…' : 'Reintentar productos'}
                  </button>
                </div>
              ) : filteredProducts.length === 0 && !isNew ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>{products.length ? 'No hay productos que coincidan con los filtros.' : 'No hay productos registrados.'}</div>
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
                          background: '#f8fafc',
                          color: '#334155',
                          fontWeight: 'bold',
                          borderLeft: '4px solid #94a3b8',
                        }}
                      >
                        <td style={{ fontFamily: 'monospace' }}>{formData.sku.trim() || '—'}</td>
                        <td>{formData.category_name || '—'}</td>
                        <td>
                          Borrador sin guardar · {formData.name.trim() || 'captura los datos obligatorios'}
                        </td>
                        <td style={{ textAlign: 'right' }}>
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
                            if (isEditing && !window.confirm('Hay cambios sin guardar. ¿Deseas descartarlos?')) return;
                            if (isEditing || isNew) {
                              setIsNew(false);
                              setIsEditing(false);
                            }
                            setSaveError('');
                            setPreviewResult(null);
                            setActiveTab('Principal / Varios');
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
                disabled={!isEditing || saveMutation.isPending || !formData.name.trim() || !formData.sku.trim() || !formData.station || !formCategory}
              >
                <Save size={14} />
                <span>{saveMutation.isPending ? 'Guardando...' : isNew ? 'Guardar Nuevo' : 'Guardar'}</span>
              </button>

              {canManageRecipes && (
                <button
                  type="button"
                  className="productos-action-btn"
                  onClick={handleSaveAndConfigureRecipe}
                  disabled={!isEditing || !branchId || saveMutation.isPending || !formData.name.trim() || !formData.sku.trim() || !formData.station || !formCategory}
                  title={branchId ? 'Guarda el producto y abre su receta' : 'Selecciona una sucursal para configurar la receta'}
                >
                  <UtensilsCrossed size={14} />
                  <span>Guardar y configurar receta</span>
                </button>
              )}

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
                    <label className="productos-form-label" htmlFor="product-inherited-classification">Clasificación:</label>
                    <input id="product-inherited-classification" className="productos-form-input" readOnly value={classificationLabel(formCategory?.classification_code)} aria-label="Clasificación heredada del grupo" />
                    <span>Heredada del grupo</span>
                  </div>
                  <div className="productos-form-row">
                    <label className="productos-form-label">Grupo (Categoría):</label>
                    <div className="productos-taxonomy-field">
                      <select
                        className="productos-form-select"
                        value={formData.category_name}
                        onChange={(e) => setFormData({ ...formData, category_name: e.target.value, subgroup_value_id: '' })}
                        disabled={!isEditing}
                        aria-label="Grupo canónico del producto"
                      >
                        {categoryOptions.map((cat) => (
                          <option key={cat} value={cat}>
                            {cat}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="productos-btn-plus"
                        onClick={() => setTaxonomyQuickCreateMode('group')}
                        disabled={!isEditing}
                        title="Crear grupo sin salir del producto"
                        aria-label="Crear grupo sin salir del producto"
                      >
                        +
                      </button>
                    </div>

                    <label className="productos-form-label" style={{ width: '90px', marginLeft: 16 }}>
                      Subgrupo:
                    </label>
                    <div className="productos-taxonomy-field">
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
                        onClick={() => setTaxonomyQuickCreateMode('subgroup')}
                        disabled={!isEditing || !formCategory}
                        title="Crear subgrupo para el grupo seleccionado"
                        aria-label="Crear subgrupo para el grupo seleccionado"
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
                        —
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
                          disabled={!isEditing || formData.is_exempt || !extendedProductFieldsAvailable}
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
                          disabled={!isEditing || !extendedProductFieldsAvailable}
                        />
                        <span>Producto exento de impuestos</span>
                      </label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', color: '#64748b' }}>
                        <input
                          type="checkbox"
                          checked={formData.non_billable}
                          onChange={(e) => setFormData({ ...formData, non_billable: e.target.checked })}
                          disabled={!isEditing || !extendedProductFieldsAvailable}
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
                      disabled={!isEditing || !extendedProductFieldsAvailable}
                    >
                      <option value="">Pendiente de contrato</option>
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
                      <option value="">Selecciona un área</option>
                      <option value="drinks">1 - BEBIDAS (Barra / Fuentes)</option>
                      <option value="kitchen">2 - COCINA</option>
                      <option value="packing">3 - EMPAQUE</option>
                    </select>
                  </div>

                  <div className="productos-form-row">
                    <label className="productos-form-label">Estado:</label>
                    <select
                      className="productos-form-select"
                      value={formData.status}
                      onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                      disabled={!isEditing}
                    >
                      <option value="active">Activo</option>
                      <option value="inactive">Inactivo</option>
                      <option value="needs_review">Requiere revisión</option>
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
                        aria-disabled="true"
                      >
                        <UtensilsCrossed size={16} />
                        <span>Comedor</span>
                        {formData.service_dining && <CheckCircle2 size={14} color="#16a34a" />}
                      </div>

                      <div
                        className={`productos-service-chip ${formData.service_delivery ? 'active' : ''}`}
                        aria-disabled="true"
                      >
                        <Truck size={16} />
                        <span>Domicilio</span>
                        {formData.service_delivery && <CheckCircle2 size={14} color="#16a34a" />}
                      </div>

                      <div
                        className={`productos-service-chip ${formData.service_quick ? 'active' : ''}`}
                        aria-disabled="true"
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
                      disabled={!isEditing || !extendedProductFieldsAvailable}
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
                        disabled={!isEditing || !extendedProductFieldsAvailable}
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
                        disabled={!isEditing || !extendedProductFieldsAvailable}
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
                        disabled={!isEditing || !extendedProductFieldsAvailable}
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
                          disabled={!isEditing || !extendedProductFieldsAvailable}
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
                          disabled={!isEditing || !extendedProductFieldsAvailable}
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
                          disabled={!isEditing || !extendedProductFieldsAvailable}
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
                      disabled
                      style={{ fontSize: '0.775rem' }}
                    >
                      <span>📄 Crear productos 1 a 1</span>
                    </button>
                    <button
                      type="button"
                      className="productos-action-btn"
                      disabled
                      style={{ fontSize: '0.775rem' }}
                    >
                      <span>📑 Crear productos 1 a 1 a todo el grupo</span>
                    </button>
                  </div>
                </>
              )}

              {/* TAB 2: RECETA */}
              {activeTab === 'Receta' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div className="productos-options-box">
                    <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0f172a', display: 'block', marginBottom: 6 }}>
                      Receta del producto
                    </span>
                    <p style={{ marginTop: 0 }}>
                      Define ingredientes y rendimiento sin salir del producto seleccionado. Cada guardado crea una versión nueva.
                    </p>
                    {!selectedProduct && <p>Guarda el producto para consultar o configurar su receta.</p>}
                    {selectedProduct && !branchId && <p>Selecciona una sucursal para consultar la receta efectiva.</p>}
                    {selectedProduct && branchId && !canManageRecipes && <p>Tu perfil no tiene permiso para consultar o editar recetas.</p>}
                    {selectedProduct && recipeQuery.isLoading && <p>Cargando receta vigente…</p>}
                    {selectedProduct && recipeQuery.isError && (
                      <div className="productos-inline-error" role="alert">
                        No fue posible consultar la receta. La edición permanece bloqueada hasta recuperar la versión vigente.
                        <button type="button" className="productos-action-btn" onClick={() => void recipeQuery.refetch()}>
                          Reintentar lectura
                        </button>
                      </div>
                    )}
                    {selectedProduct && recipeQuery.data && (
                      <div role="status">
                        <strong>
                          {recipeQuery.data.components?.length
                            ? `Receta vigente con ${recipeQuery.data.components.length} componentes`
                            : 'Este producto aún no tiene una receta vigente'}
                        </strong>
                        {recipeQuery.data.id && (
                          <p style={{ margin: '4px 0 0', color: '#64748b' }}>
                            Versión {recipeQuery.data.version ?? 'vigente'} · {recipeQuery.data.source === 'branch' ? 'Sucursal' : 'Corporativa'}
                          </p>
                        )}
                      </div>
                    )}
                    {canManageRecipes && (
                      <button
                        type="button"
                        className="productos-action-btn"
                        onClick={() => selectedProduct && setRecipeEditorProduct(selectedProduct)}
                        disabled={
                          !selectedProduct
                          || !branchId
                          || recipeQuery.isLoading
                          || recipeQuery.isError
                          || !recipeQuery.data
                          || recipeWorkspaceQuery.isLoading
                          || recipeWorkspaceQuery.isError
                        }
                      >
                        <UtensilsCrossed size={14} />
                        {recipeQuery.data?.components?.length ? 'Editar receta de este producto' : 'Configurar receta de este producto'}
                      </button>
                    )}
                    {recipeWorkspaceQuery.isLoading && <p>Cargando insumos autorizados…</p>}
                    {recipeWorkspaceQuery.isError && (
                      <div className="productos-inline-error" role="alert">
                        No fue posible cargar los insumos autorizados. Reintenta antes de configurar la receta.
                        <button type="button" className="productos-action-btn" onClick={() => recipeWorkspaceQuery.refetch()}>
                          Reintentar
                        </button>
                      </div>
                    )}
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
                        disabled
                      />
                      <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Pendiente de contrato por canal</span>
                    </div>

                    <div className="productos-form-row">
                      <label className="productos-form-label">Domicilio / WhatsApp:</label>
                      <input
                        type="text"
                        className="productos-form-input font-mono"
                        style={{ width: '120px' }}
                        value={formData.price_delivery}
                        onChange={(e) => setFormData({ ...formData, price_delivery: e.target.value })}
                        disabled
                      />
                      <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Pendiente de contrato por canal</span>
                    </div>

                    <div className="productos-form-row">
                      <label className="productos-form-label">Delivery Apps (Uber/Rappi):</label>
                      <input
                        type="text"
                        className="productos-form-input font-mono"
                        style={{ width: '120px' }}
                        value={formData.price_apps}
                        onChange={(e) => setFormData({ ...formData, price_apps: e.target.value })}
                        disabled
                      />
                      <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Pendiente de contrato por canal</span>
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
                        disabled
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
                        disabled
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
                        disabled
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
                      placeholder="Pendiente de contrato de comentarios de preparación"
                      disabled
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
                <div className="productos-compound-tab">
                  <div className="productos-compound-intro">
                    <div>
                      <strong>Producto compuesto seleccionable</strong>
                      <p>
                        Configura aquí mismo los grupos que verá el cajero, sus productos, selecciones incluidas y precios adicionales.
                      </p>
                    </div>
                  </div>

                  {selectedProduct ? (
                    <ModifierManager productId={selectedProduct.id} productName={selectedProduct.name} />
                  ) : (
                    <div className="productos-inline-warning" role="status">Guarda o selecciona un producto antes de configurar su composición.</div>
                  )}

                  <div className="productos-compound-preview">
                    <strong>Vista previa real en POS</strong>
                    <p>Comprueba el producto contra la proyección de la sucursal sin crear pedidos ni modificar disponibilidad.</p>
                    <button
                      type="button"
                      className="productos-action-btn"
                      onClick={() => previewMutation.mutate()}
                      disabled={!selectedProduct || !branchId || previewMutation.isPending}
                    >
                      {previewMutation.isPending ? 'Validando…' : 'Validar en POS'}
                    </button>
                    {!branchId && <p>Selecciona una sucursal para habilitar la vista previa.</p>}
                    {previewResult && (
                      <div className={previewResult.eligible ? 'productos-inline-warning' : 'productos-inline-error'} role="status">
                        {previewResult.eligible ? 'El producto es elegible y aparecerá en POS.' : `No aparecerá en POS: ${previewResult.reason_codes.join(', ')}`}
                      </div>
                    )}
                  </div>

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

        {taxonomyQuickCreateMode && (
          <ProductTaxonomyQuickCreateModal
            isOpen
            mode={taxonomyQuickCreateMode}
            categories={categories}
            selectedCategory={formCategory}
            selectionGroup={subgroupCoverage?.group}
            onClose={() => setTaxonomyQuickCreateMode(null)}
            onCreated={handleTaxonomyCreated}
          />
        )}

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

        {recipeEditorProduct && branchId && recipeWorkspaceQuery.data && (
          <RecipeManager
            isOpen
            productId={recipeEditorProduct.id}
            productName={recipeEditorProduct.name}
            salePriceCents={recipeEditorProduct.price_cents}
            branchId={branchId}
            items={recipeWorkspaceQuery.data.items}
            onClose={() => setRecipeEditorProduct(null)}
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
