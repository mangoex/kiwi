import { useMemo, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchApi } from '@restaurantos/api-client';
import { Building2, ChevronDown, Edit, FileText, Plus, Search, Save, X } from 'lucide-react';
import { resolveBranchId } from '../../lib/branchContext';
import { useAdminPermission } from '../../lib/adminSession';
import { FastTabDrawer } from '../../components/FastTabDrawer';
import './SuppliersList.css';

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
  credit_limit?: string | number | null;
  notes?: string;
}

interface Presentation {
  id: string;
  code: string;
  name: string;
  supplier_name: string;
  item_name: string;
  last_net_price: number;
}

const supplierForm = (supplier?: Supplier) => ({
  code: supplier?.code ?? '',
  commercial_name: supplier?.commercial_name ?? '',
  legal_name: supplier?.legal_name ?? '',
  tax_id: supplier?.tax_id ?? '',
  phone: supplier?.phone ?? '',
  billing_email: supplier?.billing_email ?? '',
  supplier_type: supplier?.supplier_type ?? 'insumos',
  fiscal_address: supplier?.fiscal_address ?? '',
  fiscal_postal_code: supplier?.fiscal_postal_code ?? '',
  municipality: supplier?.municipality ?? '',
  state: supplier?.state ?? '',
  accounting_reference: supplier?.accounting_reference ?? '',
  status: supplier?.status ?? 'active',
  credit_days: String(supplier?.credit_days ?? 0),
  notes: supplier?.notes ?? '',
});

type SupplierForm = ReturnType<typeof supplierForm>;
const fields: { key: keyof SupplierForm; label: string; type?: string; wide?: boolean }[] = [
  { key: 'commercial_name', label: 'Nombre comercial', wide: true },
  { key: 'legal_name', label: 'Razón social', wide: true },
  { key: 'tax_id', label: 'RFC' },
  { key: 'credit_days', label: 'Días de crédito', type: 'number' },
  { key: 'phone', label: 'Teléfono', type: 'tel' },
  { key: 'billing_email', label: 'Email de facturación', type: 'email' },
];

function QueryMessage({ title, detail, onRetry }: { title: string; detail?: string; onRetry?: () => void }) {
  return <div className="suppliers-message" role={onRetry ? 'alert' : 'status'}>
    <Building2 size={28} aria-hidden="true" />
    <strong>{title}</strong>
    {detail && <p>{detail}</p>}
    {onRetry && <button type="button" className="supplier-button" onClick={onRetry}>Reintentar</button>}
  </div>;
}

