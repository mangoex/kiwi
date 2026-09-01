import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import {
  User, Phone, Mail, MapPin, ReceiptText, Search, Plus,
  Store, ShoppingBag, MessageCircle, ChevronLeft, ChevronRight,
  Edit2, CheckCircle, Home
} from 'lucide-react';
import { usePosSession } from '../../session';

interface CustomerPhone {
  captured_number: string;
  is_primary: boolean;
}

interface CustomerAddress {
  id: string;
  alias: string;
  street: string;
  exterior_number: string;
  interior_number?: string;
  neighborhood: string;
  postal_code: string;
  city: string;
  municipality: string;
  state: string;
  notes?: string;
  is_default: boolean;
}

interface TaxProfile {
  legal_name: string;
  tax_id: string;
  tax_regime: string;
  fiscal_postal_code: string;
  cfdi_use?: string;
  billing_email?: string;
}

interface Customer {
  id: string;
  name: string;
  email?: string;
  phones: CustomerPhone[];
  addresses: CustomerAddress[];
  tax_profile?: TaxProfile;
  order_summary: {
    order_count: number;
    average_ticket_cents: number;
    last_order_at?: string;
  };
  created_at: string;
}

interface CustomerPage {
  items: Customer[];
  total: number;
  limit: number;
  offset: number;
}

const formatMoney = (cents: number): string => {
  return (cents / 100).toLocaleString('es-MX', { style: 'currency', currency: 'MXN' });
};

const emptyCustomer = { name: '', email: '', phone: '' };
const emptyAddress = {
  alias: 'Casa',
  street: '',
  exterior_number: '',
  interior_number: '',
  neighborhood: '',
  postal_code: '',
  city: 'Mazatlán',
  municipality: 'Mazatlán',
  state: 'Sinaloa',
  notes: '',
  is_default: false,
};
const emptyTax = {
  legal_name: '',
  tax_id: '',
  tax_regime: '612',
  fiscal_postal_code: '',
  cfdi_use: 'G03',
  billing_email: '',
};

const getInitials = (name: string): string => {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
};

