import React, { useCallback, useEffect, useState } from 'react';
import { Card, Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { User, Phone, Mail, MapPin, ReceiptText } from 'lucide-react';

interface CustomerPhone {
  captured_number: string;
  is_primary: boolean;
}

interface CustomerAddress {
  id: string;
  alias: string;
  street: string;
  exterior_number: string;
  neighborhood: string;
  postal_code: string;
  city: string;
  municipality: string;
  state: string;
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

const emptyCustomer = { name: '', email: '', phone: '' };
const emptyAddress = {
  alias: 'Casa', street: '', exterior_number: '', neighborhood: '', postal_code: '',
  city: 'Mazatlán', municipality: 'Mazatlán', state: 'Sinaloa', is_default: false,
};
const emptyTax = {
  legal_name: '', tax_id: '', tax_regime: '', fiscal_postal_code: '', cfdi_use: '', billing_email: '',
};

const Customers = () => {
  const branchId = localStorage.getItem('pos_branch_id') || '';
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [customerModal, setCustomerModal] = useState(false);
  const [addressCustomer, setAddressCustomer] = useState<Customer | null>(null);
  const [taxCustomer, setTaxCustomer] = useState<Customer | null>(null);
  const [customerForm, setCustomerForm] = useState(emptyCustomer);
  const [addressForm, setAddressForm] = useState(emptyAddress);
  const [taxForm, setTaxForm] = useState(emptyTax);
  const [saving, setSaving] = useState(false);

  const loadCustomers = useCallback(async () => {
    try {
      setError('');
      const query = branchId ? `?branch_id=${branchId}` : '';
      setCustomers(await fetchApi<Customer[]>(`/customers${query}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible cargar clientes.');
      setCustomers([]);
    } finally {
      setLoading(false);
    }
  }, [branchId]);

  useEffect(() => { void loadCustomers(); }, [loadCustomers]);

  const saveCustomer = async () => {
    setSaving(true);
    try {
      await fetchApi('/customers', {
        method: 'POST',
        body: JSON.stringify({
          branch_id: branchId,
          name: customerForm.name,
          email: customerForm.email,
          phones: customerForm.phone ? [{ number: customerForm.phone, is_primary: true, whatsapp_enabled: true }] : [],
        }),
      });
      setCustomerModal(false);
      setCustomerForm(emptyCustomer);
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
    setTaxForm(customer.tax_profile ? {
      legal_name: customer.tax_profile.legal_name,
      tax_id: customer.tax_profile.tax_id,
      tax_regime: customer.tax_profile.tax_regime,
      fiscal_postal_code: customer.tax_profile.fiscal_postal_code,
      cfdi_use: customer.tax_profile.cfdi_use || '',
      billing_email: customer.tax_profile.billing_email || '',
    } : emptyTax);
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
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: 8, color: 'var(--text-main)' }}>Directorio de clientes</h1>
          <p style={{ color: 'var(--text-muted)' }}>Teléfonos, domicilios y datos fiscales separados.</p>
        </div>
        <Button variant="primary" onClick={() => setCustomerModal(true)}>+ Nuevo cliente</Button>
      </div>

      {error && <div role="alert" style={{ marginBottom: 16, color: '#b91c1c' }}>{error}</div>}
      <Card>
        {loading ? <div style={{ padding: 40, textAlign: 'center' }}>Cargando clientes...</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead><tr style={{ borderBottom: '1px solid var(--glass-border)', color: 'var(--text-muted)' }}>
              <th style={{ padding: 12 }}>Nombre</th><th>Teléfono</th><th>Correo</th><th>Domicilios</th><th>Historial</th><th>Acciones</th>
            </tr></thead>
            <tbody>
              {customers.length === 0 ? <tr><td colSpan={6} style={{ padding: 40, textAlign: 'center' }}>No hay clientes registrados.</td></tr> : customers.map((customer) => {
                const primaryPhone = customer.phones.find((phone) => phone.is_primary) || customer.phones[0];
                return <tr key={customer.id} style={{ borderBottom: '1px solid var(--glass-border)' }}>
                  <td style={{ padding: 12, fontWeight: 600 }}><span style={{ display: 'flex', gap: 8 }}><User size={18} />{customer.name}</span></td>
                  <td><span style={{ display: 'flex', gap: 6 }}><Phone size={14} />{primaryPhone?.captured_number || 'No registrado'}</span></td>
                  <td><span style={{ display: 'flex', gap: 6 }}><Mail size={14} />{customer.email || 'No registrado'}</span></td>
                  <td>{customer.addresses.length}{customer.addresses.some((address) => address.is_default) ? ' · predeterminado' : ''}</td>
                  <td>{customer.order_summary.order_count} pedidos · {(customer.order_summary.average_ticket_cents / 100).toLocaleString('es-MX', { style: 'currency', currency: 'MXN' })}</td>
                  <td><div style={{ display: 'flex', gap: 8 }}>
                    <Button variant="secondary" onClick={() => setAddressCustomer(customer)}><MapPin size={15} /> Domicilio</Button>
                    <Button variant="secondary" onClick={() => openTaxProfile(customer)}><ReceiptText size={15} /> Fiscal</Button>
                  </div></td>
                </tr>;
              })}
            </tbody>
          </table>
        )}
      </Card>

      <Modal isOpen={customerModal} onClose={() => setCustomerModal(false)} title="Nuevo cliente">
        <FormFields fields={[
          ['Nombre', customerForm.name, (value) => setCustomerForm({ ...customerForm, name: value })],
          ['Teléfono mexicano', customerForm.phone, (value) => setCustomerForm({ ...customerForm, phone: value })],
          ['Correo', customerForm.email, (value) => setCustomerForm({ ...customerForm, email: value })],
        ]} />
        <ModalActions saving={saving} onCancel={() => setCustomerModal(false)} onSave={saveCustomer} />
      </Modal>

      <Modal isOpen={Boolean(addressCustomer)} onClose={() => setAddressCustomer(null)} title={`Nuevo domicilio · ${addressCustomer?.name || ''}`}>
        <FormFields fields={[
          ['Alias', addressForm.alias, (value) => setAddressForm({ ...addressForm, alias: value })],
          ['Calle', addressForm.street, (value) => setAddressForm({ ...addressForm, street: value })],
          ['Número exterior', addressForm.exterior_number, (value) => setAddressForm({ ...addressForm, exterior_number: value })],
          ['Colonia', addressForm.neighborhood, (value) => setAddressForm({ ...addressForm, neighborhood: value })],
          ['Código postal', addressForm.postal_code, (value) => setAddressForm({ ...addressForm, postal_code: value })],
          ['Ciudad', addressForm.city, (value) => setAddressForm({ ...addressForm, city: value })],
          ['Municipio', addressForm.municipality, (value) => setAddressForm({ ...addressForm, municipality: value })],
          ['Estado', addressForm.state, (value) => setAddressForm({ ...addressForm, state: value })],
        ]} />
        <label style={{ display: 'flex', gap: 8, marginTop: 12 }}><input type="checkbox" checked={addressForm.is_default} onChange={(event) => setAddressForm({ ...addressForm, is_default: event.target.checked })} /> Predeterminado</label>
        <ModalActions saving={saving} onCancel={() => setAddressCustomer(null)} onSave={saveAddress} />
      </Modal>

      <Modal isOpen={Boolean(taxCustomer)} onClose={() => setTaxCustomer(null)} title={`Datos fiscales · ${taxCustomer?.name || ''}`}>
        <FormFields fields={[
          ['Razón social', taxForm.legal_name, (value) => setTaxForm({ ...taxForm, legal_name: value })],
          ['RFC', taxForm.tax_id, (value) => setTaxForm({ ...taxForm, tax_id: value })],
          ['Régimen fiscal', taxForm.tax_regime, (value) => setTaxForm({ ...taxForm, tax_regime: value })],
          ['Código postal fiscal', taxForm.fiscal_postal_code, (value) => setTaxForm({ ...taxForm, fiscal_postal_code: value })],
          ['Uso CFDI', taxForm.cfdi_use, (value) => setTaxForm({ ...taxForm, cfdi_use: value })],
          ['Correo de facturación', taxForm.billing_email, (value) => setTaxForm({ ...taxForm, billing_email: value })],
        ]} />
        <ModalActions saving={saving} onCancel={() => setTaxCustomer(null)} onSave={saveTaxProfile} />
      </Modal>
    </div>
  );
};

type Field = [string, string, (value: string) => void];
const FormFields = ({ fields }: { fields: Field[] }) => <div style={{ display: 'grid', gap: 12 }}>
  {fields.map(([label, value, onChange]) => <label key={label} style={{ display: 'grid', gap: 4 }}>
    <span style={{ fontWeight: 600 }}>{label}</span>
    <Input value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => onChange(event.target.value)} />
  </label>)}
</div>;

const ModalActions = ({ saving, onCancel, onSave }: { saving: boolean; onCancel: () => void; onSave: () => void }) => (
  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
    <Button variant="secondary" onClick={onCancel}>Cancelar</Button>
    <Button variant="primary" onClick={onSave} disabled={saving}>{saving ? 'Guardando...' : 'Guardar'}</Button>
  </div>
);

export default Customers;