export function SuppliersList() {
  const canManageCatalog = useAdminPermission('catalog.manage');
  const queryClient = useQueryClient();
  const branchId = resolveBranchId();
  const query = '?branch_id=' + encodeURIComponent(branchId);
  const [search, setSearch] = useState('');
  const [activeViewTab, setActiveViewTab] = useState<'suppliers' | 'presentations'>('suppliers');
  const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null);
  const [isFastTabOpen, setIsFastTabOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState(supplierForm());

  const suppliersQuery = useQuery({
    queryKey: ['suppliers', branchId],
    queryFn: () => fetchApi<Supplier[]>('/suppliers' + query),
    retry: false,
  });
  const presentationsQuery = useQuery({
    queryKey: ['purchase-presentations', branchId],
    queryFn: () => fetchApi<Presentation[]>('/purchase-presentations' + query),
    retry: false,
  });
  const suppliers = suppliersQuery.data ?? [];
  const presentations = presentationsQuery.data ?? [];
  const term = search.trim().toLocaleLowerCase('es-MX');
  const filteredSuppliers = useMemo(() => suppliers.filter(supplier =>
    [supplier.commercial_name, supplier.legal_name, supplier.tax_id, supplier.code]
      .some(value => value?.toLocaleLowerCase('es-MX').includes(term))), [suppliers, term]);
  const filteredPresentations = useMemo(() => presentations.filter(presentation =>
    [presentation.name, presentation.code, presentation.supplier_name, presentation.item_name]
      .some(value => value?.toLocaleLowerCase('es-MX').includes(term))), [presentations, term]);

  const handleSelectSupplier = (supplier: Supplier, editMode = false) => {
    if (editMode && !canManageCatalog) return;
    setSelectedSupplier(supplier);
    setFormData(supplierForm(supplier));
    setIsEditing(editMode);
    supplierMutation.reset();
    setIsFastTabOpen(true);
  };
  const handleNewSupplier = () => handleSelectSupplier({
    id: `new-${Date.now()}`,
    code: `PROV-${Math.floor(100 + Math.random() * 900)}`,
    commercial_name: '', status: 'active', credit_days: 0,
  }, true);

  const supplierMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => {
      const existing = selectedSupplier && !selectedSupplier.id.startsWith('new-');
      return fetchApi(existing ? `/suppliers/${selectedSupplier.id}` : '/suppliers', {
        method: existing ? 'PUT' : 'POST', body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      setIsFastTabOpen(false);
    },
  });
  const handleSaveSupplier = (event: FormEvent) => {
    event.preventDefault();
    if (!canManageCatalog || !isEditing || supplierMutation.isPending) return;
    supplierMutation.mutate({
      ...formData,
      credit_days: parseInt(formData.credit_days || '0', 10),
      credit_limit: selectedSupplier?.credit_limit ?? null,
      payment_methods: [],
    });
  };
  const currentQuery = activeViewTab === 'suppliers' ? suppliersQuery : presentationsQuery;

  return <div className="suppliers-workspace">
    <header className="suppliers-heading">
      <div>
        <p className="suppliers-eyebrow">Compras y proveedores</p>
        <h1>Proveedores y cuentas por pagar</h1>
        <p className="suppliers-description">Tu directorio comercial, contactos y condiciones de compra.</p>
      </div>
      {canManageCatalog && <button type="button" className="supplier-button supplier-button--primary" onClick={handleNewSupplier}>
        <Plus size={17} aria-hidden="true" />Nuevo proveedor
      </button>}
    </header>

    <div className="suppliers-toolbar">
      <div className="suppliers-tabs" role="group" aria-label="Vista del catálogo">
        <button type="button" aria-pressed={activeViewTab === 'suppliers'} onClick={() => { setActiveViewTab('suppliers'); setSearch(''); }}>
          Cartera de proveedores <span>{suppliersQuery.isSuccess ? suppliers.length : '—'}</span>
        </button>
        <button type="button" aria-pressed={activeViewTab === 'presentations'} onClick={() => { setActiveViewTab('presentations'); setSearch(''); }}>
          Presentaciones de compra <span>{presentationsQuery.isSuccess ? presentations.length : '—'}</span>
        </button>
      </div>
      <label className="suppliers-search">
        <Search size={17} aria-hidden="true" />
        <input aria-label={activeViewTab === 'suppliers' ? 'Buscar proveedores' : 'Buscar presentaciones'}
          value={search} onChange={event => setSearch(event.target.value)}
          placeholder={activeViewTab === 'suppliers' ? 'Nombre, RFC o código' : 'Presentación, proveedor o insumo'} />
        {search && <button type="button" onClick={() => setSearch('')} aria-label="Limpiar búsqueda"><X size={15} /></button>}
      </label>
    </div>

    <section className="suppliers-catalog" aria-label={activeViewTab === 'suppliers' ? 'Directorio de proveedores' : 'Catálogo de presentaciones'}>
      {currentQuery.isError ? <QueryMessage title={activeViewTab === 'suppliers' ? 'No pudimos cargar los proveedores.' : 'No pudimos cargar las presentaciones.'}
        detail="Revisa tu conexión e inténtalo de nuevo." onRetry={() => { void currentQuery.refetch(); }} />
        : currentQuery.isPending ? <QueryMessage title="Cargando catálogo…" />
        : activeViewTab === 'suppliers' ? filteredSuppliers.length === 0
          ? <QueryMessage title={search ? 'No encontramos proveedores con esa búsqueda.' : 'Todavía no hay proveedores registrados.'} detail={search ? 'Prueba con otro nombre, RFC o código.' : 'Los proveedores que registres aparecerán aquí.'} />
          : <div className="suppliers-table-scroll" tabIndex={0} role="region" aria-label="Tabla de proveedores">
            <table className="suppliers-table">
              <thead><tr><th>Código</th><th>Proveedor / Razón social</th><th>RFC</th><th>Plazo de crédito</th><th>Estado</th><th><span className="supplier-sr-only">Acciones</span></th></tr></thead>
              <tbody>{filteredSuppliers.map(supplier => <tr key={supplier.id} data-selected={isFastTabOpen && selectedSupplier?.id === supplier.id}>
                <td><span className="supplier-code">{supplier.code}</span></td>
                <td><button type="button" className="supplier-name" onClick={() => handleSelectSupplier(supplier)}>{supplier.commercial_name}</button>
                  {supplier.legal_name && supplier.legal_name !== supplier.commercial_name && <span className="supplier-secondary">{supplier.legal_name}</span>}</td>
                <td>{supplier.tax_id || <span className="supplier-muted">Sin registrar</span>}</td>
                <td>{supplier.credit_days} días</td>
                <td><span className="supplier-status" data-active={supplier.status === 'active'}>{supplier.status === 'active' ? 'Activo' : 'Inactivo'}</span></td>
                <td><div className="supplier-row-actions">
                  <button type="button" className="supplier-button supplier-button--small" onClick={() => handleSelectSupplier(supplier)} aria-label={`Ver ${supplier.commercial_name}`}>Ver ficha</button>
                  {canManageCatalog && <button type="button" className="supplier-button supplier-button--icon" onClick={() => handleSelectSupplier(supplier, true)} aria-label={`Editar ${supplier.commercial_name}`}><Edit size={16} /></button>}
                </div></td>
              </tr>)}</tbody>
            </table>
          </div>
        : filteredPresentations.length === 0 ? <QueryMessage title={search ? 'No encontramos presentaciones con esa búsqueda.' : 'Todavía no hay presentaciones registradas.'} />
          : <div className="suppliers-table-scroll" tabIndex={0} role="region" aria-label="Tabla de presentaciones">
            <table className="suppliers-table"><thead><tr><th>Código</th><th>Presentación</th><th>Proveedor</th><th>Insumo base</th><th>Último precio neto</th></tr></thead>
              <tbody>{filteredPresentations.map(presentation => <tr key={presentation.id}>
                <td><span className="supplier-code">{presentation.code}</span></td><td><strong>{presentation.name}</strong></td>
                <td>{presentation.supplier_name}</td><td>{presentation.item_name}</td><td className="supplier-price">${presentation.last_net_price.toFixed(2)} MXN</td>
              </tr>)}</tbody>
            </table>
          </div>}
    </section>
    <p className="suppliers-footnote"><FileText size={15} aria-hidden="true" />Las condiciones del catálogo se consultan por proveedor. Los pagos se gestionan en el flujo de compras.</p>

    <FastTabDrawer isOpen={isFastTabOpen} onClose={() => { if (!supplierMutation.isPending) setIsFastTabOpen(false); }} size="wide"
      title={selectedSupplier?.commercial_name || 'Nuevo proveedor'}
      subtitle={isEditing ? 'Edición de datos del proveedor' : 'Ficha del proveedor'}
      badge={<span className="supplier-status" data-active={selectedSupplier?.status === 'active'}>{selectedSupplier?.status === 'active' ? 'Activo' : 'Inactivo'}</span>}
      footerActions={<div className="supplier-footer-actions">
        <button type="button" className="supplier-button" disabled={supplierMutation.isPending} onClick={() => setIsFastTabOpen(false)}>Cerrar</button>
        {canManageCatalog && isEditing && <button type="submit" form="supplier-form" className="supplier-button supplier-button--primary" disabled={supplierMutation.isPending}>
          <Save size={16} aria-hidden="true" />{supplierMutation.isPending ? 'Guardando…' : 'Guardar proveedor'}
        </button>}
      </div>}>
      <div className="supplier-context">
        <div className="supplier-context-icon"><Building2 size={24} aria-hidden="true" /></div>
        <div><span className="suppliers-eyebrow">Identificación comercial</span><strong>{selectedSupplier?.code}</strong>
          <p>{selectedSupplier?.tax_id || 'RFC sin registrar'} · Crédito: {selectedSupplier?.credit_days ?? 0} días</p></div>
      </div>
      <details className="supplier-section" open>
        <summary>Datos fiscales y comerciales<ChevronDown size={17} aria-hidden="true" /></summary>
        <div className="supplier-section-content">
          <p className="supplier-section-hint">Identidad, contacto y plazo de pago del proveedor.</p>
          <form id="supplier-form" onSubmit={handleSaveSupplier}>
            <fieldset disabled={!canManageCatalog || !isEditing || supplierMutation.isPending}>
              <div className="supplier-form-grid">
                {fields.map(field => <div className={`supplier-field${field.wide ? ' supplier-field--wide' : ''}`} key={field.key}>
                  <label htmlFor={`supplier-${field.key.replaceAll('_', '-')}`}>{field.label}</label>
                  <input id={`supplier-${field.key.replaceAll('_', '-')}`} type={field.type ?? 'text'}
                    value={formData[field.key]} min={field.key === 'credit_days' ? 0 : undefined} step={field.key === 'credit_days' ? 1 : undefined}
                    required={field.key === 'commercial_name'} placeholder={isEditing ? undefined : 'Sin registrar'}
                    onChange={event => setFormData({ ...formData, [field.key]: event.target.value })} />
                </div>)}
              </div>
            </fieldset>
            {supplierMutation.isError && <p className="supplier-form-error" role="alert">No pudimos guardar el proveedor. {supplierMutation.error instanceof Error ? supplierMutation.error.message : 'Inténtalo de nuevo.'}</p>}
          </form>
        </div>
      </details>
      {/* FastTab 2: Cartera de Facturas — sin información financiera simulada. */}
      <details className="supplier-section" open>
        <summary>Cuentas por pagar<ChevronDown size={17} aria-hidden="true" /></summary>
        <div className="supplier-section-content">
          <div className="supplier-finance-notice"><FileText size={22} aria-hidden="true" /><div>
            <strong>Información financiera no disponible</strong>
            <p>El saldo y los vencimientos no están disponibles en esta vista.</p>
            <p>Consulta los documentos registrados en compras para revisar cada operación.</p>
            <Link to="/purchases">Ir a compras <span aria-hidden="true">→</span></Link>
          </div></div>
        </div>
      </details>
    </FastTabDrawer>
  </div>;
}

export default SuppliersList;