const Customers = () => {
  const { session } = usePosSession();
  const branchId = session?.active_branch?.id || '';
  const branchName = session?.active_branch?.name || 'Sucursal';
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const pageSize = 50;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Modals
  const [customerModal, setCustomerModal] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [addressCustomer, setAddressCustomer] = useState<Customer | null>(null);
  const [taxCustomer, setTaxCustomer] = useState<Customer | null>(null);
  const [customerForm, setCustomerForm] = useState(emptyCustomer);
  const [addressForm, setAddressForm] = useState(emptyAddress);
  const [taxForm, setTaxForm] = useState(emptyTax);
  const [saving, setSaving] = useState(false);

  const loadCustomers = useCallback(async () => {
    try {
      setError('');
      const params = new URLSearchParams({ limit: String(pageSize), offset: String(offset) });
      if (branchId) params.set('branch_id', branchId);
      if (search.trim()) params.set('q', search.trim());
      const page = await fetchApi<CustomerPage>(`/customers?${params.toString()}`);
      setCustomers(page.items);
      setTotal(page.total);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible cargar clientes.');
      setCustomers([]);
    } finally {
      setLoading(false);
    }
  }, [branchId, offset, search]);

  useEffect(() => {
    void loadCustomers();
  }, [loadCustomers]);

  const stats = useMemo(() => {
    const withOrders = customers.filter((c) => (c.order_summary?.order_count || 0) > 0).length;
    const withAddresses = customers.filter((c) => (c.addresses || []).length > 0).length;
    const totalSpent = customers.reduce((acc, c) => acc + (c.order_summary?.average_ticket_cents || 0), 0);
    const avgTicket = withOrders > 0 ? Math.round(totalSpent / withOrders) : 0;
    return { withOrders, withAddresses, avgTicket };
  }, [customers]);

  const openNewCustomer = () => {
    setEditingCustomer(null);
    setCustomerForm(emptyCustomer);
    setError('');
    setCustomerModal(true);
  };

  const openEditCustomer = (customer: Customer) => {
    setEditingCustomer(customer);
    const primaryPhone = customer.phones.find((p) => p.is_primary)?.captured_number || customer.phones[0]?.captured_number || '';
    setCustomerForm({
      name: customer.name,
      email: customer.email || '',
      phone: primaryPhone,
    });
    setError('');
    setCustomerModal(true);
  };

  const saveCustomer = async () => {
    setSaving(true);
    try {
      if (editingCustomer) {
        await fetchApi(`/customers/${editingCustomer.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            branch_id: branchId,
            name: customerForm.name.trim(),
            email: customerForm.email.trim() || null,
          }),
        });
      } else {
        await fetchApi('/customers', {
          method: 'POST',
          body: JSON.stringify({
            branch_id: branchId,
            name: customerForm.name.trim(),
            email: customerForm.email.trim() || undefined,
            phones: customerForm.phone.trim()
              ? [{ number: customerForm.phone.trim(), is_primary: true, whatsapp_enabled: true }]
              : [],
          }),
        });
      }
      setCustomerModal(false);
      setCustomerForm(emptyCustomer);
      setEditingCustomer(null);
      await loadCustomers();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible guardar el cliente.');
    } finally {
      setSaving(false);
    }
  };

  const saveAddress = async () => {
    if (!addressCustomer) return;
    setSaving(true);
    try {
      await fetchApi(`/customers/${addressCustomer.id}/addresses`, {
        method: 'POST',
        body: JSON.stringify({ branch_id: branchId, ...addressForm }),
      });
      setAddressCustomer(null);
      setAddressForm(emptyAddress);
      await loadCustomers();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible guardar el domicilio.');
    } finally {
      setSaving(false);
    }
  };

  const openTaxProfile = (customer: Customer) => {
    setTaxCustomer(customer);
    setTaxForm(
      customer.tax_profile
        ? {
            legal_name: customer.tax_profile.legal_name,
            tax_id: customer.tax_profile.tax_id,
            tax_regime: customer.tax_profile.tax_regime || '612',
            fiscal_postal_code: customer.tax_profile.fiscal_postal_code,
            cfdi_use: customer.tax_profile.cfdi_use || 'G03',
            billing_email: customer.tax_profile.billing_email || '',
          }
        : emptyTax
    );
  };

  const saveTaxProfile = async () => {
    if (!taxCustomer) return;
    setSaving(true);
    try {
      await fetchApi(`/customers/${taxCustomer.id}/tax-profile`, {
        method: 'PUT',
        body: JSON.stringify({ branch_id: branchId, ...taxForm }),
      });
      setTaxCustomer(null);
      setTaxForm(emptyTax);
      await loadCustomers();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible guardar los datos fiscales.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: '24px 32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <div style={{ background: '#ecfdf5', color: '#059669', padding: '8px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <User size={24} />
            </div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 800, margin: 0, color: 'var(--text-main, #0f172a)' }}>
              Clientes de la Sucursal
            </h1>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', background: '#f1f5f9', color: '#334155', padding: '4px 10px', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 700 }}>
              <Store size={13} />
              {branchName}
            </span>
          </div>
          <p style={{ color: 'var(--text-muted, #64748b)', margin: 0, fontSize: '0.9rem' }}>
            Directorio operativo de clientes y domicilios para entrega y facturación en {branchName}.
          </p>
        </div>

        <Button
          variant="primary"
          onClick={openNewCustomer}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '10px 20px', borderRadius: '12px', fontWeight: 700 }}
        >
          <Plus size={18} />
          <span>+ Nuevo Cliente</span>
        </Button>
      </div>

      {/* Stats Summary Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', marginBottom: '24px' }}>
        <div style={{ background: 'var(--bg-card, #ffffff)', border: '1px solid var(--glass-border, #e2e8f0)', borderRadius: '14px', padding: '14px 18px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Total en Sucursal</span>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-main, #0f172a)', marginTop: '4px' }}>
            {total.toLocaleString('es-MX')}
          </div>
        </div>

        <div style={{ background: 'var(--bg-card, #ffffff)', border: '1px solid var(--glass-border, #e2e8f0)', borderRadius: '14px', padding: '14px 18px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Con Domicilio Registrado</span>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-main, #0f172a)', marginTop: '4px' }}>
            {stats.withAddresses}
          </div>
        </div>

        <div style={{ background: 'var(--bg-card, #ffffff)', border: '1px solid var(--glass-border, #e2e8f0)', borderRadius: '14px', padding: '14px 18px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Con Historial de Compras</span>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#10b981', marginTop: '4px' }}>
            {stats.withOrders}
          </div>
        </div>

        <div style={{ background: 'var(--bg-card, #ffffff)', border: '1px solid var(--glass-border, #e2e8f0)', borderRadius: '14px', padding: '14px 18px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Ticket Promedio</span>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-main, #0f172a)', marginTop: '4px' }}>
            {formatMoney(stats.avgTicket)}
          </div>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div role="alert" style={{ marginBottom: '16px', background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '10px 16px', borderRadius: '12px', fontSize: '0.9rem' }}>
          {error}
        </div>
      )}

      {/* Search toolbar */}
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1 1 320px', maxWidth: '520px' }}>
          <Search size={18} style={{ position: 'absolute', left: 14, top: 12, color: '#94a3b8' }} />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
            placeholder="Buscar por nombre, teléfono o correo..."
            style={{ paddingLeft: '40px', height: '42px', borderRadius: '12px', width: '100%', fontSize: '0.9rem' }}
          />
        </div>
        <span style={{ color: '#64748b', fontSize: '0.88rem', fontWeight: 600 }}>
          {total.toLocaleString('es-MX')} clientes encontrados
        </span>
      </div>

      {/* Customer List Card */}
      <div style={{ background: 'var(--bg-card, #ffffff)', border: '1px solid var(--glass-border, #e2e8f0)', borderRadius: '18px', overflow: 'hidden', boxShadow: '0 2px 5px rgba(0,0,0,0.02)' }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
            <div style={{ fontSize: '1.8rem', marginBottom: '10px' }}>⏳</div>
            <strong style={{ fontSize: '1.05rem', color: '#0f172a' }}>Cargando clientes de {branchName}...</strong>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '900px' }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--glass-border, #e2e8f0)', color: '#475569', fontSize: '0.82rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  <th style={{ padding: '14px 18px', fontWeight: 700 }}>Cliente</th>
                  <th style={{ padding: '14px 18px', fontWeight: 700 }}>Contacto</th>
                  <th style={{ padding: '14px 18px', fontWeight: 700 }}>Domicilios</th>
                  <th style={{ padding: '14px 18px', fontWeight: 700 }}>Historial Pedidos</th>
                  <th style={{ padding: '14px 18px', fontWeight: 700 }}>Datos Fiscales</th>
                  <th style={{ padding: '14px 18px', fontWeight: 700, textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {customers.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
                      <div style={{ fontSize: '2rem', marginBottom: '8px' }}>👤</div>
                      <strong style={{ fontSize: '1.1rem', color: '#0f172a' }}>No hay clientes registrados en esta sucursal</strong>
                      <p style={{ margin: '6px 0 16px', fontSize: '0.88rem' }}>Comienza registrando tu primer cliente o búsqueda por teléfono.</p>
                      <Button variant="primary" onClick={openNewCustomer}>+ Registrar Cliente</Button>
                    </td>
                  </tr>
                ) : (
                  customers.map((customer) => {
                    const primaryPhone = customer.phones.find((phone) => phone.is_primary) || customer.phones[0];
                    const cleanDigits = primaryPhone?.captured_number?.replace(/[^\d]/g, '') || '';
                    const defaultAddress = customer.addresses.find((address) => address.is_default) || customer.addresses[0];

                    return (
                      <tr
                        key={customer.id}
                        style={{ borderBottom: '1px solid var(--glass-border, #f1f5f9)', transition: 'background 0.15s ease' }}
                      >
                        {/* Avatar & Name */}
                        <td style={{ padding: '14px 18px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <div
                              style={{
                                width: '38px',
                                height: '38px',
                                borderRadius: '50%',
                                background: 'linear-gradient(135deg, #10b981, #047857)',
                                color: '#ffffff',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 800,
                                fontSize: '0.9rem',
                                flexShrink: 0,
                              }}
                            >
                              {getInitials(customer.name)}
                            </div>
                            <div>
                              <div style={{ fontWeight: 700, color: 'var(--text-main, #0f172a)', fontSize: '0.92rem' }}>
                                {customer.name}
                              </div>
                              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                                ID: {customer.id.slice(0, 8)}...
                              </span>
                            </div>
                          </div>
                        </td>

                        {/* Phone & Email */}
                        <td style={{ padding: '14px 18px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                            {primaryPhone ? (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <Phone size={13} style={{ color: '#10b981' }} />
                                <span style={{ fontWeight: 600, color: '#334155', fontSize: '0.88rem' }}>
                                  {primaryPhone.captured_number}
                                </span>
                                {cleanDigits.length >= 10 && (
                                  <a
                                    href={`https://wa.me/52${cleanDigits.slice(-10)}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    title="WhatsApp"
                                    style={{ color: '#22c55e', display: 'inline-flex' }}
                                  >
                                    <MessageCircle size={14} />
                                  </a>
                                )}
                              </div>
                            ) : (
                              <span style={{ color: '#94a3b8', fontSize: '0.82rem' }}>Sin teléfono</span>
                            )}

                            {customer.email ? (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#64748b', fontSize: '0.8rem' }}>
                                <Mail size={12} />
                                <span>{customer.email}</span>
                              </div>
                            ) : null}
                          </div>
                        </td>

                        {/* Addresses */}
                        <td style={{ padding: '14px 18px' }}>
                          {customer.addresses.length > 0 ? (
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '2px' }}>
                                <MapPin size={13} style={{ color: '#ef4444' }} />
                                <strong style={{ fontSize: '0.82rem', color: '#0f172a' }}>
                                  {defaultAddress?.alias || 'Principal'}
                                </strong>
                                <span style={{ fontSize: '0.72rem', background: '#fee2e2', color: '#991b1b', padding: '1px 5px', borderRadius: '4px', fontWeight: 600 }}>
                                  {customer.addresses.length} dir.
                                </span>
                              </div>
                              <p style={{ fontSize: '0.78rem', color: '#64748b', margin: 0, maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {defaultAddress?.street} #{defaultAddress?.exterior_number}
                              </p>
                            </div>
                          ) : (
                            <span style={{ color: '#94a3b8', fontSize: '0.82rem' }}>Sin domicilios</span>
                          )}
                        </td>

                        {/* Order Summary */}
                        <td style={{ padding: '14px 18px' }}>
                          {customer.order_summary?.order_count > 0 ? (
                            <div>
                              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0', padding: '2px 8px', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 700 }}>
                                <ShoppingBag size={12} />
                                <span>{customer.order_summary.order_count} pedidos</span>
                              </div>
                              <div style={{ fontSize: '0.76rem', color: '#64748b', marginTop: '3px' }}>
                                Promedio: <strong>{formatMoney(customer.order_summary.average_ticket_cents)}</strong>
                              </div>
                            </div>
                          ) : (
                            <span style={{ color: '#94a3b8', fontSize: '0.82rem' }}>0 pedidos</span>
                          )}
                        </td>

                        {/* Tax Profile */}
                        <td style={{ padding: '14px 18px' }}>
                          {customer.tax_profile?.tax_id ? (
                            <span style={{ background: '#fdf4ff', color: '#86198f', border: '1px solid #f5d0fe', padding: '2px 7px', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 700 }}>
                              {customer.tax_profile.tax_id}
                            </span>
                          ) : (
                            <span style={{ color: '#94a3b8', fontSize: '0.82rem' }}>No registrado</span>
                          )}
                        </td>

                        {/* Actions */}
                        <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px' }}>
                            <button
                              onClick={() => setAddressCustomer(customer)}
                              title="Agregar domicilio"
                              style={{
                                background: '#f1f5f9',
                                border: 'none',
                                color: '#334155',
                                padding: '5px 9px',
                                borderRadius: '8px',
                                fontSize: '0.78rem',
                                fontWeight: 600,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                              }}
                            >
                              <MapPin size={13} />
                              <span>Domicilio</span>
                            </button>

                            <button
                              onClick={() => openTaxProfile(customer)}
                              title="Datos fiscales"
                              style={{
                                background: '#f1f5f9',
                                border: 'none',
                                color: '#334155',
                                padding: '5px 9px',
                                borderRadius: '8px',
                                fontSize: '0.78rem',
                                fontWeight: 600,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                              }}
                            >
                              <ReceiptText size={13} />
                              <span>Fiscal</span>
                            </button>

                            <button
                              onClick={() => openEditCustomer(customer)}
                              title="Editar"
                              style={{
                                background: '#f8fafc',
                                border: '1px solid #cbd5e1',
                                color: '#0f172a',
                                padding: '5px 9px',
                                borderRadius: '8px',
                                fontSize: '0.78rem',
                                fontWeight: 700,
                                cursor: 'pointer',
                              }}
                            >
                              <Edit2 size={13} />
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
        )}

        {/* Pagination Footer */}
        <div style={{ padding: '12px 18px', background: '#f8fafc', borderTop: '1px solid var(--glass-border, #e2e8f0)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <span style={{ color: '#64748b', fontSize: '0.85rem' }}>
            Mostrando {total === 0 ? 0 : offset + 1}–{Math.min(offset + pageSize, total)} de {total.toLocaleString('es-MX')} clientes
          </span>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Button
              variant="secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - pageSize))}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '5px 10px' }}
            >
              <ChevronLeft size={15} />
              <span>Anterior</span>
            </Button>
            <Button
              variant="secondary"
              disabled={offset + pageSize >= total}
              onClick={() => setOffset(offset + pageSize)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '5px 10px' }}
            >
              <span>Siguiente</span>
              <ChevronRight size={15} />
            </Button>
          </div>
        </div>
      </div>

      {/* Modal: New / Edit Customer */}
      <Modal
        isOpen={customerModal}
        onClose={() => setCustomerModal(false)}
        title={editingCustomer ? `Editar Cliente · ${editingCustomer.name}` : 'Nuevo Cliente'}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingTop: '6px' }}>
          <label style={{ display: 'grid', gap: '4px' }}>
            <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#334155' }}>Nombre Completo *</span>
            <Input
              value={customerForm.name}
              onChange={(e) => setCustomerForm({ ...customerForm, name: e.target.value })}
              placeholder="Ej. Juan Pérez González"
            />
          </label>

          <label style={{ display: 'grid', gap: '4px' }}>
            <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#334155' }}>Teléfono Mexicano (10 dígitos)</span>
            <Input
              value={customerForm.phone}
              onChange={(e) => setCustomerForm({ ...customerForm, phone: e.target.value })}
              placeholder="Ej. 6691234567"
            />
          </label>

          <label style={{ display: 'grid', gap: '4px' }}>
            <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#334155' }}>Correo Electrónico</span>
            <Input
              value={customerForm.email}
              onChange={(e) => setCustomerForm({ ...customerForm, email: e.target.value })}
              placeholder="Ej. cliente@ejemplo.com"
            />
          </label>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
            <Button variant="secondary" onClick={() => setCustomerModal(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={saving || !customerForm.name.trim()}
              onClick={saveCustomer}
            >
              {saving ? 'Guardando...' : 'Guardar Cliente'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal: New Address */}
      <Modal
        isOpen={Boolean(addressCustomer)}
        onClose={() => setAddressCustomer(null)}
        title={`Nuevo Domicilio · ${addressCustomer?.name || ''}`}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingTop: '6px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Alias (Ej. Casa, Trabajo)</span>
              <Input
                value={addressForm.alias}
                onChange={(e) => setAddressForm({ ...addressForm, alias: e.target.value })}
              />
            </label>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Código Postal</span>
              <Input
                value={addressForm.postal_code}
                onChange={(e) => setAddressForm({ ...addressForm, postal_code: e.target.value })}
                placeholder="82000"
              />
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '10px' }}>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Calle *</span>
              <Input
                value={addressForm.street}
                onChange={(e) => setAddressForm({ ...addressForm, street: e.target.value })}
                placeholder="Av. Principal"
              />
            </label>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Núm. Ext *</span>
              <Input
                value={addressForm.exterior_number}
                onChange={(e) => setAddressForm({ ...addressForm, exterior_number: e.target.value })}
                placeholder="123"
              />
            </label>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Núm. Int</span>
              <Input
                value={addressForm.interior_number}
                onChange={(e) => setAddressForm({ ...addressForm, interior_number: e.target.value })}
                placeholder="4B"
              />
            </label>
          </div>

          <label style={{ display: 'grid', gap: '4px' }}>
            <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Colonia / Fraccionamiento *</span>
            <Input
              value={addressForm.neighborhood}
              onChange={(e) => setAddressForm({ ...addressForm, neighborhood: e.target.value })}
              placeholder="Centro"
            />
          </label>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Ciudad / Municipio</span>
              <Input
                value={addressForm.city}
                onChange={(e) => setAddressForm({ ...addressForm, city: e.target.value, municipality: e.target.value })}
              />
            </label>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Estado</span>
              <Input
                value={addressForm.state}
                onChange={(e) => setAddressForm({ ...addressForm, state: e.target.value })}
              />
            </label>
          </div>

          <label style={{ display: 'grid', gap: '4px' }}>
            <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Referencias / Notas de Entrega</span>
            <Input
              value={addressForm.notes}
              onChange={(e) => setAddressForm({ ...addressForm, notes: e.target.value })}
              placeholder="Casa amarilla con portón negro..."
            />
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', marginTop: '6px' }}>
            <input
              type="checkbox"
              checked={addressForm.is_default}
              onChange={(e) => setAddressForm({ ...addressForm, is_default: e.target.checked })}
              style={{ width: '16px', height: '16px' }}
            />
            <span style={{ fontSize: '0.88rem', color: '#334155', fontWeight: 600 }}>
              Marcar como domicilio predeterminado
            </span>
          </label>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
            <Button variant="secondary" onClick={() => setAddressCustomer(null)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={saving || !addressForm.street.trim() || !addressForm.exterior_number.trim()}
              onClick={saveAddress}
            >
              {saving ? 'Guardando...' : 'Guardar Domicilio'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal: Tax Profile */}
      <Modal
        isOpen={Boolean(taxCustomer)}
        onClose={() => setTaxCustomer(null)}
        title={`Datos Fiscales CFDI · ${taxCustomer?.name || ''}`}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingTop: '6px' }}>
          <label style={{ display: 'grid', gap: '4px' }}>
            <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Razón Social / Nombre Fiscal *</span>
            <Input
              value={taxForm.legal_name}
              onChange={(e) => setTaxForm({ ...taxForm, legal_name: e.target.value })}
              placeholder="Ej. JUAN PEREZ GONZALEZ"
            />
          </label>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>RFC *</span>
              <Input
                value={taxForm.tax_id}
                onChange={(e) => setTaxForm({ ...taxForm, tax_id: e.target.value.toUpperCase() })}
                placeholder="XAXX010101000"
              />
            </label>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Código Postal Fiscal *</span>
              <Input
                value={taxForm.fiscal_postal_code}
                onChange={(e) => setTaxForm({ ...taxForm, fiscal_postal_code: e.target.value })}
                placeholder="82000"
              />
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Régimen Fiscal (SAT)</span>
              <Input
                value={taxForm.tax_regime}
                onChange={(e) => setTaxForm({ ...taxForm, tax_regime: e.target.value })}
                placeholder="612"
              />
            </label>
            <label style={{ display: 'grid', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Uso de CFDI</span>
              <Input
                value={taxForm.cfdi_use}
                onChange={(e) => setTaxForm({ ...taxForm, cfdi_use: e.target.value })}
                placeholder="G03"
              />
            </label>
          </div>

          <label style={{ display: 'grid', gap: '4px' }}>
            <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#334155' }}>Correo para Facturación</span>
            <Input
              value={taxForm.billing_email}
              onChange={(e) => setTaxForm({ ...taxForm, billing_email: e.target.value })}
              placeholder="facturacion@empresa.com"
            />
          </label>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
            <Button variant="secondary" onClick={() => setTaxCustomer(null)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={saving || !taxForm.legal_name.trim() || !taxForm.tax_id.trim() || !taxForm.fiscal_postal_code.trim()}
              onClick={saveTaxProfile}
            >
              {saving ? 'Guardando...' : 'Guardar Datos Fiscales'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default Customers;
