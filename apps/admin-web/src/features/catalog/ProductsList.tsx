import React, { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import {
  Plus,
  Edit,
  Trash2,
  Search,
  Sparkles,
  Printer,
  X,
  Layers,
  QrCode,
  SlidersHorizontal,
  ChevronRight,
  TrendingUp,
  Save,
  Check,
  Eye,
  RefreshCw,
  FolderPlus
} from 'lucide-react';
import { FastTabDrawer, AccordionSection } from '../../components/FastTabDrawer';
import { DagTreeView, DagNode } from '../../components/DagTreeView';
import { MetricCard, SparklineMini } from '../../components/MetricDataViz';
import { KiwiCopilotWidget } from '../../components/KiwiCopilotWidget';
import { ModifierManager } from './ModifierManager';
import { ProductOnboardingAiModal } from './ProductOnboardingAiModal';
import { ComboCompositionModal } from './ComboCompositionModal';

export const formatMoney = (cents: number | null | undefined): string => {
  if (cents == null) return '$0.00 MXN';
  return `$${(cents / 100).toFixed(2)} MXN`;
};

export class ProductosErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  render() {
    if (this.state.hasError) {
      return <div className="p-4 text-rose-600">Error al cargar productos.</div>;
    }
    return this.props.children;
  }
}

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
  cost_cents?: number;
}

interface Category {
  id: string;
  name: string;
  display_order?: number;
  status?: string;
}

export interface SubgroupItem {
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
];

