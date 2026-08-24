import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Modal, Badge } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Truck, PackagePlus, Edit, Phone, Mail, MapPin, Building2, Hash, FileText } from 'lucide-react';
import '../../premium-catalogs.css';
import { resolveBranchId } from '../../lib/branchContext';

interface Supplier {
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
  contacts?: Array<{ id: string; name: string; phone?: string; primary_for_orders: boolean }>;
}

interface Item {
  id: string;
  name: string;
  sku: string;
  base_unit_id: string;
  unit_code: string;
}

interface Unit {
  id: string;
  name: string;
  code: string;
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

const INITIAL_SUPPLIER_FORM = {
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
  credit_days: '0',
  credit_limit: '',
  notes: '',
};

const SuppliersList = () => {
  const queryClient = useQueryClient();
  const branchId = resolveBranchId();
  const [activeTab, setActiveTab] = useState<'suppliers' | 'presentations'>('suppliers');
  const [supplierOpen, setSupplierOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [presentationOpen, setPresentationOpen] = useState(false);

  const [supplierForm, setSupplierForm] = useState(INITIAL_SUPPLIER_FORM);
  const [presentationForm, setPresentationForm] = useState({
    supplier_id: '',
    item_id: '',
    code: '',
    name: '',
    package_type: 'bag',
    commercial_unit_id: '',
    usable_content: '',
    last_net_price: '',
  });

  const query = branchId ? `?branch_id=${branchId}` : '';

  const { data: suppliers = [], isLoading: loadingSuppliers } = useQuery<Supplier[]>({
    queryKey: ['suppliers'],
    queryFn: () => fetchApi(`/suppliers${query}`),
  });

  const { data: presentations = [], isLoading: loadingPresentations } = useQuery<Presentation[]>({
    queryKey: ['purchase-presentations'],
    queryFn: () => fetchApi(`/purchase-presentations${query}`),
  });

  const { data: items = [] } = useQuery<Item[]>({
    queryKey: ['inventory', 'items'],
    queryFn: () => fetchApi('/inventory/items'),
  });

  const { data: units = [] } = useQuery<Unit[]>({
    queryKey: ['inventory', 'units'],
    queryFn: () => fetchApi('/inventory/units'),
  });

  const supplierMutation = useMutation({
    mutationFn: (payload: typeof supplierForm) => {
      const body = {
        ...payload,
        credit_days: Number(payload.credit_days || 0),
        credit_limit: payload.credit_limit ? Number(payload.credit_limit) : null,
        delivery_days: [],
        payment_methods: [],
      };
      if (editingSupplier) {
        return fetchApi(`/suppliers/${editingSupplier.id}`, {
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
      void queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      setSupplierOpen(false);
      setEditingSupplier(null);
    },
  });

  const presentationMutation = useMutation({
    mutationFn: () => {
      const item = items.find((candidate) => candidate.id === presentationForm.item_id);
      return fetchApi('/purchase-presentations', {
        method: 'POST',
        body: JSON.stringify({
          ...presentationForm,
          base_unit_id: item?.base_unit_id,
          base_unit_yield: presentationForm.usable_content,
          commercial_quantity: '1',
          yield_percent: '1',
          tax_rate: '0',
        }),
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['purchase-presentations'] });
      setPresentationOpen(false);
    },
  });

  const openNewSupplierModal = () => {
    setEditingSupplier(null);
    setSupplierForm(INITIAL_SUPPLIER_FORM);
    setSupplierOpen(true);
  };

  const openEditSupplierModal = (s: Supplier) => {
    setEditingSupplier(s);
    setSupplierForm({
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
      credit_days: String(s.credit_days || 0),
      credit_limit: s.credit_limit ? String(s.credit_limit) : '',
      notes: s.notes || '',
    });
    setSupplierOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 className="premium-header-title">Proveedores y Catálogo de Compra</h1>
          <p className="premium-header-subtitle">
            Administra proveedores, domicilios, teléfonos, cuentas contables y presentaciones para compras y costeo.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Button variant="secondary" onClick={() => setPresentationOpen(true)}>
            <PackagePlus size={17} /> Nueva Presentación
          </Button>
          <Button variant="primary" onClick={openNewSupplierModal}>
            <Plus size={17} /> Nuevo Proveedor
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <button
          onClick={() => setActiveTab('suppliers')}
          style={{
            padding: '8px 16px',
            borderRadius: 8,
            border: 'none',
            fontWeight: 600,
            fontSize: '0.9rem',
            cursor: 'pointer',
            background: activeTab === 'suppliers' ? '#047857' : '#f1f5f9',
            color: activeTab === 'suppliers' ? '#ffffff' : '#64748b',
          }}
        >
          Proveedores ({suppliers.length})
        </button>
        <button
          onClick={() => setActiveTab('presentations')}
          style={{
            padding: '8px 16px',
            borderRadius: 8,
            border: 'none',
            fontWeight: 600,
            fontSize: '0.9rem',
            cursor: 'pointer',
            background: activeTab === 'presentations' ? '#047857' : '#f1f5f9',
            color: activeTab === 'presentations' ? '#ffffff' : '#64748b',
          }}
        >
          Presentaciones de Compra ({presentations.length})
        </button>
      </div>

      {activeTab === 'suppliers' ? (
        <div className="premium-card" style={{ overflowX: 'auto' }}>
          {loadingSuppliers ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando proveedores...</div>
          ) : suppliers.length === 0 ? (
            <div className="premium-empty-state">
              <Truck size={48} className="premium-empty-icon" />
              <h3>No hay proveedores registrados</h3>
              <p>Da de alta a tus proveedores con sus datos fiscales y de contacto.</p>
            </div>
          ) : (
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Proveedor / Razón Social</th>
                  <th>RFC</th>
                  <th>Tipo</th>
                  <th>Contacto</th>
                  <th>Dirección y CP</th>
                  <th>Cuenta Contable</th>
                  <th>Estatus</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((s) => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 600, fontFamily: 'monospace' }}>{s.code}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ padding: 6, background: '#f0fdf4', color: '#16a34a', borderRadius: 6 }}>
                          <Building2 size={16} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, color: '#0f172a' }}>{s.commercial_name}</div>
                          {s.legal_name && <div style={{ fontSize: '0.8rem', color: '#64748b' }}>{s.legal_name}</div>}
                        </div>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>{s.tax_id || '—'}</td>
                    <td>
                      <Badge variant="info">
                        {SUPPLIER_TYPES.find((t) => t.value === (s.supplier_type || 'insumos'))?.label.split(' ')[0] || s.supplier_type || 'Insumos'}
                      </Badge>
                    </td>
                    <td>
                      <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {s.phone && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#334155' }}>
                            <Phone size={13} style={{ color: '#047857' }} />
                            <span>{s.phone}</span>
                          </div>
                        )}
                        {s.billing_email && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#64748b' }}>
                            <Mail size={13} />
                            <span>{s.billing_email}</span>
                          </div>
                        )}
                        {!s.phone && !s.billing_email && <span style={{ color: '#94a3b8' }}>—</span>}
                      </div>
                    </td>
                    <td>
                      <div style={{ fontSize: '0.85rem', maxWidth: 220, color: '#475569' }}>
                        {s.fiscal_address ? (
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 4 }}>
                            <MapPin size={13} style={{ marginTop: 2, flexShrink: 0, color: '#047857' }} />
                            <span>
                              {s.fiscal_address}
                              {s.fiscal_postal_code ? `, C.P. ${s.fiscal_postal_code}` : ''}
                            </span>
                          </div>
                        ) : (
                          <span style={{ color: '#94a3b8' }}>—</span>
                        )}
                      </div>
                    </td>
                    <td>
                      {s.accounting_reference ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'monospace', fontSize: '0.85rem', color: '#0284c7' }}>
                          <Hash size={13} />
                          <span>{s.accounting_reference}</span>
                        </div>
                      ) : (
                        <span style={{ color: '#94a3b8' }}>—</span>
                      )}
                    </td>
                    <td>
                      <Badge variant={s.status === 'active' ? 'success' : s.status === 'suspended' ? 'warning' : 'default'}>
                        {s.status === 'active' ? 'Activo' : s.status === 'suspended' ? 'Suspendido' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="premium-action-btn edit"
                        title="Editar proveedor"
                        onClick={() => openEditSupplierModal(s)}
                      >
                        <Edit size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <div className="premium-card" style={{ overflowX: 'auto' }}>
          {loadingPresentations ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando presentaciones...</div>
          ) : presentations.length === 0 ? (
            <div className="premium-empty-state">
              <PackagePlus size={48} className="premium-empty-icon" />
              <h3>No hay presentaciones de compra registradas</h3>
              <p>Asocia empaques y presentaciones comerciales a tus insumos base.</p>
            </div>
          ) : (
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Presentación</th>
                  <th>Proveedor</th>
                  <th>Insumo Base</th>
                  <th>Último Precio</th>
                  <th>Costo Unidad Base</th>
                </tr>
              </thead>
              <tbody>
                {presentations.map((p) => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 600, fontFamily: 'monospace' }}>{p.code}</td>
                    <td style={{ fontWeight: 500 }}>{p.name}</td>
                    <td>{p.supplier_name}</td>
                    <td>{p.item_name}</td>
                    <td style={{ fontWeight: 600, color: '#0f172a' }}>${Number(p.last_net_price).toFixed(2)}</td>
                    <td style={{ color: '#047857', fontWeight: 600 }}>
                      ${Number(p.cost_per_base_unit).toFixed(4)} / {p.base_unit_code}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Modal Proveedor */}
      <Modal
        isOpen={supplierOpen}
        onClose={() => setSupplierOpen(false)}
        title={editingSupplier ? `Editar Proveedor (${editingSupplier.code})` : 'Nuevo Proveedor'}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Fila 1: Código, Nombre Comercial */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12 }}>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Código *</span>
              <Input
                placeholder="Ej. PROV-01"
                value={supplierForm.code}
                onChange={(e: any) => setSupplierForm({ ...supplierForm, code: e.target.value.toUpperCase() })}
                disabled={Boolean(editingSupplier)}
              />
            </label>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Nombre Comercial *</span>
              <Input
                placeholder="Ej. Carnes Selectas"
                value={supplierForm.commercial_name}
                onChange={(e: any) => setSupplierForm({ ...supplierForm, commercial_name: e.target.value })}
              />
            </label>
          </div>

          {/* Fila 2: Razón Social, RFC */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Razón Social</span>
              <Input
                placeholder="Ej. Distribuidora Culiacán SA de CV"
                value={supplierForm.legal_name}
                onChange={(e: any) => setSupplierForm({ ...supplierForm, legal_name: e.target.value })}
              />
            </label>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>RFC</span>
              <Input
                placeholder="XAXX010101000"
                value={supplierForm.tax_id}
                onChange={(e: any) => setSupplierForm({ ...supplierForm, tax_id: e.target.value.toUpperCase() })}
              />
            </label>
          </div>

          {/* Fila 3: Tipo y Estatus */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Tipo de Proveedor</span>
              <select
                value={supplierForm.supplier_type}
                onChange={(e) => setSupplierForm({ ...supplierForm, supplier_type: e.target.value })}
                style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff', fontSize: '0.95rem' }}
              >
                {SUPPLIER_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </label>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Estatus</span>
              <select
                value={supplierForm.status}
                onChange={(e) => setSupplierForm({ ...supplierForm, status: e.target.value })}
                style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff', fontSize: '0.95rem' }}
              >
                <option value="active">Activo</option>
                <option value="inactive">Inactivo</option>
                <option value="suspended">Suspendido</option>
              </select>
            </label>
          </div>

          {/* Fila 4: Teléfono y Email */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Teléfono</span>
              <Input
                placeholder="667 123 4567"
                value={supplierForm.phone}
                onChange={(e: any) => setSupplierForm({ ...supplierForm, phone: e.target.value })}
              />
            </label>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Email de Compras / Facturación</span>
              <Input
                placeholder="contacto@proveedor.com"
                value={supplierForm.email}
                onChange={(e: any) => setSupplierForm({ ...supplierForm, email: e.target.value })}
              />
            </label>
          </div>

          {/* Fila 5: Dirección y Código Postal */}
          <div style={{ display: 'grid', gridTemplateColumns: '3fr 1fr', gap: 12 }}>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Dirección (Calle, Número, Colonia)</span>
              <Input
                placeholder="Av. Álvaro Obregón 123, Col. Centro"
                value={supplierForm.address}
                onChange={(e: any) => setSupplierForm({ ...supplierForm, address: e.target.value })}
              />
            </label>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Código Postal</span>
              <Input
                placeholder="80000"
                maxLength={5}
                value={supplierForm.postal_code}
                onChange={(e: any) => setSupplierForm({ ...supplierForm, postal_code: e.target.value })}
              />
            </label>
          </div>

          {/* Fila 6: Cuenta Contable y Días de Crédito */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Cuenta Contable</span>
              <Input
                placeholder="Ej. 201-01-001"
                value={supplierForm.accounting_reference}
                onChange={(e: any) => setSupplierForm({ ...supplierForm, accounting_reference: e.target.value })}
              />
            </label>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Días de Crédito</span>
              <Input
                type="number"
                min="0"
                placeholder="0"
                value={supplierForm.credit_days}
                onChange={(e: any) => setSupplierForm({ ...supplierForm, credit_days: e.target.value })}
              />
            </label>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
            <Button variant="secondary" onClick={() => setSupplierOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => supplierMutation.mutate(supplierForm)}
              disabled={supplierMutation.isPending || !supplierForm.code.trim() || !supplierForm.commercial_name.trim()}
            >
              {supplierMutation.isPending ? 'Guardando...' : editingSupplier ? 'Guardar Cambios' : 'Crear Proveedor'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal Presentación */}
      <Modal isOpen={presentationOpen} onClose={() => setPresentationOpen(false)} title="Nueva Presentación de Compra">
        <div style={{ display: 'grid', gap: 12 }}>
          <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
            <span>Proveedor</span>
            <select
              value={presentationForm.supplier_id}
              onChange={(e) => setPresentationForm({ ...presentationForm, supplier_id: e.target.value })}
              style={{ padding: '10px', borderRadius: 8, border: '1px solid #cbd5e1' }}
            >
              <option value="">Selecciona un proveedor</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>{s.commercial_name} ({s.code})</option>
              ))}
            </select>
          </label>

          <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
            <span>Insumo Base</span>
            <select
              value={presentationForm.item_id}
              onChange={(e) => setPresentationForm({ ...presentationForm, item_id: e.target.value })}
              style={{ padding: '10px', borderRadius: 8, border: '1px solid #cbd5e1' }}
            >
              <option value="">Selecciona un insumo</option>
              {items.map((item) => (
                <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>
              ))}
            </select>
          </label>

          <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
            <span>Unidad Comercial / Empaque</span>
            <select
              value={presentationForm.commercial_unit_id}
              onChange={(e) => setPresentationForm({ ...presentationForm, commercial_unit_id: e.target.value })}
              style={{ padding: '10px', borderRadius: 8, border: '1px solid #cbd5e1' }}
            >
              <option value="">Selecciona unidad</option>
              {units.map((unit) => (
                <option key={unit.id} value={unit.id}>{unit.name} ({unit.code})</option>
              ))}
            </select>
          </label>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12 }}>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Código</span>
              <Input
                placeholder="Ej. PRES-01"
                value={presentationForm.code}
                onChange={(e: any) => setPresentationForm({ ...presentationForm, code: e.target.value.toUpperCase() })}
              />
            </label>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Nombre de la Presentación</span>
              <Input
                placeholder="Ej. Costal 25 Kg"
                value={presentationForm.name}
                onChange={(e: any) => setPresentationForm({ ...presentationForm, name: e.target.value })}
              />
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Contenido Aprovechable (en unidad base)</span>
              <Input
                type="number"
                step="any"
                placeholder="Ej. 25"
                value={presentationForm.usable_content}
                onChange={(e: any) => setPresentationForm({ ...presentationForm, usable_content: e.target.value })}
              />
            </label>
            <label style={{ display: 'grid', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              <span>Precio Neto ($ MXN)</span>
              <Input
                type="number"
                step="0.01"
                placeholder="Ej. 350.00"
                value={presentationForm.last_net_price}
                onChange={(e: any) => setPresentationForm({ ...presentationForm, last_net_price: e.target.value })}
              />
            </label>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
            <Button variant="secondary" onClick={() => setPresentationOpen(false)}>Cancelar</Button>
            <Button
              variant="primary"
              onClick={() => presentationMutation.mutate()}
              disabled={presentationMutation.isPending || !presentationForm.supplier_id || !presentationForm.item_id || !presentationForm.usable_content}
            >
              {presentationMutation.isPending ? 'Guardando...' : 'Guardar Presentación'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default SuppliersList;
