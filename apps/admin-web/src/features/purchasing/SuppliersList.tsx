import React, { useState, useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';
import {
  Plus,
  Truck,
  Edit,
  Phone,
  Mail,
  Building2,
  Trash2,
  Search,
  Sparkles,
  FileText,
  DollarSign,
  Calendar,
  AlertTriangle,
  CheckCircle,
  Clock,
  Save,
  X,
  CreditCard,
  Layers,
  ArrowUpRight
} from 'lucide-react';
import { FastTabDrawer, AccordionSection } from '../../components/FastTabDrawer';
import { MetricCard, SparklineMini } from '../../components/MetricDataViz';
import { KiwiCopilotWidget } from '../../components/KiwiCopilotWidget';
import { DagTreeView, DagNode } from '../../components/DagTreeView';

export interface Supplier {
  id: string;
  code: string;
  commercial_name: string;
  legal_name?: string;
  tax_id?: string;
  phone?: string;
  billing_email?: string;
  supplier_type?: string;
  fiscal_address?: string;
  fiscal_postal_code?: string;
  municipality?: string;
  state?: string;
  accounting_reference?: string;
  status: string;
  credit_days: number;
  credit_limit?: number;
  notes?: string;
  pending_balance_cents?: number;
  due_status?: 'ok' | 'due_soon' | 'overdue';
}

interface Item {
  id: string;
  name: string;
  sku: string;
  base_unit_id: string;
  unit_code: string;
}

interface Presentation {
  id: string;
  code: string;
  name: string;
  supplier_name: string;
  item_name: string;
  last_net_price: number;
  cost_per_base_unit: number;
  base_unit_code: string;
}

const SUPPLIER_TYPES = [
  { value: 'insumos', label: 'Insumos y Alimentos' },
  { value: 'empaque', label: 'Empaque y Desechables' },
  { value: 'servicios', label: 'Servicios' },
  { value: 'mantenimiento', label: 'Mantenimiento y Equipo' },
  { value: 'general', label: 'General / Otros' },
];

export const SuppliersList: React.FC = () => {
  const queryClient = useQueryClient();

  // Search and filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('(TODOS)');

  // Selected row & FastTab state
  const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null);
  const [isFastTabOpen, setIsFastTabOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [activeViewTab, setActiveViewTab] = useState<'suppliers' | 'presentations'>('suppliers');

  // Supplier Form Data
  const [formData, setFormData] = useState({
    code: '',
    commercial_name: '',
    legal_name: '',
    tax_id: '',
    phone: '',
    email: '',
    supplier_type: 'insumos',
    address: '',
    postal_code: '',
    municipality: 'Culiacán',
    state: 'Sinaloa',
    accounting_reference: '',
    status: 'active',
    credit_days: '15',
    credit_limit: '',
    notes: '',
  });

  // Queries
  const { data: rawSuppliers = [], isLoading: loadingSuppliers } = useQuery<Supplier[]>({
    queryKey: ['suppliers'],
    queryFn: () => fetchApi<Supplier[]>('/suppliers').catch(() => [] as Supplier[]),
  });

  const { data: rawPresentations = [], isLoading: loadingPresentations } = useQuery<Presentation[]>({
    queryKey: ['purchase-presentations'],
    queryFn: () => fetchApi<Presentation[]>('/purchase-presentations').catch(() => [] as Presentation[]),
  });

  // Simulated enrichment with balances and due dates
  const suppliers: Supplier[] = useMemo(() => {
    return (Array.isArray(rawSuppliers) ? rawSuppliers : []).map((s, idx) => ({
      ...s,
      pending_balance_cents: s.pending_balance_cents ?? (idx % 3 === 0 ? 2450000 : idx % 2 === 0 ? 1230000 : 0),
      due_status: idx % 3 === 0 ? 'overdue' : idx % 2 === 0 ? 'due_soon' : 'ok',
    }));
  }, [rawSuppliers]);

  const presentations = useMemo(
    () => (Array.isArray(rawPresentations) ? rawPresentations : []),
    [rawPresentations]
  );

  // Filtered Suppliers
  const filteredSuppliers = useMemo(() => {
    const term = search.trim().toLowerCase();
    return suppliers.filter((s) => {
      const matchSearch =
        !term ||
        s.commercial_name.toLowerCase().includes(term) ||
        (s.tax_id || '').toLowerCase().includes(term) ||
        s.code.toLowerCase().includes(term);
      const matchStatus = statusFilter === '(TODOS)' || s.status === statusFilter;
      return matchSearch && matchStatus;
    });
  }, [suppliers, search, statusFilter]);

  // Open FastTab for supplier
  const handleSelectSupplier = (s: Supplier, editMode = false) => {
    setSelectedSupplier(s);
    setIsEditing(editMode);
    setFormData({
      code: s.code || '',
      commercial_name: s.commercial_name || '',
      legal_name: s.legal_name || '',
      tax_id: s.tax_id || '',
      phone: s.phone || '',
      email: s.billing_email || '',
      supplier_type: s.supplier_type || 'insumos',
      address: s.fiscal_address || '',
      postal_code: s.fiscal_postal_code || '',
      municipality: s.municipality || 'Culiacán',
      state: s.state || 'Sinaloa',
      accounting_reference: s.accounting_reference || '',
      status: s.status || 'active',
      credit_days: String(s.credit_days || 15),
      credit_limit: s.credit_limit ? String(s.credit_limit) : '',
      notes: s.notes || '',
    });
    setIsFastTabOpen(true);
  };

  const handleNewSupplier = () => {
    const newDraft: Supplier = {
      id: `new-${Date.now()}`,
      code: `PROV-${Math.floor(100 + Math.random() * 900)}`,
      commercial_name: '',
      status: 'active',
      credit_days: 15,
      pending_balance_cents: 0,
      due_status: 'ok',
    };
    handleSelectSupplier(newDraft, true);
  };

  // Mutations
  const supplierMutation = useMutation({
    mutationFn: (body: any) => {
      if (selectedSupplier && !selectedSupplier.id.startsWith('new-')) {
        return fetchApi(`/suppliers/${selectedSupplier.id}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
      }
      return fetchApi('/suppliers', {
        method: 'POST',
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      setIsFastTabOpen(false);
    },
    onError: (err: any) => {
      alert(`Error al guardar proveedor: ${err.message || 'Error de red'}`);
    },
  });

  const handleSaveSupplier = (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      code: formData.code,
      commercial_name: formData.commercial_name,
      legal_name: formData.legal_name,
      tax_id: formData.tax_id,
      phone: formData.phone,
      billing_email: formData.email,
      supplier_type: formData.supplier_type,
      fiscal_address: formData.address,
      fiscal_postal_code: formData.postal_code,
      municipality: formData.municipality,
      state: formData.state,
      accounting_reference: formData.accounting_reference,
      status: formData.status,
      credit_days: parseInt(formData.credit_days || '0', 10),
      credit_limit: formData.credit_limit ? parseFloat(formData.credit_limit) : null,
      notes: formData.notes,
      payment_methods: [],
    };
    supplierMutation.mutate(payload);
  };

  // DAG hierarchical nodes for supplier traceability
  const supplierDagNodes: DagNode[] = useMemo(() => {
    return [
      {
        id: 'cxp-fac-1',
        title: 'Factura CFDI A-9842 (Vencimiento: 3 días)',
        sku: 'UUID-9842',
        type: 'subrecipe',
        directCostCents: 1450000,
        children: [
          {
            id: 'cxp-rem-1',
            title: 'Entrada Almacén Centro #402',
            type: 'ingredient',
            quantityUsed: '150 kg',
            costBase: '$85.00 / kg',
            directCostCents: 1275000,
            mermaPercent: 0,
          },
          {
            id: 'cxp-rem-2',
            title: 'Flete Refrigerado Directo',
            type: 'ingredient',
            directCostCents: 175000,
          },
        ],
      },
    ];
  }, []);

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-gray-50/60 text-gray-900 pb-16">
      {/* 1. Header Superior */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 shadow-2xs">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-emerald-600 mb-0.5">
              Compras y Proveedores
            </div>
            <h1 className="text-xl font-bold tracking-tight text-gray-900">
              Proveedores y Cuentas por Pagar (CXP)
            </h1>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              className="bg-white hover:bg-violet-50 text-violet-700 border border-violet-200 font-medium py-2 px-3.5 rounded-lg text-xs flex items-center gap-1.5 transition-colors shadow-2xs cursor-pointer"
            >
              <Sparkles size={14} className="text-violet-600" />
              Conciliación Inteligente SAT
            </button>

            <button
              type="button"
              onClick={handleNewSupplier}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2 px-4 rounded-lg text-xs flex items-center gap-1.5 transition-colors shadow-xs cursor-pointer"
            >
              <Plus size={15} />
              + Nuevo Proveedor
            </button>
          </div>
        </div>

        {/* Subheader & View toggles */}
        <div className="flex flex-wrap items-center justify-between gap-3 mt-4 pt-3 border-t border-gray-100">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveViewTab('suppliers')}
              className={`text-xs px-3 py-1.5 rounded-lg font-bold transition-colors cursor-pointer ${
                activeViewTab === 'suppliers'
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              Cartera de Proveedores ({suppliers.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveViewTab('presentations')}
              className={`text-xs px-3 py-1.5 rounded-lg font-bold transition-colors cursor-pointer ${
                activeViewTab === 'presentations'
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              Presentaciones de Compra ({presentations.length})
            </button>
          </div>

          {/* Quick Filter & Search */}
          <div className="flex items-center gap-3">
            <div className="relative w-64">
              <Search size={14} className="absolute left-2.5 top-2.5 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar por razón social, RFC o clave..."
                className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg pl-8 pr-7 py-1.5 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-emerald-500"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch('')}
                  className="absolute right-2 top-2 text-gray-400 hover:text-gray-600"
                >
                  <X size={13} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Área Central: Data Grid de Alta Densidad */}
      <div className="p-6 flex-1">
        {activeViewTab === 'suppliers' ? (
          <div className="bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-gray-50/80 border-b border-gray-200 text-gray-600 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="py-2.5 px-3 w-16">Código</th>
                    <th className="py-2.5 px-3">Proveedor / Razón Social</th>
                    <th className="py-2.5 px-3 w-28">RFC</th>
                    <th className="py-2.5 px-3 text-center">Plazo Crédito</th>
                    <th className="py-2.5 px-3 text-right">Saldo Pendiente</th>
                    <th className="py-2.5 px-3 text-center">Semáforo Vencimiento</th>
                    <th className="py-2.5 px-3 text-center">Estatus</th>
                    <th className="py-2.5 px-3 text-right w-36">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {loadingSuppliers ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-gray-400">
                        Cargando cartera de proveedores...
                      </td>
                    </tr>
                  ) : filteredSuppliers.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-gray-500">
                        No hay proveedores registrados coincidentes.
                      </td>
                    </tr>
                  ) : (
                    filteredSuppliers.map((s) => {
                      const isSelected = selectedSupplier?.id === s.id;
                      const balanceFormatted = `$${((s.pending_balance_cents || 0) / 100).toLocaleString('es-MX', {
                        minimumFractionDigits: 2,
                      })} MXN`;

                      const dueBadge =
                        s.due_status === 'overdue' ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
                            <AlertTriangle size={11} /> Vencido
                          </span>
                        ) : s.due_status === 'due_soon' ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                            <Clock size={11} /> Por Vencer
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle size={11} /> Al Día
                          </span>
                        );

                      return (
                        <tr
                          key={s.id}
                          onClick={() => handleSelectSupplier(s, false)}
                          className={`transition-colors cursor-pointer select-none ${
                            isSelected
                              ? 'bg-violet-50/70 border-l-4 border-violet-500 font-medium'
                              : 'hover:bg-gray-50/90'
                          }`}
                        >
                          <td className="py-2.5 px-3 font-mono font-medium text-gray-600">
                            {s.code}
                          </td>
                          <td className="py-2.5 px-3 font-semibold text-gray-900">
                            {s.commercial_name}
                            {s.legal_name && s.legal_name !== s.commercial_name && (
                              <span className="block text-[11px] font-normal text-gray-400">
                                {s.legal_name}
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-gray-700">
                            {s.tax_id || 'SIN RFC'}
                          </td>
                          <td className="py-2.5 px-3 text-center text-gray-700">
                            <span className="font-semibold">{s.credit_days}</span> días
                          </td>
                          <td className="py-2.5 px-3 text-right font-bold text-gray-900">
                            {balanceFormatted}
                          </td>
                          <td className="py-2.5 px-3 text-center">{dueBadge}</td>
                          <td className="py-2.5 px-3 text-center">
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                              {s.status === 'active' ? 'Activo' : 'Inactivo'}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                              <button
                                type="button"
                                onClick={() => handleSelectSupplier(s, false)}
                                className="text-xs bg-white hover:bg-gray-100 text-gray-700 border border-gray-200 px-2 py-1 rounded shadow-2xs font-medium transition-colors"
                              >
                                Ver Estado
                              </button>
                              <button
                                type="button"
                                onClick={() => handleSelectSupplier(s, true)}
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
          </div>
        ) : (
          /* Presentations Tab */
          <div className="bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600 mb-3">
              Catálogo de Presentaciones de Compra
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold uppercase text-[10px]">
                    <th className="py-2 px-3">Código</th>
                    <th className="py-2 px-3">Presentación</th>
                    <th className="py-2 px-3">Proveedor</th>
                    <th className="py-2 px-3">Insumo Base</th>
                    <th className="py-2 px-3 text-right">Último Costo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {presentations.map((p) => (
                    <tr key={p.id} className="hover:bg-gray-50">
                      <td className="py-2 px-3 font-mono text-gray-600">{p.code}</td>
                      <td className="py-2 px-3 font-medium text-gray-900">{p.name}</td>
                      <td className="py-2 px-3 text-gray-600">{p.supplier_name}</td>
                      <td className="py-2 px-3 text-gray-600">{p.item_name}</td>
                      <td className="py-2 px-3 text-right font-bold text-gray-900">
                        ${p.last_net_price.toFixed(2)} MXN
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* 3. Panel Lateral FastTab Slide-Over (Cero Modales) */}
      <FastTabDrawer
        isOpen={isFastTabOpen}
        onClose={() => setIsFastTabOpen(false)}
        title={selectedSupplier?.commercial_name || 'Nuevo Proveedor'}
        subtitle={`RFC: ${selectedSupplier?.tax_id || 'SIN RFC'} • Plazo: ${selectedSupplier?.credit_days || 0} días`}
        badge={
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
            {selectedSupplier?.status === 'active' ? 'Proveedor Vigente' : 'Suspendido'}
          </span>
        }
        footerActions={
          <div className="flex items-center gap-2 w-full justify-end">
            <button
              type="button"
              onClick={() => setIsFastTabOpen(false)}
              className="text-xs bg-white hover:bg-gray-100 text-gray-700 border border-gray-200 py-1.5 px-3 rounded-lg transition-colors cursor-pointer"
            >
              Cerrar
            </button>
            <button
              type="button"
              onClick={handleSaveSupplier}
              className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-1.5 px-4 rounded-lg flex items-center gap-1.5 shadow-xs transition-colors cursor-pointer"
            >
              <Save size={13} /> Guardar Proveedor
            </button>
          </div>
        }
      >
        {/* FastTab 1: Datos Fiscales y Comerciales */}
        <AccordionSection title="1. Datos Fiscales y Comerciales" defaultOpen={true}>
          <div className="space-y-3">
            <div>
              <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
                Nombre Comercial / Razón Social
              </label>
              <input
                type="text"
                value={formData.commercial_name}
                onChange={(e) => setFormData({ ...formData, commercial_name: e.target.value })}
                className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 focus:bg-white focus:ring-1 focus:ring-emerald-500 font-semibold"
                placeholder="Ej. La Huerta Fresca S.A."
              />
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
                  RFC
                </label>
                <input
                  type="text"
                  value={formData.tax_id}
                  onChange={(e) => setFormData({ ...formData, tax_id: e.target.value })}
                  className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 font-mono text-gray-800"
                />
              </div>

              <div>
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
                  Días de Crédito
                </label>
                <input
                  type="number"
                  value={formData.credit_days}
                  onChange={(e) => setFormData({ ...formData, credit_days: e.target.value })}
                  className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-gray-800"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
                  Teléfono
                </label>
                <input
                  type="text"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-gray-800"
                />
              </div>
              <div>
                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
                  Email Facturación
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full text-xs bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-gray-800"
                />
              </div>
            </div>
          </div>
        </AccordionSection>

        {/* FastTab 2: Cartera de Facturas y Vencimientos */}
        <AccordionSection title="2. Cartera de Facturas y Vencimientos" defaultOpen={true}>
          <div className="space-y-2 text-xs">
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-2.5">
              <div className="flex justify-between items-center mb-1">
                <span className="font-bold text-gray-900">Factura #F-9081 (Vencida)</span>
                <span className="text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded font-bold text-[10px]">
                  +8 días mora
                </span>
              </div>
              <div className="flex justify-between text-gray-600 text-[11px]">
                <span>Saldo por pagar:</span>
                <strong className="font-mono text-gray-900">$14,500.00 MXN</strong>
              </div>
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded-lg p-2.5">
              <div className="flex justify-between items-center mb-1">
                <span className="font-bold text-gray-900">Factura #F-9204 (Al día)</span>
                <span className="text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-bold text-[10px]">
                  Vence en 6 días
                </span>
              </div>
              <div className="flex justify-between text-gray-600 text-[11px]">
                <span>Saldo por pagar:</span>
                <strong className="font-mono text-gray-900">$10,000.00 MXN</strong>
              </div>
            </div>
          </div>
        </AccordionSection>

        {/* FastTab 3: Trazabilidad Jerárquica DAG */}
        <AccordionSection title="3. Árbol de Trazabilidad (Factura -> Entrada -> Insumos)" defaultOpen={true}>
          <DagTreeView
            rootTitle="Cadena de Suministro y Recepción"
            rootSku={selectedSupplier?.code}
            nodes={supplierDagNodes}
            totalDirectCostCents={1450000}
          />
        </AccordionSection>

        {/* FastTab 4: Resumen Financiero y Liquidez */}
        <AccordionSection title="4. Resumen Financiero y Liquidez Dinámica" defaultOpen={true}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <MetricCard
                label="Pasivo Total Pendiente"
                value={`$${(((selectedSupplier?.pending_balance_cents || 0)) / 100).toLocaleString('es-MX', {
                  minimumFractionDigits: 2,
                })} MXN`}
                badge={{ text: 'CXP', variant: 'warning' }}
              />
              <MetricCard
                label="Días Promedio Pago (DPO)"
                value="22 días"
                subtext="Meta pactada: 15 días"
              />
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-xs flex items-center justify-between">
              <div>
                <span className="text-[10px] uppercase font-bold text-gray-400 block">
                  Proyección de Pagos a 30 Días
                </span>
                <span className="text-sm font-extrabold text-violet-700">
                  Flujo Semanal Compensado
                </span>
              </div>
              <SparklineMini
                data={[10, 15, 25, 18, 24, 20]}
                color="#7c3aed"
                width={130}
                height={38}
              />
            </div>
          </div>
        </AccordionSection>
      </FastTabDrawer>

      {/* 4. Kiwi IA Copilot Widget (Dockeado) */}
      <KiwiCopilotWidget
        initialPromptSuggestion="Sube tu factura XML o di: 'Pagar facturas vencidas de este proveedor'..."
        contextModule="Cuentas por Pagar"
      />
    </div>
  );
};

export default SuppliersList;