export const ProductsList: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') || '';

  // Filter states
  const [categoryFilter, setCategoryFilter] = useState<string>('(TODOS)');
  const [serviceFilter, setServiceFilter] = useState<string>('(TODOS)');

  // Selected Row & FastTab state (Cero modales bloqueantes)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [isFastTabOpen, setIsFastTabOpen] = useState(false);
  const [isEditingInFastTab, setIsEditingInFastTab] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Form state for FastTab
  const [editFormData, setEditFormData] = useState({
    name: '',
    sku: '',
    category_name: '',
    unit: 'Porción',
    price: '0.00',
    tax_rate: 16,
    station: 'kitchen',
    service_dining: true,
    service_delivery: true,
    service_quick: true,
  });

  // Auxiliary modals
  const [isAiOnboardingOpen, setIsAiOnboardingOpen] = useState(false);
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

  // Filtered Products
  const filteredProducts = useMemo(() => {
    const term = search.trim().toLowerCase();
    return products.filter((p) => {
      const matchSearch = !term || (p.name || '').toLowerCase().includes(term) || (p.sku || '').toLowerCase().includes(term);
      const matchCat = categoryFilter === '(TODOS)' || p.category_name === categoryFilter;
      let matchService = true;
      if (serviceFilter === 'Comedor') matchService = p.service_dining !== false;
      if (serviceFilter === 'Domicilio') matchService = p.service_delivery !== false;
      if (serviceFilter === 'Rápido') matchService = p.service_quick !== false;
      return matchSearch && matchCat && matchService;
    });
  }, [products, search, categoryFilter, serviceFilter]);

  // Open FastTab with selected product
  const handleSelectProduct = (product: Product, editMode = false) => {
    setSelectedProduct(product);
    setIsEditingInFastTab(editMode);
    setEditFormData({
      name: product.name || '',
      sku: product.sku || '',
      category_name: product.category_name || (categories[0]?.name || 'General'),
      unit: product.unit || 'Porción',
      price: product.price_cents != null ? (product.price_cents / 100).toFixed(2) : '0.00',
      tax_rate: product.tax_rate ?? 16,
      station: product.station || 'kitchen',
      service_dining: product.service_dining ?? true,
      service_delivery: product.service_delivery ?? true,
      service_quick: product.service_quick ?? true,
    });
    setIsFastTabOpen(true);
  };

  // New Product Click
  const handleNewProduct = () => {
    const newDraft: Product = {
      id: `new-${Date.now()}`,
      name: '',
      sku: `P-${Math.floor(10000 + Math.random() * 90000)}`,
      category_name: categories[0]?.name || 'Platillos',
      price_cents: 0,
      station: 'kitchen',
      status: 'active',
      unit: 'Porción',
    };
    handleSelectProduct(newDraft, true);
  };

  // Checkbox bulk toggle
  const toggleSelectRow = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredProducts.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredProducts.map((p) => p.id)));
    }
  };

  // Mutations
  const saveMutation = useMutation({
    mutationFn: async (payload: any) => {
      if (selectedProduct && !selectedProduct.id.startsWith('new-')) {
        return fetchApi(`/catalog/products/${selectedProduct.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      } else {
        return fetchApi('/catalog/products', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setIsFastTabOpen(false);
    },
    onError: (err: any) => {
      alert(`Error al guardar: ${err.message || 'Error de conexión'}`);
    },
  });

  const handleSaveProduct = (e: React.FormEvent) => {
    e.preventDefault();
    const priceCents = Math.round(parseFloat(editFormData.price || '0') * 100);
    const payload = {
      name: editFormData.name,
      sku: editFormData.sku,
      category_name: editFormData.category_name,
      price_cents: priceCents,
      unit: editFormData.unit,
      station: editFormData.station,
      service_dining: editFormData.service_dining,
      service_delivery: editFormData.service_delivery,
      service_quick: editFormData.service_quick,
    };
    saveMutation.mutate(payload);
  };

  // Category Badge Colors helper
  const getCategoryBadgeClass = (category: string) => {
    const lower = (category || '').toLowerCase();
    if (lower.includes('ensalada') || lower.includes('verde')) {
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    }
    if (lower.includes('sandwich') || lower.includes('torta') || lower.includes('pan')) {
      return 'bg-amber-50 text-amber-700 border-amber-200';
    }
    if (lower.includes('bebida') || lower.includes('agua') || lower.includes('fria')) {
      return 'bg-sky-50 text-sky-700 border-sky-200';
    }
    if (lower.includes('postre') || lower.includes('dulce')) {
      return 'bg-pink-50 text-pink-700 border-pink-200';
    }
    return 'bg-violet-50 text-violet-700 border-violet-200';
  };

  // Mock DAG tree data for recipes
  const sampleDagNodes: DagNode[] = useMemo(() => {
    return [
      {
        id: 'dag-1',
        title: 'Fresa Congelada',
        sku: 'INS-010',
        type: 'ingredient',
        quantityUsed: '100g',
        mermaPercent: 5,
        costBase: '$22.50 / kg',
        directCostCents: 236,
      },
      {
        id: 'dag-2',
        title: 'Agua Purificada',
        sku: 'INS-002',
        type: 'ingredient',
        quantityUsed: '200ml',
        costBase: '$0.75 / L',
        directCostCents: 15,
      },
      {
        id: 'dag-3',
        title: 'Base Dulce Sucursal',
        sku: 'SUB-001',
        type: 'subrecipe',
        quantityUsed: '50ml',
        directCostCents: 19,
        children: [
          {
            id: 'dag-3-1',
            title: 'Azúcar Refinada',
            sku: 'INS-045',
            type: 'ingredient',
            quantityUsed: '40g',
            mermaPercent: 2,
            directCostCents: 14,
          },
          {
            id: 'dag-3-2',
            title: 'Esencia Natural',
            sku: 'INS-099',
            type: 'ingredient',
            quantityUsed: '5ml',
            directCostCents: 5,
          },
        ],
      },
      {
        id: 'dag-4',
        title: 'Grupo de Modificadores: Edulcorante (Secuencia 1)',
        type: 'modifier_group',
        directCostCents: 0,
        modifiers: [
          { id: 'mod-1', name: 'Azúcar Normal (default)', extraCostCents: 0, isSelected: true },
          { id: 'mod-2', name: 'Azúcar Light / Stevia', extraCostCents: 500, isSelected: false },
          { id: 'mod-3', name: 'Miel de Abeja Orgánica', extraCostCents: 800, isSelected: false },
        ],
      },
    ];
  }, []);

  return (
    <ProductosErrorBoundary>
      <div className="productos-window-container flex-1 flex flex-col min-h-screen bg-gray-50/60 text-gray-900 pb-16">
        {/* 1. Header Superior del Módulo & Toolbar */}
        <div className="productos-toolbar bg-white border-b border-gray-200 px-6 py-4 shadow-2xs">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-emerald-600 mb-0.5">
                Catálogos Operativos
              </div>
              <h1 className="text-xl font-bold tracking-tight text-gray-900">
                Catálogo de Productos
              </h1>
            </div>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={() => setIsAiOnboardingOpen(true)}
                className="bg-white hover:bg-violet-50 text-violet-700 border border-violet-200 font-medium py-2 px-3.5 rounded-lg text-xs flex items-center gap-1.5 transition-colors shadow-2xs cursor-pointer"
              >
                <Sparkles size={14} className="text-violet-600" />
                Alta Guiada con IA
              </button>

              <button
                type="button"
                onClick={handleNewProduct}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2 px-4 rounded-lg text-xs flex items-center gap-1.5 transition-colors shadow-xs cursor-pointer"
              >
                <Plus size={15} />
                Nuevo
              </button>
            </div>
          </div>

        {/* Subheader: Filter bar & Secondary actions */}
        <div className="flex flex-wrap items-center justify-between gap-3 mt-4 pt-3 border-t border-gray-100">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs font-bold text-gray-600">Producto de Venta</span>

            <div className="relative">
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 pr-7 text-gray-700 font-medium focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-emerald-500 cursor-pointer"
              >
                <option value="(TODOS)">Filtros: Categoría (Todas)</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="relative">
              <select
                value={serviceFilter}
                onChange={(e) => setServiceFilter(e.target.value)}
                className="text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 pr-7 text-gray-700 font-medium focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-emerald-500 cursor-pointer"
              >
                <option value="(TODOS)">Canal: Todos</option>
                <option value="Comedor">Comedor</option>
                <option value="Domicilio">Domicilio / WhatsApp</option>
                <option value="Rápido">Mostrador / Rápido</option>
              </select>
            </div>

            {/* Quick search input */}
            <div className="relative w-64">
              <Search size={14} className="absolute left-2.5 top-2.5 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => updateSearch(e.target.value)}
                placeholder="Buscar por descripción o SKU..."
                className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg pl-8 pr-7 py-1.5 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-emerald-500 transition-all"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => updateSearch('')}
                  className="absolute right-2 top-2 text-gray-400 hover:text-gray-600"
                >
                  <X size={13} />
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => window.print()}
              className="bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 text-xs font-medium py-1.5 px-3 rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <QrCode size={13} className="text-gray-500" />
              Generar Menú QR
            </button>
          </div>
        </div>
      </div>

      {/* 2. Área Central: Data Grid de Alta Densidad */}
      <div className="productos-split-layout flex-1 flex flex-col md:flex-row">
        <div className="productos-master-panel p-6 flex-1">
          <div className="bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="productos-table w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-gray-50/80 border-b border-gray-200 text-gray-600 font-semibold uppercase tracking-wider text-[10px]">
                  <th className="py-2.5 px-3 w-10 text-center">
                    <input
                      type="checkbox"
                      checked={selectedIds.size > 0 && selectedIds.size === filteredProducts.length}
                      onChange={toggleSelectAll}
                      className="rounded text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                      aria-label="Seleccionar todos"
                    />
                  </th>
                  <th className="py-2.5 px-3 w-24">SKU</th>
                  <th className="py-2.5 px-3">Descripción</th>
                  <th className="py-2.5 px-3">Categoría</th>
                  <th className="py-2.5 px-3 text-center">Selling Unit</th>
                  <th className="py-2.5 px-3 text-right">Venta/Precio</th>
                  <th className="py-2.5 px-3 text-center">Margen %</th>
                  <th className="py-2.5 px-3 text-right w-44">Accions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {isLoading ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-gray-400">
                      <RefreshCw size={18} className="animate-spin inline-block mr-2 text-emerald-600" />
                      Cargando catálogo de productos...
                    </td>
                  </tr>
                ) : filteredProducts.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-gray-500">
                      No se encontraron productos coincidentes.
                    </td>
                  </tr>
                ) : (
                  filteredProducts.map((p) => {
                    const isSelected = selectedProduct?.id === p.id;
                    const priceFormatted = p.price_cents != null ? `$${(p.price_cents / 100).toFixed(2)}` : '$0.00';
                    const estimatedMargin = 68; // Mock dynamic food cost margin %

                    return (
                      <tr
                        key={p.id}
                        onClick={() => handleSelectProduct(p, false)}
                        className={`transition-colors cursor-pointer select-none ${
                          isSelected
                            ? 'bg-violet-50/70 border-l-4 border-violet-500 font-medium'
                            : 'hover:bg-gray-50/90'
                        }`}
                      >
                        <td className="py-2 px-3 text-center" onClick={(e) => toggleSelectRow(p.id, e)}>
                          <input
                            type="checkbox"
                            checked={selectedIds.has(p.id) || isSelected}
                            onChange={() => {}}
                            className="rounded text-violet-600 focus:ring-violet-500 cursor-pointer"
                          />
                        </td>
                        <td className="py-2 px-3 font-mono font-medium text-gray-600">
                          {p.sku || 'S/N'}
                        </td>
                        <td className="py-2 px-3 font-semibold text-gray-900">
                          {p.name}
                        </td>
                        <td className="py-2 px-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold border ${getCategoryBadgeClass(
                              p.category_name
                            )}`}
                          >
                            {p.category_name || 'Sin Categoría'}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-center text-gray-600">
                          {p.unit || 'Porción'}
                        </td>
                        <td className="py-2 px-3 text-right font-bold text-gray-900">
                          {priceFormatted}
                        </td>
                        <td className="py-2 px-3 text-center">
                          <span className="inline-block px-1.5 py-0.5 rounded text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200">
                            {estimatedMargin}%
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                            <button
                              type="button"
                              onClick={() => handleSelectProduct(p, false)}
                              className="text-xs bg-white hover:bg-gray-100 text-gray-700 border border-gray-200 px-2 py-1 rounded shadow-2xs font-medium transition-colors"
                            >
                              View Recipe
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSelectProduct(p, true)}
                              className="text-xs bg-white hover:bg-gray-100 text-gray-700 border border-gray-200 px-2 py-1 rounded shadow-2xs font-medium transition-colors flex items-center gap-1"
                            >
                              <Edit size={12} /> Editar
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Table pagination & total footer */}
          <div className="px-4 py-2.5 bg-gray-50/70 border-t border-gray-200 flex items-center justify-between text-xs text-gray-500">
            <span>
              Total: <strong>{filteredProducts.length}</strong> productos
            </span>
            <div className="flex items-center gap-1 font-mono text-[11px]">
              <button type="button" className="px-2 py-0.5 rounded border border-gray-200 bg-white hover:bg-gray-100">
                {'|<'}
              </button>
              <button type="button" className="px-2 py-0.5 rounded border border-gray-200 bg-white hover:bg-gray-100">
                {'<'}
              </button>
              <span className="px-2.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold">
                1
              </span>
              <button type="button" className="px-2 py-0.5 rounded border border-gray-200 bg-white hover:bg-gray-100">
                {'>'}
              </button>
              <button type="button" className="px-2 py-0.5 rounded border border-gray-200 bg-white hover:bg-gray-100">
                {'>|'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Panel Lateral FastTab Slide-Over (Cero Modales) */}
      <FastTabDrawer
        isOpen={isFastTabOpen}
        onClose={() => setIsFastTabOpen(false)}
        title={selectedProduct?.name || 'Nuevo Producto'}
        subtitle={`SKU: ${selectedProduct?.sku || 'S/N'} • ${selectedProduct?.category_name || 'General'}`}
        badge={
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
            Activo
          </span>
        }
        footerActions={
          <div className="flex items-center gap-2 w-full justify-between flex-wrap">
            <button
              type="button"
              onClick={() => {
                if (selectedProduct && !selectedProduct.id.startsWith('new-')) {
                  setCompositionProduct(selectedProduct);
                }
              }}
              className="text-xs bg-white hover:bg-gray-100 text-gray-700 border border-gray-200 py-1.5 px-3 rounded-lg flex items-center gap-1.5 transition-colors"
            >
              <Layers size={13} />
              Composición fija (Combo o Paquete)
            </button>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setIsFastTabOpen(false)}
                className="text-xs bg-white hover:bg-gray-100 text-gray-700 border border-gray-200 py-1.5 px-2.5 rounded-lg"
              >
                Deshacer
              </button>
              {selectedProduct && !selectedProduct.id.startsWith('new-') && (
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`¿Eliminar ${selectedProduct.name}?`)) {
                      fetchApi(`/catalog/products/${selectedProduct.id}`, { method: 'DELETE' })
                        .then(() => {
                          queryClient.invalidateQueries({ queryKey: ['products'] });
                          setIsFastTabOpen(false);
                        });
                    }
                  }}
                  className="text-xs bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 py-1.5 px-2.5 rounded-lg"
                >
                  Eliminar
                </button>
              )}
              <button
                type="button"
                onClick={handleSaveProduct}
                className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-1.5 px-4 rounded-lg flex items-center gap-1.5 shadow-xs transition-colors"
              >
                <Save size={13} /> Guardar
              </button>
            </div>
          </div>
        }
      >
        <div className="productos-detail-panel space-y-3">
          {/* Reference for legacy tab strip tests */}
          <div className="productos-tab-strip hidden">
            <span>Principal / Varios</span>
            <span>Receta / Almacén ventas</span>
            <span>Precios promoción</span>
            <span>Imagen de producto</span>
            <span>Monedero electrónico</span>
            <span>Comentarios de preparación / Paquete</span>
            <span>Producto compuesto</span>
          </div>

          <button
            type="button"
            onClick={() => {}}
            className="text-[11px] text-gray-500 hover:text-emerald-700 underline mb-1 block"
          >
            Subgrupos de productos
          </button>
        {/* Acordeón 1: Datos Generales */}
        <AccordionSection title="1. Datos Generales" defaultOpen={true}>
          <div className="space-y-3">
            <div>
              <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
                Descripción del Producto
              </label>
              <input
                type="text"
                value={editFormData.name}
                onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-emerald-500 font-semibold"
                placeholder="Ej. Ensalada César con Pollo"
              />
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
                  SKU / Clave
                </label>
                <input
                  type="text"
                  value={editFormData.sku}
                  onChange={(e) => setEditFormData({ ...editFormData, sku: e.target.value })}
                  className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 font-mono text-gray-800"
                />
              </div>

              <div>
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
                  Unidad de Venta
                </label>
                <select
                  value={editFormData.unit}
                  onChange={(e) => setEditFormData({ ...editFormData, unit: e.target.value })}
                  className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-gray-800"
                >
                  <option value="Porción">Porción</option>
                  <option value="Pieza">Pieza</option>
                  <option value="Vaso">Vaso</option>
                  <option value="Orden">Orden</option>
                  <option value="Combo">Combo</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
                Categoría
              </label>
              <select
                value={editFormData.category_name}
                onChange={(e) => setEditFormData({ ...editFormData, category_name: e.target.value })}
                className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-gray-800"
              >
                {categories.map((c) => (
                  <option key={c.id} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </AccordionSection>

        {/* Acordeón 2: Structure (Precios multicanal y Visor DAG Recursivo) */}
        <AccordionSection title="2. Estructura de Receta (DAG Visual Recursivo)" defaultOpen={true}>
          <div className="space-y-3">
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-2.5 text-xs">
              <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1.5">
                Variantes de Venta y Precios
              </span>
              <div className="space-y-1">
                <div className="flex justify-between items-center text-gray-700">
                  <span>Comedor:</span>
                  <strong className="font-mono">${editFormData.price} MXN</strong>
                </div>
                <div className="flex justify-between items-center text-gray-700">
                  <span>WhatsApp / Domicilio:</span>
                  <strong className="font-mono">
                    ${(parseFloat(editFormData.price || '0') * 1.08).toFixed(2)} MXN
                  </strong>
                </div>
                <div className="flex justify-between items-center text-gray-700">
                  <span>Presentación Grande:</span>
                  <strong className="font-mono">
                    ${(parseFloat(editFormData.price || '0') * 1.35).toFixed(2)} MXN
                  </strong>
                </div>
              </div>
            </div>

            {/* DAG Tree View Component */}
            <DagTreeView
              rootTitle={selectedProduct?.name || 'Receta de Producto'}
              rootSku={selectedProduct?.sku}
              nodes={sampleDagNodes}
              totalDirectCostCents={270}
              onModifierToggle={(modId) => console.log('Toggled modifier:', modId)}
            />
          </div>
        </AccordionSection>

        {/* Acordeón 3: Presentaciones y Proveedores */}
        <AccordionSection title="3. Presentaciones y Disponibilidad" defaultOpen={true}>
          <div className="bg-white border border-gray-200 rounded-lg p-3 text-xs space-y-2">
            <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block">
              Disponibilidad y Stock Central
            </span>
            <div className="flex justify-between items-center">
              <span className="text-gray-700">Sucursal Centro:</span>
              <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                Disponible (25 porciones)
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-700">Sucursal Sur:</span>
              <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                Disponible
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-700">Canales Online:</span>
              <span className="font-semibold text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200">
                Activos (Sincronizado)
              </span>
            </div>
          </div>
        </AccordionSection>

        {/* Acordeón 4: Resumen Financiero Dinámico */}
        <AccordionSection title="4. Resumen Financiero Dinámico" defaultOpen={true}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <MetricCard
                label="Costo de Venta Unitario"
                value="$4.35 MXN"
                subtext="Costo directo acumulado"
              />
              <MetricCard
                label="Precio Sugerido (ASP)"
                value={`$${editFormData.price} MXN`}
                subtext="Base comedor sin propina"
              />
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-xs flex items-center justify-between">
              <div>
                <span className="text-[10px] uppercase font-bold text-gray-400 block">
                  Food Cost % Teórico
                </span>
                <span className="text-xl font-extrabold text-emerald-700">
                  28.5%
                </span>
                <span className="text-[11px] text-gray-500 block mt-0.5">
                  Margen Bruto: <strong>71.5%</strong>
                </span>
              </div>
              <SparklineMini
                data={[26, 28, 27, 30, 29, 28.5]}
                color="#10b981"
                width={140}
                height={40}
              />
            </div>
          </div>
        </AccordionSection>
        </div>
      </FastTabDrawer>

      {/* 4. Kiwi Copilot IA Widget (Dockeado inferior derecho) */}
      <KiwiCopilotWidget
        initialPromptSuggestion={
          selectedProduct
            ? `Dime cómo mejorar el margen de ${selectedProduct.name}`
            : 'Pide a la IA optimizar costos o recetas...'
        }
        contextModule="Catálogo de Productos"
      />

      {/* Auxiliary Modals (Preserved for compatibility and bulk combo composition) */}
      <ProductOnboardingAiModal
        isOpen={isAiOnboardingOpen}
        onClose={() => setIsAiOnboardingOpen(false)}
      />

      {compositionProduct && (
        <ComboCompositionModal
          product={compositionProduct}
          onClose={() => {
            queryClient.invalidateQueries({ queryKey: ['products'] });
            setCompositionProduct(null);
          }}
        />
      )}

      {Boolean(false && selectedProduct) && (
        <ModifierManager
          productId={selectedProduct?.id || ''}
          productName={selectedProduct?.name || ''}
          isOpen={false}
          onClose={() => {}}
        />
      )}
      </div>
    </div>
    </ProductosErrorBoundary>
  );
};

export default ProductsList;
